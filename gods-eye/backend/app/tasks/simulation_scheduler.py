"""Automated Paper Trading Scheduler — runs simulations during market hours.

Runs hourly during IST market hours (pre-market 8:45 + every hour from 10:15-14:15)
and auto-records outcomes at 15:45 after market close.

Also takes a nightly SQLite + skills snapshot at 23:30 IST, 7 days a week,
regardless of ``SCHEDULER_ENABLED`` — paper-trading history and learned
skills need to survive volume mishaps even when the simulation loop is off.

Uses the same asyncio background-task pattern as PCRCollector for lifecycle management.
"""

import asyncio
import logging
import os
import sqlite3
import tarfile
import uuid
from datetime import datetime, time, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.config import config
from app.api.schemas import MarketInput, SimulationResult, AggregatorResult
from app.engine.orchestrator import Orchestrator
from app.engine.aggregator import Aggregator
from app.data.market_data import market_data_service
from app.memory.prediction_tracker import PredictionTracker
from app.engine.paper_trader import paper_trader
from app.data import nse_holidays

logger = logging.getLogger("gods_eye.scheduler")

# IST timezone offset: UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))
# ── Schedule Configuration ──────────────────────────────────────────────────
# Pre-market: run once at 8:45 AM to establish opening thesis
# Hourly: runs at :15 past each hour during market (10:15, 11:15, 12:15, 13:15, 14:15)
# This gives 6 total simulation points per day

PRE_MARKET_TIME = time(8, 45)
HOURLY_RUN_TIMES = [
    time(10, 15),
    time(11, 15),
    time(12, 15),
    time(13, 15),
    time(14, 15),
]
ALL_RUN_TIMES = [PRE_MARKET_TIME] + HOURLY_RUN_TIMES

# Outcome recording: 15 minutes after market close
OUTCOME_RECORD_TIME = time(15, 45)

# Daily summary: compile + persist the day's trading recap for the dashboard
DAILY_SUMMARY_TIME = time(16, 0)

# Paper trade EOD settlement: close all open positions at 15:25 IST (5 min before close)
EOD_SETTLEMENT_TIME = time(15, 25)

# Position monitoring window: check open trades every poll cycle during market hours
MARKET_OPEN_TIME = time(9, 15)
MARKET_CLOSE_TIME = time(15, 30)

# How close we need to be to a scheduled time to trigger (seconds)
SCHEDULE_TOLERANCE_SECONDS = 120  # 2-minute window

# Main loop poll interval
POLL_INTERVAL_SECONDS = 30

# ── Nightly Backup ──────────────────────────────────────────────────────────
# Snapshot SQLite + learned skills at 23:30 IST, 7 days a week regardless of
# SCHEDULER_ENABLED so paper-trading history and the SkillStore survive
# volume mishaps (accidental drop, container rebuild without volume mount,
# bad migration). Single-volume only — not offsite.
BACKUP_TIME = time(23, 30)
BACKUP_DIR = os.getenv("GODS_EYE_BACKUP_DIR", "/app/data/backups")
BACKUP_RETENTION_DAYS = 7
SKILLS_DIR = os.getenv("GODS_EYE_LEARNING_SKILL_DIR", "/app/skills")

def _get_ist_now() -> datetime:
    """Get current time in IST."""
    return datetime.now(IST)


def _is_weekday() -> bool:
    """Return True if today is a weekday (Mon-Fri). Kept for back-compat."""
    return _get_ist_now().weekday() < 5


def _is_trading_day() -> bool:
    """Return True iff today is Mon-Fri AND not an NSE holiday.

    NSE holidays come from nse_holidays.py, which caches a fetched list from
    NSE's public API and falls back to a hardcoded calendar if the fetch
    fails. Either way this call is in-memory and cheap.
    """
    today = _get_ist_now().date()
    return nse_holidays.is_trading_day(today)


def _time_diff_seconds(t1: time, t2: time) -> float:
    """Return absolute difference in seconds between two times."""
    s1 = t1.hour * 3600 + t1.minute * 60 + t1.second
    s2 = t2.hour * 3600 + t2.minute * 60 + t2.second
    return abs(s1 - s2)


