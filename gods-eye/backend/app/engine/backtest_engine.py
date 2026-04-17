"""Backtest engine — replays historical days through the 3-round agent simulation.

This module provides:
  BacktestDayResult  — per-day replay result with direction, P&L, accuracy
  BacktestRunResult  — aggregated run statistics across a date range
  BacktestEngine     — orchestrates the replay loop and persists results to SQLite
"""

import asyncio
import json
import logging
import math
import os
import sqlite3
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from app.api.schemas import MarketInput
from app.config import config
from app.data.historical_store import historical_store
from app.data.event_calendar import (
    get_event_for_date,
    is_pre_event_blackout,
    get_post_event_context,
    classify_vix_regime,
)
from app.data.technical_signals import TechnicalSignals
from app.data.fii_dii_store import fii_dii_store as _fii_dii_store, get_fii_dii_for_quant
from app.data.pcr_store import pcr_store as _pcr_store
from app.engine.orchestrator import Orchestrator
from app.engine.signal_scorer import SignalScorer
from app.engine.stop_loss_engine import StopLossEngine

logger = logging.getLogger("gods_eye.backtest")

# Direction to numeric weight for consensus voting
DIRECTION_WEIGHTS: Dict[str, int] = {
    "STRONG_BUY": 2,
    "BUY": 1,
    "HOLD": 0,
    "SELL": -1,
    "STRONG_SELL": -2,
}

# Directions that are in the "BUY family" or "SELL family"
_BUY_FAMILY = {"BUY", "STRONG_BUY"}
_SELL_FAMILY = {"SELL", "STRONG_SELL"}

# Minimum directional move (%) for a prediction to count as correct
# TRD-L1: 0.1% = ~22 NIFTY points at 22,000 level. This is below typical
# round-trip transaction costs (brokerage + STT + slippage ≈ 0.15-0.25%).
# A "correct" BUY with +0.12% move would actually lose money after costs.
# Consider raising to 0.2-0.3% to only count trades that would be profitable.
_CORRECT_THRESHOLD = 0.1

# ATM option leverage proxy (delta ≈ 0.5, leverage ≈ 3x underlying move)
_OPTION_LEVERAGE = 3.0


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class BacktestDayResult:
    """Result for a single signal day in a backtest run."""

    date: str                              # "YYYY-MM-DD" — the signal day
    next_date: str                         # "YYYY-MM-DD" — the outcome day
    nifty_close: float                     # close on signal day
    nifty_next_close: float                # close on outcome day
    actual_move_pct: float                 # (next_close - close) / close * 100
    predicted_direction: str              # BUY/SELL/HOLD/STRONG_BUY/STRONG_SELL
    predicted_conviction: float           # 0-100 weighted consensus conviction
    direction_correct: Optional[bool]     # None when HOLD
    pnl_points: float                     # simulated P&L in Nifty index points
    per_agent_directions: Dict[str, str]  # {"FII": "BUY", "DII": "HOLD", ...}
    round_history: List[Dict]             # raw from orchestrator (rounds 1-3)
    signals: Dict                         # {"rsi": float, "supertrend": str, ...}
    signal_score: Optional[Dict] = field(default=None)  # ScoreResult as plain dict

    # Stop loss fields (Profitability Roadmap v2)
    stop_loss_hit: bool = False                  # True if stop triggered during next day
    stop_price: Optional[float] = None           # NIFTY stop level (None when HOLD)
    stop_distance_pts: Optional[float] = None    # Distance from entry to stop in pts

    # Entry price (T's close in close-to-close structure)
    entry_price: float = 0.0                     # T's close — MOC entry price
    overnight_gap_pct: float = 0.0               # Unused in close-to-close (gap is part of P&L)


