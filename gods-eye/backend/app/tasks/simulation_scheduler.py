"""Automated Paper Trading Scheduler — runs simulations during market hours.

Runs hourly during IST market hours (pre-market 8:45 + every hour from 10:15-14:15)
and auto-records outcomes at 15:45 after market close.

Uses the same asyncio background-task pattern as PCRCollector for lifecycle management.
"""

import asyncio
import logging
import uuid
from datetime import datetime, time, timezone, timedelta
from typing import Optional, List, Dict, Any

from app.config import config
from app.api.schemas import MarketInput, SimulationResult, AggregatorResult
from app.engine.orchestrator import Orchestrator
from app.engine.aggregator import Aggregator
from app.data.market_data import market_data_service
from app.memory.prediction_tracker import PredictionTracker
from app.engine.paper_trader import paper_trader

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

# Paper trade EOD settlement: close all open positions at 15:25 IST (5 min before close)
EOD_SETTLEMENT_TIME = time(15, 25)

# Position monitoring window: check open trades every poll cycle during market hours
MARKET_OPEN_TIME = time(9, 15)
MARKET_CLOSE_TIME = time(15, 30)

# How close we need to be to a scheduled time to trigger (seconds)
SCHEDULE_TOLERANCE_SECONDS = 120  # 2-minute window

# Main loop poll interval
POLL_INTERVAL_SECONDS = 30

def _get_ist_now() -> datetime:
    """Get current time in IST."""
    return datetime.now(IST)


def _is_weekday() -> bool:
    """Return True if today is a weekday (Mon-Fri)."""
    return _get_ist_now().weekday() < 5


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
        self._tracker = PredictionTracker()
        self._last_status: str = "idle"
        self._total_runs: int = 0
        self._total_outcomes: int = 0

    # ── Public API ───────────────────────────────────────────────────────

    def start(self):
        """Start the scheduler background task."""
        if self._task is None or self._task.done():
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
        return {
            "enabled": self._enabled,
            "running": self._task is not None and not self._task.done(),
            "last_status": self._last_status,
            "total_runs_today": len(self._today_runs),
            "total_runs_all_time": self._total_runs,
            "total_outcomes_recorded": self._total_outcomes,
            "today_predictions": list(self._today_runs.values()),
            "outcome_recorded_today": self._outcome_recorded_today,
            "next_run": next_run.strftime("%H:%M") if next_run else None,            "current_time_ist": now.strftime("%H:%M:%S"),
            "is_weekday": _is_weekday(),
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
                    logger.info("Scheduler: new day %s — resetting daily state", today)
                if not self._enabled or not _is_weekday():
                    self._last_status = "waiting" if not _is_weekday() else "disabled"
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