class SimulationScheduler:
    """Automated paper trading scheduler.

    Lifecycle:
        scheduler.start()  → spawns background task
        scheduler.stop()   → cancels background task
        scheduler.shutdown() → clean stop

    Follows the same pattern as PCRCollector.
    """
    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._enabled: bool = config.SCHEDULER_ENABLED
        self._eod_settled_today: bool = False
        self._today_runs: Dict[str, str] = {}  # time_key → prediction_id
        self._today_date: Optional[str] = None
        self._outcome_recorded_today: bool = False
        self._backed_up_today: bool = False
        self._summary_generated_today: bool = False
        self._tracker = PredictionTracker()
        self._last_status: str = "idle"
        self._total_runs: int = 0
        self._total_outcomes: int = 0
        self._init_summary_table()

    # ── Public API ───────────────────────────────────────────────────────

    def start(self):
        """Start the scheduler background task."""
        if self._task is None or self._task.done():
            # Kick off a holiday refresh in the background so the first
            # trading-day decision after startup uses the API-fetched list
            # rather than the hardcoded fallback. Fire-and-forget — the
            # fallback is safe if the fetch is still in flight.
            asyncio.create_task(nse_holidays.refresh_holidays())
            self._task = asyncio.create_task(self._scheduler_loop())
            logger.info(
                "Simulation scheduler started (enabled=%s, schedule=%s)",
                self._enabled,
                [t.strftime("%H:%M") for t in ALL_RUN_TIMES],
            )

    def stop(self):
        """Stop the scheduler background task."""
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("Simulation scheduler stopped")
    async def shutdown(self):
        """Clean shutdown."""
        self.stop()

    def enable(self):
        """Enable automated scheduling."""
        self._enabled = True
        logger.info("Scheduler enabled")

    def disable(self):
        """Disable automated scheduling (loop keeps running but skips runs)."""
        self._enabled = False
        logger.info("Scheduler disabled")

    @property
    def status(self) -> Dict[str, Any]:
        """Return current scheduler status."""
        now = _get_ist_now()
        next_run = self._next_scheduled_time(now.time())
        today = now.date()
        return {
            "enabled": self._enabled,
            "running": self._task is not None and not self._task.done(),
            "last_status": self._last_status,
            "total_runs_today": len(self._today_runs),
            "total_runs_all_time": self._total_runs,
            "total_outcomes_recorded": self._total_outcomes,
            "today_predictions": list(self._today_runs.values()),
            "outcome_recorded_today": self._outcome_recorded_today,
            "summary_generated_today": self._summary_generated_today,
            "next_run": next_run.strftime("%H:%M") if next_run else None,
            "current_time_ist": now.strftime("%H:%M:%S"),
            "is_weekday": _is_weekday(),
            "is_trading_day": _is_trading_day(),
            "is_nse_holiday": nse_holidays.is_trading_holiday(today),
            "next_holiday": nse_holidays.next_holiday(today),
            "holiday_cache": nse_holidays.get_cache_info(),
            "schedule": [t.strftime("%H:%M") for t in ALL_RUN_TIMES],
        }

    async def trigger_now(self) -> Dict[str, Any]:
        """Manually trigger a simulation right now (bypasses schedule)."""
        logger.info("Manual simulation trigger")
        return await self._run_simulation("manual")

    async def record_outcomes_now(self) -> Dict[str, Any]:
        """Manually trigger outcome recording right now."""
        logger.info("Manual outcome recording trigger")
        return await self._record_outcomes()

    # ── Background Loop ──────────────────────────────────────────────────

    async def _scheduler_loop(self):
        """Main background loop — polls every 30s, fires at scheduled times."""
        while True:
            try:
                now = _get_ist_now()

                # Reset daily state at midnight
                today = now.strftime("%Y-%m-%d")
                if today != self._today_date:
                    self._today_runs = {}
                    self._today_date = today
                    self._outcome_recorded_today = False
                    self._eod_settled_today = False
                    self._backed_up_today = False
                    self._summary_generated_today = False
                    logger.info("Scheduler: new day %s — resetting daily state", today)
                    # Refresh the NSE holiday list at day rollover so a
                    # holiday added to NSE's calendar mid-year takes effect
                    # without a redeploy. Fire-and-forget.
                    asyncio.create_task(nse_holidays.refresh_holidays())

                current_time_for_backup = now.time()
                # ── Nightly Backup ─────────────────────────────────────────
                # Runs 7 days/week regardless of _enabled or weekday — this
                # MUST stay above the enabled/weekday gate or weekends break
                # the backup chain and the volume is one bad deploy from
                # losing a week of trade history.
                if not self._backed_up_today:
                    if _time_diff_seconds(current_time_for_backup, BACKUP_TIME) <= SCHEDULE_TOLERANCE_SECONDS:
                        logger.info("Scheduler: nightly backup time")
                        try:
                            await self._run_backup()
                            self._backed_up_today = True
                        except Exception as e:
                            logger.error("Scheduler: backup failed: %s", e)

                if not self._enabled or not _is_trading_day():
                    if not self._enabled:
                        self._last_status = "disabled"
                    elif not _is_weekday():
                        self._last_status = "waiting:weekend"
                    else:
                        self._last_status = "waiting:nse_holiday"
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    continue

                current_time = now.time()

                # Check simulation schedule
                for run_time in ALL_RUN_TIMES:
                    time_key = run_time.strftime("%H:%M")
                    if time_key not in self._today_runs:
                        if _time_diff_seconds(current_time, run_time) <= SCHEDULE_TOLERANCE_SECONDS:
                            logger.info("Scheduler: time for %s run", time_key)
                            try:
                                result = await self._run_simulation(time_key)
                                if result.get("prediction_id"):
                                    self._today_runs[time_key] = result["prediction_id"]
                                    self._total_runs += 1
                                    self._last_status = f"ran:{time_key}"
                            except Exception as e:
                                logger.error("Scheduler: simulation at %s failed: %s", time_key, e)
                                self._last_status = f"error:{time_key}"

                # ── Paper Trade Position Monitoring ────────────────────────
                # During market hours, check open trades for stop/target hits
                if MARKET_OPEN_TIME <= current_time <= MARKET_CLOSE_TIME:
                    try:
                        open_trades = paper_trader.get_open_trades()
                        if open_trades:
                            live_data = await market_data_service.build_market_input()
                            current_spot = live_data.get("nifty_spot", 0)
                            if current_spot > 0:
                                closed = paper_trader.check_open_trades(current_spot)
                                for t in closed:
                                    logger.info(
                                        "Scheduler: trade %s %s at spot=%.0f → ₹%.0f P&L",
                                        t.trade_id, t.status, current_spot, t.net_pnl or 0,
                                    )
                    except Exception as e:
                        logger.error("Scheduler: position monitor error: %s", e)

                # ── EOD Settlement ────────────────────────────────────────
                # Close PREVIOUS-DAY trades at 15:25 IST (T+1 close exit)
                # Today's trades survive overnight — matches backtest close-to-close
                if not self._eod_settled_today:
                    if _time_diff_seconds(current_time, EOD_SETTLEMENT_TIME) <= SCHEDULE_TOLERANCE_SECONDS:
                        logger.info("Scheduler: EOD settlement time")
                        try:
                            live_data = await market_data_service.build_market_input()
                            closing_spot = live_data.get("nifty_spot", 0)
                            closing_vix = live_data.get("india_vix", 15.0)
                            if closing_spot > 0:
                                closed = paper_trader.close_all_eod(closing_spot, closing_vix)
                                logger.info("Scheduler: EOD settled %d trades at spot=%.0f", len(closed), closing_spot)
                            self._eod_settled_today = True
                        except Exception as e:
                            logger.error("Scheduler: EOD settlement failed: %s", e)
                # Check outcome recording
                if not self._outcome_recorded_today:
                    if _time_diff_seconds(current_time, OUTCOME_RECORD_TIME) <= SCHEDULE_TOLERANCE_SECONDS:
                        logger.info("Scheduler: outcome recording time")
                        try:
                            await self._record_outcomes()
                            self._outcome_recorded_today = True
                        except Exception as e:
                            logger.error("Scheduler: outcome recording failed: %s", e)

                # ── Daily Summary ─────────────────────────────────────────
                # At 16:00 IST (after outcomes have been recorded), compile
                # a one-row recap of the day — P&L, trades, prediction
                # consensus — and upsert into daily_summaries for the
                # frontend dashboard widget.
                if not self._summary_generated_today:
                    if _time_diff_seconds(current_time, DAILY_SUMMARY_TIME) <= SCHEDULE_TOLERANCE_SECONDS:
                        logger.info("Scheduler: daily summary time")
                        try:
                            await self._generate_daily_summary()
                            self._summary_generated_today = True
                        except Exception as e:
                            logger.error("Scheduler: daily summary failed: %s", e)

                await asyncio.sleep(POLL_INTERVAL_SECONDS)

            except asyncio.CancelledError:
                logger.info("Scheduler loop cancelled")
                break
            except Exception as e:
                logger.error("Scheduler loop error: %s", e)
                self._last_status = f"loop_error:{e}"
                await asyncio.sleep(60)

    # ── Core Logic ───────────────────────────────────────────────────────

    async def _run_simulation(self, trigger_label: str) -> Dict[str, Any]:
        """Run a full 8-agent simulation using live market data.

        1. Fetch live market data via market_data_service
        2. Run Orchestrator.run_simulation()
        3. Aggregate with Aggregator
        4. Log prediction via PredictionTracker
        Returns dict with simulation_id, prediction_id, direction, conviction.
        """
        self._last_status = f"running:{trigger_label}"
        start_ts = datetime.now()

        # Step 1: Fetch live market data
        try:
            live_data = await market_data_service.build_market_input()
            mi_fields = {k: v for k, v in live_data.items() if not k.startswith("_")}
            market_input = MarketInput(**mi_fields)
        except Exception as e:
            logger.error("Scheduler: failed to fetch market data: %s", e)
            return {"error": f"market_data_fetch_failed: {e}"}

        nifty_spot = market_input.nifty_spot
        if nifty_spot <= 0:
            logger.warning("Scheduler: nifty_spot=%s, skipping run", nifty_spot)
            return {"error": "invalid_nifty_spot"}

        # Step 2: Run full orchestrator simulation
        try:
            orchestrator = Orchestrator()
            sim_result = await orchestrator.run_simulation(market_input)
        except Exception as e:
            logger.error("Scheduler: orchestrator failed: %s", e)
            return {"error": f"orchestrator_failed: {e}"}

        # Step 3: Aggregate
        aggregator_result = Aggregator.aggregate(            sim_result["final_outputs"],
            hybrid=True,
            tuned_weights=sim_result.get("tuned_weights"),
        )

        # Step 4: Build SimulationResult and log
        simulation_id = f"sched_{trigger_label}_{uuid.uuid4().hex[:8]}"

        # Check data freshness
        try:
            from app.data.freshness import check_data_freshness
            freshness = check_data_freshness()
            data_warnings = freshness.get("warnings", [])
        except Exception:
            data_warnings = []

        result = SimulationResult(
            simulation_id=simulation_id,
            timestamp=datetime.now(),
            market_input=market_input,
            agents_output=sim_result["final_outputs"],
            round_history=sim_result["round_history"],
            aggregator_result=aggregator_result,
            execution_time_ms=sim_result["execution_time_ms"],
            model_used=config.MODEL,
            feedback_active=sim_result.get("feedback_active", False),
            tuned_weights=sim_result.get("tuned_weights"),
            data_warnings=data_warnings,
        )
        # Log simulation + prediction
        self._tracker.log_simulation(result)
        prediction_id = self._tracker.log_prediction(result)

        elapsed = (datetime.now() - start_ts).total_seconds()
        direction = aggregator_result.final_direction
        conviction = aggregator_result.final_conviction

        logger.info(
            "Scheduler run [%s]: %s @ %.0f%% conviction (nifty=%.0f, elapsed=%.1fs, pred=%s)",
            trigger_label, direction, conviction, nifty_spot, elapsed, prediction_id,
        )

        # ── Paper Trade Execution ─────────────────────────────────────
        # If signal is BUY/SELL with sufficient conviction, open a paper trade
        trade_id = None
        try:
            vix = market_input.india_vix or 15.0
            # Pass gap estimate from orchestrator to paper trader for position sizing
            gap_est = sim_result.get("_gap_estimate_obj")
            trade = paper_trader.open_trade(
                simulation_id=simulation_id,
                prediction_id=prediction_id,
                direction=direction,
                conviction=conviction,
                nifty_spot=nifty_spot,
                vix=vix,
                gap_estimate=gap_est,
            )
            if trade:
                trade_id = trade.trade_id
                logger.info(                    "Scheduler: paper trade %s opened: %s %s×%d @ ₹%.1f (stop=%.0f, target=%.0f)",
                    trade.trade_id, trade.option_type, trade.instrument,
                    trade.lots, trade.entry_premium, trade.stop_nifty, trade.target_nifty,
                )
        except Exception as e:
            logger.error("Scheduler: paper trade execution failed: %s", e)

        return {
            "simulation_id": simulation_id,
            "prediction_id": prediction_id,
            "direction": direction,
            "conviction": conviction,
            "nifty_spot": nifty_spot,
            "trigger": trigger_label,
            "elapsed_seconds": round(elapsed, 1),
            "trade_id": trade_id,
        }

    async def _record_outcomes(self) -> Dict[str, Any]:
        """Record outcomes for all of today's predictions.

        1. Fetch NIFTY close from Dhan API
        2. For each prediction today, determine actual direction
        3. Call prediction_tracker.record_outcome()
        """
        from app.data.dhan_client import dhan_client

        # Get NIFTY close price
        nifty_data = await dhan_client.fetch_nifty50()
        if not nifty_data or not nifty_data.get("last"):
            logger.warning("Scheduler: cannot fetch NIFTY close for outcome recording")
            return {"error": "nifty_close_unavailable"}

        nifty_close = nifty_data["last"]
        nifty_prev_close = nifty_data.get("prev_close", 0)

        if nifty_prev_close <= 0:
            logger.warning("Scheduler: prev_close unavailable, cannot classify direction")
            return {"error": "prev_close_unavailable"}

        # Classify actual direction
        move_pct = ((nifty_close - nifty_prev_close) / nifty_prev_close) * 100

        if move_pct > 0.3:
            actual_direction = "BUY"  # Up day
        elif move_pct < -0.3:
            actual_direction = "SELL"  # Down day
        else:
            actual_direction = "HOLD"  # Flat day (±0.3%)

        recorded = 0
        failed = 0

        for time_key, prediction_id in self._today_runs.items():
            try:
                success = self._tracker.record_outcome(
                    prediction_id=prediction_id,
                    actual_direction=actual_direction,
                    notes=f"auto:{time_key} nifty_close={nifty_close:.0f} move={move_pct:+.2f}%",
                )
                if success:
                    recorded += 1
                    self._total_outcomes += 1
                else:
                    failed += 1
                    logger.warning("Scheduler: prediction %s not found for outcome", prediction_id)
            except Exception as e:
                failed += 1
                logger.error("Scheduler: outcome recording failed for %s: %s", prediction_id, e)

        logger.info(
            "Scheduler outcomes: %d recorded, %d failed. NIFTY close=%.0f move=%+.2f%% → %s",
            recorded, failed, nifty_close, move_pct, actual_direction,
        )

        return {
            "nifty_close": nifty_close,
            "move_pct": round(move_pct, 2),
            "actual_direction": actual_direction,
            "recorded": recorded,
            "failed": failed,
        }

    # ── Daily Summary ────────────────────────────────────────────────────

    def _init_summary_table(self) -> None:
        """Create the daily_summaries table if it doesn't exist.

        Stores a one-row-per-day recap that the frontend dashboard widget
        reads without having to re-aggregate paper_trades + predictions on
        every page load.
        """
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_summaries (
                    date_ist TEXT PRIMARY KEY,
                    is_trading_day INTEGER NOT NULL DEFAULT 1,
                    nifty_open REAL,
                    nifty_close REAL,
                    nifty_move_pct REAL,
                    actual_direction TEXT,
                    predictions_count INTEGER NOT NULL DEFAULT 0,
                    majority_direction TEXT,
                    avg_conviction REAL,
                    trades_opened INTEGER NOT NULL DEFAULT 0,
                    trades_closed INTEGER NOT NULL DEFAULT 0,
                    wins INTEGER NOT NULL DEFAULT 0,
                    losses INTEGER NOT NULL DEFAULT 0,
                    win_rate REAL,
                    gross_pnl REAL NOT NULL DEFAULT 0,
                    net_pnl REAL NOT NULL DEFAULT 0,
                    top_agent TEXT,
                    notes TEXT,
                    generated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_daily_summaries_date "
                "ON daily_summaries(date_ist DESC)"
            )
            conn.commit()
            conn.close()
        except Exception as e:
            # Non-fatal: summary writes will fail later if the table can't
            # be created, but that shouldn't block the scheduler loop.
            logger.error("Scheduler: failed to init daily_summaries table: %s", e)

    async def _generate_daily_summary(self) -> Dict[str, Any]:
        """Aggregate today's paper trades + predictions into one recap row.

        Idempotent via UPSERT on date_ist — running this twice yields the
        same row, so a scheduler retry after 15:59 failure is safe.
        """
        def _compute() -> Dict[str, Any]:
            today = _get_ist_now().date().isoformat()
            conn = sqlite3.connect(config.DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            try:
                cur = conn.cursor()

                # ── paper_trades aggregation ────────────────────────────
                cur.execute(
                    """
                    SELECT
                        COUNT(*) AS total,
                        SUM(CASE WHEN status != 'OPEN' THEN 1 ELSE 0 END) AS closed,
                        SUM(CASE WHEN status != 'OPEN' AND net_pnl > 0 THEN 1 ELSE 0 END) AS wins,
                        SUM(CASE WHEN status != 'OPEN' AND net_pnl <= 0 THEN 1 ELSE 0 END) AS losses,
                        COALESCE(SUM(gross_pnl), 0) AS gross_pnl,
                        COALESCE(SUM(net_pnl), 0) AS net_pnl
                    FROM paper_trades
                    WHERE date_ist = ?
                    """,
                    (today,),
                )
                row = cur.fetchone()
                trades_opened = int(row["total"] or 0)
                trades_closed = int(row["closed"] or 0)
                wins = int(row["wins"] or 0)
                losses = int(row["losses"] or 0)
                gross_pnl = float(row["gross_pnl"] or 0)
                net_pnl = float(row["net_pnl"] or 0)
                win_rate = (wins / trades_closed * 100) if trades_closed > 0 else None

                # ── predictions consensus ───────────────────────────────
                # Tolerate schema drift: if the predictions table doesn't
                # exist yet, skip this section instead of dropping the row.
                predictions_count = 0
                majority_direction = None
                avg_conviction = None
                actual_direction = None
                try:
                    cur.execute(
                        """
                        SELECT
                            predicted_direction AS direction,
                            COUNT(*) AS n,
                            AVG(predicted_conviction) AS avg_conv
                        FROM predictions
                        WHERE DATE(timestamp) = ?
                        GROUP BY predicted_direction
                        ORDER BY n DESC
                        """,
                        (today,),
                    )
                    buckets = cur.fetchall()
                    if buckets:
                        predictions_count = sum(int(b["n"]) for b in buckets)
                        majority_direction = buckets[0]["direction"]
                        total_conv = sum(
                            float(b["avg_conv"] or 0) * int(b["n"]) for b in buckets
                        )
                        avg_conviction = total_conv / predictions_count if predictions_count else None

                    cur.execute(
                        "SELECT actual_direction FROM predictions "
                        "WHERE DATE(timestamp) = ? AND actual_direction IS NOT NULL "
                        "LIMIT 1",
                        (today,),
                    )
                    ar = cur.fetchone()
                    if ar:
                        actual_direction = ar["actual_direction"]
                except sqlite3.OperationalError as e:
                    logger.debug("daily_summary: predictions aggregation skipped: %s", e)

                # ── top agent (best agent_accuracy today) ────────────────
                top_agent = None
                try:
                    cur.execute(
                        """
                        SELECT agent_id, AVG(CASE WHEN was_correct = 1 THEN 1.0 ELSE 0.0 END) AS acc
                        FROM agent_accuracy
                        WHERE DATE(timestamp) = ?
                        GROUP BY agent_id
                        ORDER BY acc DESC
                        LIMIT 1
                        """,
                        (today,),
                    )
                    ta = cur.fetchone()
                    if ta:
                        top_agent = ta["agent_id"]
                except sqlite3.OperationalError as e:
                    logger.debug("daily_summary: agent_accuracy lookup skipped: %s", e)

                # ── NIFTY open/close via prediction snapshot ──────────────
                nifty_open = None
                nifty_close = None
                nifty_move_pct = None
                try:
                    cur.execute(
                        """
                        SELECT nifty_spot, timestamp
                        FROM predictions
                        WHERE DATE(timestamp) = ? AND nifty_spot > 0
                        ORDER BY timestamp ASC
                        """,
                        (today,),
                    )
                    rows = cur.fetchall()
                    if rows:
                        nifty_open = float(rows[0]["nifty_spot"])
                        nifty_close = float(rows[-1]["nifty_spot"])
                        if nifty_open > 0:
                            nifty_move_pct = (nifty_close - nifty_open) / nifty_open * 100
                except sqlite3.OperationalError as e:
                    logger.debug("daily_summary: nifty snapshot skipped: %s", e)

                now_iso = datetime.now(IST).isoformat()
                cur.execute(
                    """
                    INSERT INTO daily_summaries (
                        date_ist, is_trading_day,
                        nifty_open, nifty_close, nifty_move_pct, actual_direction,
                        predictions_count, majority_direction, avg_conviction,
                        trades_opened, trades_closed, wins, losses, win_rate,
                        gross_pnl, net_pnl, top_agent, notes, generated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(date_ist) DO UPDATE SET
                        is_trading_day=excluded.is_trading_day,
                        nifty_open=excluded.nifty_open,
                        nifty_close=excluded.nifty_close,
                        nifty_move_pct=excluded.nifty_move_pct,
                        actual_direction=excluded.actual_direction,
                        predictions_count=excluded.predictions_count,
                        majority_direction=excluded.majority_direction,
                        avg_conviction=excluded.avg_conviction,
                        trades_opened=excluded.trades_opened,
                        trades_closed=excluded.trades_closed,
                        wins=excluded.wins,
                        losses=excluded.losses,
                        win_rate=excluded.win_rate,
                        gross_pnl=excluded.gross_pnl,
                        net_pnl=excluded.net_pnl,
                        top_agent=excluded.top_agent,
                        notes=excluded.notes,
                        generated_at=excluded.generated_at
                    """,
                    (
                        today, 1 if _is_trading_day() else 0,
                        nifty_open, nifty_close, nifty_move_pct, actual_direction,
                        predictions_count, majority_direction, avg_conviction,
                        trades_opened, trades_closed, wins, losses, win_rate,
                        gross_pnl, net_pnl, top_agent, None, now_iso,
                    ),
                )
                conn.commit()

                return {
                    "date_ist": today,
                    "nifty_open": nifty_open,
                    "nifty_close": nifty_close,
                    "nifty_move_pct": nifty_move_pct,
                    "actual_direction": actual_direction,
                    "predictions_count": predictions_count,
                    "majority_direction": majority_direction,
                    "avg_conviction": avg_conviction,
                    "trades_opened": trades_opened,
                    "trades_closed": trades_closed,
                    "wins": wins,
                    "losses": losses,
                    "win_rate": win_rate,
                    "gross_pnl": gross_pnl,
                    "net_pnl": net_pnl,
                    "top_agent": top_agent,
                }
            finally:
                conn.close()

        result = await asyncio.to_thread(_compute)
        logger.info(
            "Daily summary [%s]: trades=%d/%d wins=%d pnl=₹%.0f net predictions=%d majority=%s",
            result["date_ist"],
            result["trades_opened"],
            result["trades_closed"],
            result["wins"],
            result["net_pnl"],
            result["predictions_count"],
            result["majority_direction"],
        )
        return result

    # ── Backup ────────────────────────────────────────────────────────────

    async def _run_backup(self) -> None:
        """Snapshot SQLite + skills to the Railway volume, prune old copies.

        Uses ``sqlite3.Connection.backup()`` (the online-backup API) instead
        of copying the DB file, so a backup taken mid-write still yields a
        consistent snapshot without blocking the live connection.

        The snapshot is offloaded to a worker thread via asyncio.to_thread
        so the scheduler loop's 30-second poll cadence is preserved.
        """
        def _snapshot() -> Dict[str, Any]:
            # Use IST to match the scheduler's notion of "today" — otherwise
            # a backup kicked off at 23:30 IST from a UTC container could
            # land on the wrong date near the day boundary.
            stamp = _get_ist_now().strftime("%Y-%m-%d")
            backup_dir = Path(BACKUP_DIR)
            backup_dir.mkdir(parents=True, exist_ok=True)

            # 1. SQLite snapshot via online backup API (consistent under load).
            db_dest = backup_dir / f"gods_eye_{stamp}.db"
            db_src_path = getattr(config, "DATABASE_PATH", None) or os.getenv(
                "GODS_EYE_DB_PATH", "/app/data/gods_eye.db"
            )
            db_copied = False
            if os.path.exists(db_src_path):
                # Clean up any stale dest + sidecar files from a prior same-day
                # run so we don't append/merge onto a half-written snapshot.
                for ext in ("", "-shm", "-wal", "-journal"):
                    p = Path(str(db_dest) + ext)
                    if p.exists():
                        try:
                            p.unlink()
                        except OSError:
                            pass

                # Force DELETE journal mode on the destination so SQLite does
                # not leave .db-shm / .db-wal artifacts next to the snapshot.
                # Explicit close() (not relying on context-manager exit, which
                # only commits) ensures the WAL is checkpointed + files freed.
                src = sqlite3.connect(db_src_path)
                dst = sqlite3.connect(str(db_dest))
                try:
                    dst.execute("PRAGMA journal_mode=DELETE")
                    src.backup(dst)
                finally:
                    dst.close()
                    src.close()
                db_copied = True
            else:
                logger.warning("Backup: DB not found at %s — skipping", db_src_path)

            # 2. Skills tarball (learned patterns — not regeneratable).
            skills_dest = backup_dir / f"skills_{stamp}.tar.gz"
            skills_copied = False
            if os.path.isdir(SKILLS_DIR):
                with tarfile.open(str(skills_dest), mode="w:gz") as tar:
                    tar.add(SKILLS_DIR, arcname=os.path.basename(SKILLS_DIR))
                skills_copied = True
            else:
                logger.info("Backup: skills dir %s absent — skipping", SKILLS_DIR)

            # 3. Prune anything older than BACKUP_RETENTION_DAYS.
            # Match only our own snapshot filenames so an operator who drops
            # an unrelated file into the backup dir doesn't lose it silently.
            # Includes .db-shm / .db-wal / -journal siblings for safety, even
            # though journal_mode=DELETE should prevent them being created.
            import time as _time
            cutoff = _time.time() - (BACKUP_RETENTION_DAYS * 86400)
            pruned = 0
            for f in backup_dir.iterdir():
                if not f.is_file():
                    continue
                name = f.name
                is_snapshot = (
                    (name.startswith("gods_eye_") and (
                        name.endswith(".db") or name.endswith(".db-shm")
                        or name.endswith(".db-wal") or name.endswith(".db-journal")
                    ))
                    or (name.startswith("skills_") and name.endswith(".tar.gz"))
                )
                if not is_snapshot:
                    continue
                try:
                    if f.stat().st_mtime < cutoff:
                        f.unlink()
                        pruned += 1
                except OSError as e:
                    logger.warning("Backup prune failed for %s: %s", f, e)

            return {
                "stamp": stamp,
                "db": db_copied,
                "skills": skills_copied,
                "pruned": pruned,
                "dir": str(backup_dir),
            }

        result = await asyncio.to_thread(_snapshot)
        logger.info(
            "Backup done: db=%s skills=%s pruned=%d dir=%s",
            result["db"], result["skills"], result["pruned"], result["dir"],
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _next_scheduled_time(self, current_time: time) -> Optional[time]:
        """Return the next scheduled run time after current_time, or None if done for day."""
        for t in ALL_RUN_TIMES:
            if t > current_time:
                return t        # Check outcome time
        if not self._outcome_recorded_today and OUTCOME_RECORD_TIME > current_time:
            return OUTCOME_RECORD_TIME
        return None


# Global singleton (mirrors PCRCollector pattern)
simulation_scheduler = SimulationScheduler()