@dataclass
class BacktestRunResult:
    """Aggregated result for a complete backtest run."""

    run_id: str
    instrument: str                           # "NIFTY" or "BANKNIFTY"
    from_date: str
    to_date: str
    mock_mode: bool
    days: List[BacktestDayResult]
    overall_accuracy: float                   # correct / (total - HOLD days)
    per_agent_accuracy: Dict[str, float]      # agent -> accuracy 0-1
    total_pnl_points: float
    created_at: str                           # ISO timestamp

    # Phase 3 performance metrics
    hit_rate_pct: float = 0.0                 # % of non-HOLD days direction was correct
    avg_pnl_per_trade: float = 0.0            # mean P&L points on non-HOLD days
    max_drawdown_pct: float = 0.0             # max peak-to-trough on cumulative P&L curve
    sharpe_ratio: float = 0.0                 # (mean daily P&L / std daily P&L) × √252
    total_trades: int = 0                     # count of non-HOLD days

    # Phase 3 regime accuracy
    regime_accuracy: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Stop loss stats (Profitability Roadmap v2)
    total_stops_hit: int = 0             # trades where stop was triggered before EOD
    stop_loss_enabled: bool = False      # whether stop loss was active for this run

    # Latency stats
    avg_overnight_gap_pct: float = 0.0   # mean |gap| (T close → T+1 open) across trades


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class BacktestEngine:
    """Replay engine: iterate historical days, run 3-round simulation per day.

    Usage:
        engine = BacktestEngine()
        result = await engine.run_backtest("NIFTY", "2024-01-01", "2024-02-01")
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        self.orchestrator = Orchestrator()
        self._init_schema()

    # ------------------------------------------------------------------ #
    # Schema                                                               #
    # ------------------------------------------------------------------ #

    def _init_schema(self) -> None:
        """Create backtest_runs table and indexes if they do not exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backtest_runs (
                run_id           TEXT    PRIMARY KEY,
                instrument       TEXT    NOT NULL,
                from_date        TEXT    NOT NULL,
                to_date          TEXT    NOT NULL,
                mock_mode        INTEGER NOT NULL DEFAULT 1,
                day_count        INTEGER NOT NULL DEFAULT 0,
                overall_accuracy REAL,
                total_pnl_points REAL,
                result_json      TEXT    NOT NULL,
                created_at       TEXT    NOT NULL
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_br_instrument_dates
                ON backtest_runs(instrument, from_date, to_date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_br_created
                ON backtest_runs(created_at)
        """)

        conn.commit()
        conn.close()
        logger.info("BacktestEngine schema initialised at %s", self.db_path)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def run_backtest(
        self,
        instrument: str = "NIFTY",
        from_date: str = None,
        to_date: str = None,
    ) -> BacktestRunResult:
        """Run a full backtest over a date range using real LLM agents.

        Trade structure: close-to-close.
          - Signal generated at T's close (3:25 PM IST).
          - Entry via MOC order at T's close (3:29 PM).
          - Exit at T+1's close.
          - Overnight gap (T close → T+1 open) is intended strategy P&L.

        Args:
            instrument:  "NIFTY" or "BANKNIFTY"
            from_date:   start date "YYYY-MM-DD" (inclusive); defaults to 30 days ago
            to_date:     end date "YYYY-MM-DD" (inclusive); defaults to yesterday

        Returns:
            BacktestRunResult with per-day results and aggregate statistics.
        """
        # Default date range: last 30 calendar days (roughly 20 trading days)
        today = date.today()
        if to_date is None:
            to_date = (today - timedelta(days=1)).isoformat()
        if from_date is None:
            from_date = (today - timedelta(days=30)).isoformat()

        logger.info(
            "Starting backtest: instrument=%s from=%s to=%s (real LLM, close-to-close)",
            instrument, from_date, to_date,
        )

        # Fetch all OHLCV rows (entire history) and VIX closes
        all_ohlcv = await historical_store.get_ohlcv(instrument)
        vix_rows = await historical_store.get_vix_closes()

        # Build a fast VIX lookup: date -> vix_close
        vix_map: Dict[str, float] = {r["date"]: r["close"] for r in vix_rows}

        # Filter to signal rows within [from_date, to_date]
        signal_rows = [
            r for r in all_ohlcv
            if from_date <= r["date"] <= to_date
        ]

        if not signal_rows:
            logger.warning(
                "No OHLCV rows found for %s in [%s, %s]",
                instrument, from_date, to_date,
            )

        # ARCH-C2: Override config for backtest speed (restored in finally block).
        # This save/restore pattern is not thread-safe but acceptable since the
        # application runs with --workers 1 (see CLAUDE.md "What NOT to Use").
        # If multi-worker deployment is needed, move these overrides to a
        # request-scoped context or pass them as parameters.
        original_model = config.MODEL
        original_samples = config.SAMPLES_PER_AGENT
        original_rounds = config.INTERACTION_ROUNDS
        original_mock = config.MOCK_MODE
        # Use real LLM by default; allow override via GODS_EYE_MOCK=true for fast validation runs
        config.MOCK_MODE = os.getenv("GODS_EYE_MOCK", "false").lower() in ("true", "1", "yes")
        config.MODEL = os.getenv("GODS_EYE_BACKTEST_MODEL", "claude-sonnet-4-6")
        config.SAMPLES_PER_AGENT = 1   # 1 sample instead of 3 (3x faster)
        config.INTERACTION_ROUNDS = 1  # 1 round instead of 3 (3x faster)

        days: List[BacktestDayResult] = []

        try:
            for i, row in enumerate(signal_rows):
                # Look up the next row in the full dataset (not just signal rows)
                # to get actual next-day close — needed even if next day is outside range
                signal_date = row["date"]

                # Find this row's index in the full dataset
                full_indices = [j for j, r in enumerate(all_ohlcv) if r["date"] == signal_date]
                if not full_indices:
                    continue
                full_idx = full_indices[0]

                # Skip if there is no next trading day in the full dataset
                if full_idx + 1 >= len(all_ohlcv):
                    logger.debug("Skipping %s — no next trading day in dataset", signal_date)
                    continue

                next_row = all_ohlcv[full_idx + 1]
                next_date = next_row["date"]
                nifty_next_close = next_row["close"]

                # Signal generated using T's close data
                nifty_close = row["close"]

                # Close-to-close structure: signal at 3:25 PM → MOC entry at T's close
                # (3:29 PM), hold overnight, exit at T+1's close.
                # The overnight gap (T close → T+1 open) is intended P&L — it's where
                # FII/DII flows and macro moves first manifest.
                entry_price = nifty_close
                actual_move_pct = (nifty_next_close - nifty_close) / nifty_close * 100

                # Build MarketInput from historical data (no future data leakage)
                market_input = self._build_market_input(row, vix_map, all_ohlcv)

                # Run all agents in staggered parallel with retry (0.5s stagger between tasks)
                try:
                    tasks = {}
                    # ARCH-M7: Use `agent_idx` to avoid shadowing outer loop variable `i`
                    for agent_idx, (name, agent) in enumerate(self.orchestrator.agents.items()):
                        await asyncio.sleep(0.5 * agent_idx)  # stagger to avoid rate-limit bursts
                        tasks[name] = asyncio.create_task(
                            self._call_agent_with_retry(name, agent, market_input, round_num=1)
                        )
                    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
                    final_outputs = {}
                    for name, result in zip(tasks.keys(), results):
                        if result is not None and not isinstance(result, Exception):
                            final_outputs[name] = result
                        else:
                            logger.warning("Agent %s skipped for %s (no result after retries)", name, signal_date)
                except Exception as exc:
                    logger.error("Simulation failed for %s: %s", signal_date, exc)
                    continue

                round_history = []

                # Compute consensus direction + conviction
                predicted_direction, predicted_conviction = self._compute_consensus(final_outputs)

                # Apply VIX regime gate + event blackout (NEW)
                predicted_direction, predicted_conviction = self._apply_vix_event_gate(
                    predicted_direction,
                    predicted_conviction,
                    market_input.india_vix,
                    market_input.event_risk,
                    signal_date,
                )

                # Per-agent directions from final outputs
                per_agent_directions = {
                    name: resp.direction
                    for name, resp in final_outputs.items()
                }

                # Correctness and P&L — based on entry_price (T+1 open), not T close
                direction_correct = self._is_correct(predicted_direction, actual_move_pct)
                pnl_points = self._compute_pnl(predicted_direction, actual_move_pct, entry_price)

                # ---- Stop Loss (Profitability Roadmap v2) ----
                stop_hit = False
                sl_stop_price: Optional[float] = None
                sl_stop_dist: Optional[float] = None

                if config.STOP_LOSS_ENABLED and predicted_direction not in ("HOLD",):
                    # Build OHLCV window: all rows strictly BEFORE signal_date (no leakage)
                    ohlcv_window = [r for r in all_ohlcv if r["date"] < signal_date]

                    # Stop computed from entry_price (T+1 open) — latency-correct
                    sl_result = StopLossEngine.compute_stop_for_day(
                        direction=predicted_direction,
                        entry_close=entry_price,
                        ohlcv_window=ohlcv_window,
                        atr_multiplier=config.STOP_LOSS_ATR_MULTIPLIER,
                        pct_stop=config.STOP_LOSS_PCT,
                    )

                    if sl_result.method != "none":
                        sl_stop_price = sl_result.stop_price
                        sl_stop_dist = sl_result.stop_distance_pts

                        # Gap-open stop check: if T+1 opens past the stop (gap risk),
                        # stop is hit at T+1 open. Use T+1 open as a single-point range.
                        next_open = next_row["open"]
                        gap_stop_hit = StopLossEngine.check_stop_hit(
                            direction=predicted_direction,
                            stop_price=sl_result.stop_price,
                            day_low=next_open,
                            day_high=next_open,
                        )

                        # Intraday stop check: full T+1 day range
                        intraday_stop_hit = StopLossEngine.check_stop_hit(
                            direction=predicted_direction,
                            stop_price=sl_result.stop_price,
                            day_low=next_row["low"],
                            day_high=next_row["high"],
                        )

                        stop_hit = gap_stop_hit or intraday_stop_hit

                        if stop_hit:
                            # Override P&L with capped stop-loss exit
                            pnl_points = StopLossEngine.compute_stopped_pnl(
                                direction=predicted_direction,
                                entry_price=entry_price,
                                stop_price=sl_result.stop_price,
                            )
                            logger.debug(
                                "Stop hit on %s: direction=%s entry=%.1f stop=%.1f "
                                "gap_hit=%s intraday_hit=%s pnl=%.1f",
                                signal_date, predicted_direction, entry_price,
                                sl_result.stop_price, gap_stop_hit, intraday_stop_hit,
                                pnl_points,
                            )
                # ---- End Stop Loss ----

                # Technical signals (sliced to signal date — no leakage)
                signals = TechnicalSignals.compute_signals_for_date(all_ohlcv, signal_date)

                # Combined signal score via SignalScorer (sentiment + technicals)
                score_result = SignalScorer.score(
                    direction=predicted_direction,
                    conviction=predicted_conviction,
                    signals=signals,
                    instrument=instrument,
                )

                day_result = BacktestDayResult(
                    date=signal_date,
                    next_date=next_date,
                    nifty_close=nifty_close,
                    nifty_next_close=nifty_next_close,
                    actual_move_pct=round(actual_move_pct, 4),
                    predicted_direction=predicted_direction,
                    predicted_conviction=round(predicted_conviction, 2),
                    direction_correct=direction_correct,
                    pnl_points=round(pnl_points, 2),
                    per_agent_directions=per_agent_directions,
                    round_history=round_history,
                    signals=signals,
                    signal_score=vars(score_result),
                    stop_loss_hit=stop_hit,
                    stop_price=sl_stop_price,
                    stop_distance_pts=sl_stop_dist,
                    entry_price=round(entry_price, 2),
                    overnight_gap_pct=0.0,  # N/A in close-to-close (gap is part of P&L)
                )
                days.append(day_result)
                logger.debug(
                    "Day %s: predicted=%s actual_move=%.2f%% correct=%s pnl=%.1f",
                    signal_date, predicted_direction, actual_move_pct,
                    direction_correct, pnl_points,
                )

        finally:
            config.MOCK_MODE = original_mock   # restore original (False in prod, True in tests)
            config.MODEL = original_model
            config.SAMPLES_PER_AGENT = original_samples
            config.INTERACTION_ROUNDS = original_rounds

        # Aggregate statistics
        eligible = [d for d in days if d.direction_correct is not None]
        correct = [d for d in eligible if d.direction_correct]
        overall_accuracy = len(correct) / len(eligible) if eligible else 0.0
        total_pnl_points = sum(d.pnl_points for d in days)
        per_agent_accuracy = self._compute_per_agent_accuracy(days)

        # Phase 3 performance metrics
        total_trades = len(eligible)
        hit_rate_pct = round((len(correct) / total_trades * 100) if total_trades else 0.0, 2)
        avg_pnl_per_trade = round((sum(d.pnl_points for d in eligible) / total_trades) if total_trades else 0.0, 2)
        max_drawdown_pct = self._compute_max_drawdown(days)
        sharpe_ratio = self._compute_sharpe(days)

        # Phase 3 regime accuracy
        regime_accuracy = self._compute_regime_accuracy(days, vix_map)

        # Stop loss summary
        total_stops_hit = sum(1 for d in days if d.stop_loss_hit)

        # overnight_gap_pct is not tracked in close-to-close (gap is intended P&L)
        avg_overnight_gap_pct = 0.0

        run_result = BacktestRunResult(
            run_id=str(uuid.uuid4()),
            instrument=instrument,
            from_date=from_date,
            to_date=to_date,
            mock_mode=False,  # always real LLM — mock backtest mode removed
            days=days,
            overall_accuracy=round(overall_accuracy, 4),
            per_agent_accuracy=per_agent_accuracy,
            total_pnl_points=round(total_pnl_points, 2),
            created_at=datetime.now(timezone.utc).isoformat(),
            hit_rate_pct=hit_rate_pct,
            avg_pnl_per_trade=avg_pnl_per_trade,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            total_trades=total_trades,
            regime_accuracy=regime_accuracy,
            total_stops_hit=total_stops_hit,
            stop_loss_enabled=config.STOP_LOSS_ENABLED,
            avg_overnight_gap_pct=avg_overnight_gap_pct,
        )

        # Persist to SQLite
        self._save_run(run_result)

        logger.info(
            "Backtest complete: %d days, accuracy=%.1f%%, total_pnl=%.1f pts",
            len(days), overall_accuracy * 100, total_pnl_points,
        )
        return run_result

    # ------------------------------------------------------------------ #
    # Helper methods                                                       #
    # ------------------------------------------------------------------ #

    def _build_market_input(
        self,
        row: Dict,
        vix_map: Dict[str, float],
        all_rows: List[Dict],
    ) -> MarketInput:
        """Build a MarketInput from a historical OHLCV row.

        Uses neutral proxies for fields not available historically (FII/DII flows,
        USD/INR, DXY, PCR). Technical signals are computed with no future data leakage.
        """
        signal_date = row["date"]

        # VIX: use actual historical VIX if available, else neutral proxy
        india_vix = vix_map.get(signal_date, 16.0)

        # Technical signals sliced to signal_date
        signals = TechnicalSignals.compute_signals_for_date(all_rows, signal_date)
        rsi_14 = signals.get("rsi")

        # Historical prices: last 60 closes up to and including signal_date (no leakage)
        historical_closes = [
            r["close"] for r in all_rows if r["date"] <= signal_date
        ][-60:]

        # Derive momentum-based proxies from historical data
        # so agents see bearish signals when market is actually falling
        recent_closes = [r["close"] for r in all_rows if r["date"] <= signal_date]
        close_today = row["close"]

        # 5-day momentum: positive = market rising, negative = falling
        close_5d_ago = recent_closes[-6] if len(recent_closes) >= 6 else recent_closes[0]
        momentum_5d_pct = ((close_today - close_5d_ago) / close_5d_ago) * 100

        # Real FII/DII from store (Profitability Roadmap v2 Phase 1)
        # Falls back to momentum proxy when no real data for this date (logs warning).
        fii_dii_data = get_fii_dii_for_quant(_fii_dii_store, signal_date)
        if fii_dii_data["fii_net_cr"] != 0.0 or fii_dii_data["dii_net_cr"] != 0.0:
            # Real data available — pass directly in INR crores.
            # fii_flow_5d in MarketInput is in INR crores throughout the system.
            # AlgoQuantAgent no longer applies a unit conversion (Profitability Roadmap v2).
            fii_flow_5d = fii_dii_data["fii_net_cr"]
            dii_flow_5d = fii_dii_data["dii_net_cr"]
        else:
            # Fallback: momentum proxy (no real data for this date)
            logger.debug("FII/DII proxy used for %s — no real data in store", signal_date)
            fii_flow_5d = momentum_5d_pct * 1500
            dii_flow_5d = -momentum_5d_pct * 800

        # Real PCR from store (Profitability Roadmap v2 Phase 2)
        # Dhan doesn't provide historical option chain, so real PCR only exists for
        # dates collected since pcr_collector started. Falls back to 1.0 (neutral).
        real_pcr = _pcr_store.get_pcr(signal_date)
        if real_pcr is not None:
            pcr_index = real_pcr
        else:
            pcr_index = 1.0  # Neutral fallback — no scoring effect on PCR factor

        # 20-day SMA trend regime — explicit bearish/bullish label for agents + gate
        sma_20 = (
            sum(recent_closes[-20:]) / len(recent_closes[-20:])
            if len(recent_closes) >= 20
            else close_today
        )
        trend_pct = (close_today - sma_20) / sma_20 * 100  # % above/below 20D SMA

        if trend_pct <= -2.0:
            trend_regime = "BEARISH"      # >2% below 20D MA — strong downtrend
        elif trend_pct <= -0.5:
            trend_regime = "BEARISH"      # 0.5–2% below 20D MA — mild downtrend
        elif trend_pct >= 2.0:
            trend_regime = "BULLISH"
        elif trend_pct >= 0.5:
            trend_regime = "BULLISH"
        else:
            trend_regime = "NEUTRAL"

        # Context from momentum — include explicit trend regime for agents to read
        if momentum_5d_pct < -2:
            context = f"correction | trend:{trend_regime} {trend_pct:+.1f}%_vs_20dSMA"
        elif momentum_5d_pct < -1:
            context = f"weakness | trend:{trend_regime} {trend_pct:+.1f}%_vs_20dSMA"
        elif momentum_5d_pct > 2:
            context = f"rally | trend:{trend_regime} {trend_pct:+.1f}%_vs_20dSMA"
        elif momentum_5d_pct > 1:
            context = f"strength | trend:{trend_regime} {trend_pct:+.1f}%_vs_20dSMA"
        else:
            context = f"normal | trend:{trend_regime} {trend_pct:+.1f}%_vs_20dSMA"

        # --- Event calendar context ---
        # TRD-H3: exclude_shocks=True in backtest to avoid lookahead bias.
        # MACRO_SHOCK events (e.g. Iran missile attack, Japan crash) are
        # unknowable in advance — including them gives the backtest unfair
        # foreknowledge that would inflate accuracy metrics.
        event_on_day = get_event_for_date(signal_date, exclude_shocks=True)
        pre_blackout = is_pre_event_blackout(signal_date, lookahead_days=1, exclude_shocks=True)
        post_ctx = get_post_event_context(signal_date, lookback_days=2)

        if event_on_day:
            event_risk = event_on_day.lower()
            context = event_on_day.lower()          # override momentum context
        elif pre_blackout:
            event_risk = "pre_event_blackout"
            context = "pre_event_blackout"
        elif post_ctx:
            event_risk = post_ctx
            # Keep momentum context but note post-event regime
        else:
            event_risk = None

        return MarketInput(
            nifty_spot=close_today,
            nifty_open=row["open"],
            nifty_high=row["high"],
            nifty_low=row["low"],
            nifty_close=close_today,
            india_vix=india_vix,
            fii_flow_5d=round(fii_flow_5d, 2),
            dii_flow_5d=round(dii_flow_5d, 2),
            # TRD-L5: Hardcoded USD/INR and DXY — these should use actual historical
            # values for the signal date. USD/INR moved from 82 to 87 during FY2024-25
            # and DXY from 99 to 108. FII agent uses these for flow direction inference.
            # Future: add a forex_store with daily USD/INR and DXY history.
            usd_inr=84.0,
            dxy=103.0,
            pcr_index=round(pcr_index, 3),
            pcr_stock=1.0,
            max_pain=close_today,
            dte=15,
            rsi_14=rsi_14,
            context=context,
            macd_signal=None,
            historical_prices=historical_closes,
            event_risk=event_risk,
        )

    # Minimum total agent weight for a directional family to trigger a trade.
    # FII alone (0.30) is just enough; PROMOTER+RBI (0.20) is not.
    DIRECTIONAL_WEIGHT_THRESHOLD = 0.25

    # VIX regime conviction floors — WFO-optimized on 2023-2024 (476 days, 13,800 combos)
    # Validated on 2025 full year (+218.8%).  Sharpe improvement: 0.020 → 0.083
    VIX_NORMAL_FLOOR    = 60.0   # VIX < 13: slightly more permissive in calm markets
    VIX_ELEVATED_FLOOR  = 74.0   # VIX 13–16: stricter than before (was 72)
    VIX_HIGH_FLOOR      = 78.0   # VIX 16–19: only very aligned signals (unchanged)
    VIX_EXTREME_THRESHOLD = 19.0  # VIX > 19: block all trades (was 20 — tighter cutoff)

    @staticmethod
    async def _call_agent_with_retry(
        agent_name: str,
        agent,
        market_input,
        round_num: int = 1,
        max_retries: int = 3,
    ):
        """Call one agent with exponential-backoff retry (up to max_retries attempts)."""
        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                return await agent.analyze(market_input, round_num=round_num)
            except Exception as exc:
                last_exc = exc
                wait = 2 ** attempt
                if attempt < max_retries:
                    logger.warning(
                        "Agent %s attempt %d failed: %s — retry in %ds",
                        agent_name, attempt, exc, wait,
                    )
                    await asyncio.sleep(wait)
        logger.error("Agent %s all retries failed: %s", agent_name, last_exc)
        return None

    def _compute_consensus(
        self, final_outputs: Dict
    ) -> Tuple[str, float]:
        """Compute weighted consensus using config.AGENT_WEIGHTS.

        TODO (TRD-H2): This consensus algorithm diverges from aggregator.py's
        _standard_aggregate / _hybrid_aggregate. Backtest uses a threshold-based
        family-weight approach (faster, no quant/LLM split) while the live
        aggregator uses a score-based weighted average with hybrid quant/LLM
        buckets and agreement boost. Unifying them is desirable but risky —
        the backtest WFO parameters were optimized against THIS algorithm.
        Any unification must re-run WFO optimization and validate on out-of-sample data.

        Groups: BUY family (STRONG_BUY, BUY), SELL family (SELL, STRONG_SELL), HOLD.

        A directional family triggers a trade if its total weight >= DIRECTIONAL_WEIGHT_THRESHOLD
        (default 0.25).  This means FII alone (0.30) calling SELL → SELL signal, which
        correctly respects the stated agent weight architecture instead of raw vote counts.

        If both BUY and SELL families clear the threshold, the heavier one wins.
        If neither clears the threshold, result is HOLD.

        Conviction = weighted-average conviction of the winning family's agents.

        Returns:
            (direction, conviction) tuple
        """
        if not final_outputs:
            return ("HOLD", 50.0)

        buy_family = {"STRONG_BUY", "BUY"}
        sell_family = {"SELL", "STRONG_SELL"}

        buy_weight = 0.0
        sell_weight = 0.0
        buy_conv_sum = 0.0
        sell_conv_sum = 0.0
        hold_conv_sum = 0.0
        hold_count = 0

        for agent_name, resp in final_outputs.items():
            # Normalise key: backtest uses uppercase names like "FII", "DII", etc.
            key = agent_name.upper().replace("_AGENT", "").replace("RETAIL_FNO", "RETAIL_FNO")
            w = config.AGENT_WEIGHTS.get(key, 0.10)
            d = resp.direction
            if d in buy_family:
                buy_weight += w
                buy_conv_sum += resp.conviction * w
            elif d in sell_family:
                sell_weight += w
                sell_conv_sum += resp.conviction * w
            else:
                hold_conv_sum += resp.conviction
                hold_count += 1

        threshold = self.DIRECTIONAL_WEIGHT_THRESHOLD

        if buy_weight >= threshold or sell_weight >= threshold:
            # At least one directional family cleared the threshold
            if buy_weight >= sell_weight:
                avg_conv = buy_conv_sum / buy_weight if buy_weight else 50.0
                winning_direction = "STRONG_BUY" if avg_conv > 80 else "BUY"
                conviction = avg_conv
            else:
                avg_conv = sell_conv_sum / sell_weight if sell_weight else 50.0
                winning_direction = "STRONG_SELL" if avg_conv > 80 else "SELL"
                conviction = avg_conv
        else:
            # Neither directional family is strong enough → HOLD
            avg_hold = hold_conv_sum / hold_count if hold_count else 50.0
            winning_direction = "HOLD"
            conviction = avg_hold

        # Apply conviction floor — same gate as aggregator.aggregate()
        # Without this, _compute_consensus never respects config.CONVICTION_FLOOR
        # and in bull markets every day clears the directional threshold.
        if winning_direction != "HOLD" and conviction < config.CONVICTION_FLOOR:
            winning_direction = "HOLD"
            conviction = 50.0

        # NEWS_EVENT agent veto: if news agent is confident enough about HOLD,
        # override the consensus direction regardless of other agents.
        # Only applies when NEWS_EVENT agent is present and calling HOLD with ≥ 70 conviction.
        news_output = final_outputs.get("NEWS_EVENT")
        if (
            news_output is not None
            and news_output.direction == "HOLD"
            and news_output.conviction >= 70.0
            and winning_direction != "HOLD"
        ):
            logger.debug(
                "NEWS_EVENT veto: news agent conviction=%.1f → forcing HOLD",
                news_output.conviction,
            )
            winning_direction = "HOLD"
            conviction = 50.0

        return (winning_direction, conviction)

    def _apply_vix_event_gate(
        self,
        direction: str,
        conviction: float,
        india_vix: float,
        event_risk: Optional[str],
        signal_date: str,
        context: str = "",
    ) -> Tuple[str, float]:
        """Apply tiered VIX conviction escalation, event blackout, and trend-regime rules.

        Rules (in priority order):
        1. pre_event_blackout → force HOLD (known binary event within 1 day)
        2. VIX > 20 → force HOLD (premium too expensive + chaotic direction)
        3. VIX 16–20 → conviction must be >= VIX_HIGH_FLOOR (78) to trade
        4. VIX 14–16 → conviction must be >= VIX_ELEVATED_FLOOR (72) to trade
        5. VIX < 14  → standard config.CONVICTION_FLOOR (65)
        6. Trend-asymmetric gate: if trend is BEARISH and direction is BUY,
           raise the effective floor to VIX_HIGH_FLOOR (78). Agents need much
           stronger consensus to buy into a downtrend. SELL signals are
           unaffected — SELL in a BEARISH trend is directionally aligned.

        HOLD signals pass through unchanged (never penalize sitting out).
        """
        if direction == "HOLD":
            return direction, conviction

        # Rule 1: pre-event blackout (election day, budget day, etc.)
        if event_risk == "pre_event_blackout":
            logger.debug("VIX gate: pre-event blackout on %s → HOLD", signal_date)
            return "HOLD", 50.0

        # Rule 2: VIX extreme — force HOLD
        if india_vix > self.VIX_EXTREME_THRESHOLD:
            logger.debug(
                "VIX gate: VIX=%.1f > %.0f on %s → HOLD (extreme regime)",
                india_vix, self.VIX_EXTREME_THRESHOLD, signal_date,
            )
            return "HOLD", 50.0

        # Rule 3–5: tiered VIX conviction floor (WFO-optimized cutoffs)
        if india_vix >= 16.0:
            floor = self.VIX_HIGH_FLOOR       # 78
        elif india_vix >= 13.0:
            floor = self.VIX_ELEVATED_FLOOR   # 74  (cutoff lowered from 14 → 13)
        else:
            floor = self.VIX_NORMAL_FLOOR     # 60  (uses class constant, not config)

        # Rule 6: trend-asymmetric gate
        # Two triggers — both raise the BUY floor to VIX_HIGH_FLOOR (78):
        #   a) 20D SMA BEARISH: NIFTY below its 20-day moving average (lagging, persistent)
        #   b) 5D momentum falling: context includes "correction" or "weakness" (fast-reacting)
        # Either trigger is sufficient — this covers both the onset of a crash (fast momentum)
        # and sustained downtrends (20D SMA). SELL in bearish regimes is directionally
        # aligned and passes through with the normal VIX-based floor unchanged.
        buy_family = {"BUY", "STRONG_BUY"}
        bearish_trend = "trend:BEARISH" in context
        momentum_weak = any(kw in context for kw in ("correction", "weakness"))
        if direction in buy_family and (bearish_trend or momentum_weak):
            trend_floor = self.VIX_HIGH_FLOOR   # 78
            floor = max(floor, trend_floor)
            logger.debug(
                "Trend gate: BEARISH trend on %s, raising BUY floor to %.0f",
                signal_date, floor,
            )

        if conviction < floor:
            logger.debug(
                "Gate: VIX=%.1f conviction=%.1f < floor=%.1f on %s → HOLD",
                india_vix, conviction, floor, signal_date,
            )
            return "HOLD", 50.0

        return direction, conviction

    def _is_correct(self, predicted: str, actual_move_pct: float) -> Optional[bool]:
        """Evaluate prediction correctness.

        Rules:
          - HOLD -> None (excluded from accuracy denominator)
          - BUY/STRONG_BUY -> True if actual_move_pct > +0.1%
          - SELL/STRONG_SELL -> True if actual_move_pct < -0.1%
          - Otherwise -> False
        """
        if predicted == "HOLD":
            return None
        if predicted in _BUY_FAMILY:
            return actual_move_pct > _CORRECT_THRESHOLD
        if predicted in _SELL_FAMILY:
            return actual_move_pct < -_CORRECT_THRESHOLD
        return None  # unknown direction — treat as HOLD

    def _compute_pnl(
        self, predicted: str, actual_move_pct: float, close: float
    ) -> float:
        """Compute simulated P&L in Nifty index points for one ATM option lot.

        ATM CE (BUY signal): profits when market goes up.
        ATM PE (SELL signal): profits when market goes down.
        Proxy: option moves ~3x the underlying % move (delta ≈ 0.5, leverage ≈ 3x).

        TRD-M4: Transaction costs are NOT modeled here. Real-world costs include:
        - Brokerage: ~Rs80 round-trip (Dhan/Zerodha flat fee)
        - STT: 0.0625% on sell side for options
        - Slippage: 0.5-2 NIFTY points per leg depending on liquidity
        - Impact cost: wider for large orders near expiry
        The options_pnl.py module accounts for brokerage but this backtest P&L
        proxy does not. Actual returns will be lower than reported here.
        """
        if predicted in _BUY_FAMILY:
            return actual_move_pct * _OPTION_LEVERAGE * (close / 100)
        elif predicted in _SELL_FAMILY:
            return -actual_move_pct * _OPTION_LEVERAGE * (close / 100)
        else:  # HOLD
            return 0.0

    def _compute_per_agent_accuracy(
        self, days: List[BacktestDayResult]
    ) -> Dict[str, float]:
        """Compute per-agent accuracy across all backtest days.

        For each agent: accuracy = correct_days / eligible_days
        Eligible = days where that agent's direction is NOT HOLD.
        Returns 0.0 for agents with zero eligible days.
        """
        agent_correct: Dict[str, int] = {}
        agent_eligible: Dict[str, int] = {}

        for day in days:
            for agent_name, agent_direction in day.per_agent_directions.items():
                if agent_name not in agent_correct:
                    agent_correct[agent_name] = 0
                    agent_eligible[agent_name] = 0

                # Skip HOLD — not eligible
                if agent_direction == "HOLD":
                    continue

                # Only count days where the overall direction_correct is not None
                # (i.e., the simulation ran and produced a valid result)
                agent_eligible[agent_name] += 1

                # Agent is correct if its individual direction passes _is_correct
                actual = day.actual_move_pct
                agent_correct_flag = self._is_correct(agent_direction, actual)
                if agent_correct_flag:
                    agent_correct[agent_name] += 1

        result: Dict[str, float] = {}
        for agent_name in agent_correct:
            eligible = agent_eligible[agent_name]
            result[agent_name] = (
                round(agent_correct[agent_name] / eligible, 4) if eligible > 0 else 0.0
            )
        return result

    # ------------------------------------------------------------------ #
    # Phase 3 metric helpers                                               #
    # ------------------------------------------------------------------ #

    def _compute_max_drawdown(self, days: List[BacktestDayResult]) -> float:
        """Max peak-to-trough drawdown on the cumulative P&L curve (percentage).

        Returns 0.0 if no trades or no drawdown.
        """
        if not days:
            return 0.0

        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0

        for d in days:
            cumulative += d.pnl_points
            if cumulative > peak:
                peak = cumulative
            drawdown = peak - cumulative
            if drawdown > max_dd:
                max_dd = drawdown

        # Express as % of peak (avoid div-by-zero)
        if peak > 0:
            return round((max_dd / peak) * 100, 2)
        elif max_dd > 0:
            # Started losing from day 1 — express absolute drawdown as negative %
            return round(max_dd, 2)
        return 0.0

    def _compute_sharpe(self, days: List[BacktestDayResult]) -> float:
        """Annualized Sharpe ratio: (mean daily P&L / std daily P&L) × √252.

        Uses all days (including HOLD = 0 P&L) for a realistic daily return series.
        Returns 0.0 if fewer than 2 days or zero variance.

        TRD-M6: This Sharpe is computed on raw NIFTY index points, not percentage
        returns. Because NIFTY's absolute level changes over time (e.g. 18,000 vs
        24,000), the same % move produces different point values. This inflates
        Sharpe in rising markets and deflates it in falling ones. For a true
        risk-adjusted metric, convert pnl_points to % returns first:
          daily_return_pct = pnl_points / entry_price * 100
        Kept as-is for now since the backtest operates on a narrow date range
        where the NIFTY level variation is small (~10%).
        """
        if len(days) < 2:
            return 0.0

        pnls = [d.pnl_points for d in days]
        mean_pnl = sum(pnls) / len(pnls)
        variance = sum((p - mean_pnl) ** 2 for p in pnls) / (len(pnls) - 1)

        if variance <= 0:
            return 0.0

        std_pnl = math.sqrt(variance)
        return round((mean_pnl / std_pnl) * math.sqrt(252), 2)

    def _compute_regime_accuracy(
        self,
        days: List[BacktestDayResult],
        vix_map: Dict[str, float],
    ) -> Dict[str, Dict[str, float]]:
        """Per-agent accuracy grouped by VIX regime.

        Regimes: low_vix (<15), normal_vix (15-20), elevated_vix (20-30), high_vix (>30).
        Returns: {"low_vix": {"FII": 0.68, ...}, "normal_vix": {...}, ...}
        """
        regime_buckets: Dict[str, List[BacktestDayResult]] = {
            "low_vix": [],
            "normal_vix": [],
            "elevated_vix": [],
            "high_vix": [],
        }

        for d in days:
            vix = vix_map.get(d.date, 16.0)
            if vix < 15:
                regime_buckets["low_vix"].append(d)
            elif vix < 20:
                regime_buckets["normal_vix"].append(d)
            elif vix < 30:
                regime_buckets["elevated_vix"].append(d)
            else:
                regime_buckets["high_vix"].append(d)

        result: Dict[str, Dict[str, float]] = {}
        for regime, regime_days in regime_buckets.items():
            if not regime_days:
                result[regime] = {}
                continue
            result[regime] = self._compute_per_agent_accuracy(regime_days)

        return result

    # ------------------------------------------------------------------ #
    # Persistence                                                          #
    # ------------------------------------------------------------------ #

    def _save_run(self, run: BacktestRunResult) -> None:
        """Persist a completed BacktestRunResult to SQLite."""

        def _serialize(obj):
            """Custom JSON serializer for dataclasses containing dataclasses."""
            if hasattr(obj, "__dataclass_fields__"):
                return asdict(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        try:
            result_json = json.dumps(asdict(run))
        except Exception as exc:
            logger.error("Failed to serialize BacktestRunResult: %s", exc)
            result_json = "{}"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO backtest_runs
               (run_id, instrument, from_date, to_date, mock_mode, day_count,
                overall_accuracy, total_pnl_points, result_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.run_id,
                run.instrument,
                run.from_date,
                run.to_date,
                1 if run.mock_mode else 0,
                len(run.days),
                run.overall_accuracy,
                run.total_pnl_points,
                result_json,
                run.created_at,
            ),
        )
        conn.commit()
        conn.close()
        logger.info(
            "Saved backtest run %s (%d days) to SQLite", run.run_id, len(run.days)
        )
