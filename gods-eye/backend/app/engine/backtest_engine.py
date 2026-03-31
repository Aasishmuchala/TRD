"""Backtest engine — replays historical days through the 3-round agent simulation.

This module provides:
  BacktestDayResult  — per-day replay result with direction, P&L, accuracy
  BacktestRunResult  — aggregated run statistics across a date range
  BacktestEngine     — orchestrates the replay loop and persists results to SQLite
"""

import asyncio
import json
import logging
import os
import sqlite3
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple

from app.api.schemas import MarketInput
from app.config import config
from app.data.historical_store import historical_store
from app.data.technical_signals import TechnicalSignals
from app.engine.orchestrator import Orchestrator
from app.engine.signal_scorer import SignalScorer

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


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class BacktestEngine:
    """Replay engine: iterate historical days, run 3-round simulation per day.

    Usage:
        engine = BacktestEngine()
        result = await engine.run_backtest("NIFTY", "2024-01-01", "2024-02-01", mock_mode=True)
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
        mock_mode: bool = True,
    ) -> BacktestRunResult:
        """Run a full backtest over a date range.

        Args:
            instrument:  "NIFTY" or "BANKNIFTY"
            from_date:   start date "YYYY-MM-DD" (inclusive); defaults to 30 days ago
            to_date:     end date "YYYY-MM-DD" (inclusive); defaults to yesterday
            mock_mode:   if True, agents use MockResponseGenerator (no LLM API calls)

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
            "Starting backtest: instrument=%s from=%s to=%s mock=%s",
            instrument, from_date, to_date, mock_mode,
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

        # Save and override config for backtest (restored in finally)
        original_mock = config.MOCK_MODE
        original_model = config.MODEL
        original_samples = config.SAMPLES_PER_AGENT
        original_rounds = config.INTERACTION_ROUNDS
        config.MOCK_MODE = mock_mode
        if not mock_mode:
            # Use fast model + minimal samples for backtesting speed
            config.MODEL = os.getenv("GODS_EYE_BACKTEST_MODEL", "google/gemini-2.0-flash-001")
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

                # Compute actual move
                nifty_close = row["close"]
                actual_move_pct = (nifty_next_close - nifty_close) / nifty_close * 100

                # Build MarketInput from historical data (no future data leakage)
                market_input = self._build_market_input(row, vix_map, all_ohlcv)

                # Run all 6 agents in PARALLEL (single round, no interaction)
                # This is 6x faster than sequential orchestrator for backtesting
                try:
                    agent_tasks = {
                        name: agent.analyze(market_input, round_num=1)
                        for name, agent in self.orchestrator.agents.items()
                    }
                    results = await asyncio.gather(
                        *agent_tasks.values(), return_exceptions=True
                    )
                    final_outputs = {}
                    for name, result in zip(agent_tasks.keys(), results):
                        if not isinstance(result, Exception):
                            final_outputs[name] = result
                        else:
                            logger.warning("Agent %s failed for %s: %s", name, signal_date, result)
                except Exception as exc:
                    logger.error("Simulation failed for %s: %s", signal_date, exc)
                    continue

                round_history = []

                # Compute consensus direction + conviction
                predicted_direction, predicted_conviction = self._compute_consensus(final_outputs)

                # Per-agent directions from final outputs
                per_agent_directions = {
                    name: resp.direction
                    for name, resp in final_outputs.items()
                }

                # Correctness and P&L
                direction_correct = self._is_correct(predicted_direction, actual_move_pct)
                pnl_points = self._compute_pnl(predicted_direction, actual_move_pct, nifty_close)

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
                )
                days.append(day_result)
                logger.debug(
                    "Day %s: predicted=%s actual_move=%.2f%% correct=%s pnl=%.1f",
                    signal_date, predicted_direction, actual_move_pct,
                    direction_correct, pnl_points,
                )

        finally:
            config.MOCK_MODE = original_mock
            config.MODEL = original_model
            config.SAMPLES_PER_AGENT = original_samples
            config.INTERACTION_ROUNDS = original_rounds

        # Aggregate statistics
        eligible = [d for d in days if d.direction_correct is not None]
        correct = [d for d in eligible if d.direction_correct]
        overall_accuracy = len(correct) / len(eligible) if eligible else 0.0
        total_pnl_points = sum(d.pnl_points for d in days)
        per_agent_accuracy = self._compute_per_agent_accuracy(days)

        run_result = BacktestRunResult(
            run_id=str(uuid.uuid4()),
            instrument=instrument,
            from_date=from_date,
            to_date=to_date,
            mock_mode=mock_mode,
            days=days,
            overall_accuracy=round(overall_accuracy, 4),
            per_agent_accuracy=per_agent_accuracy,
            total_pnl_points=round(total_pnl_points, 2),
            created_at=datetime.utcnow().isoformat(),
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

        # Simulate FII/DII from momentum: falling market → FII selling, DII buying
        fii_flow_proxy = momentum_5d_pct * 1500  # -2% move → -3000 Cr outflow
        dii_flow_proxy = -momentum_5d_pct * 800   # DII absorbs opposite

        # PCR from RSI: oversold → high PCR (put heavy), overbought → low PCR
        rsi_val = rsi_14 if rsi_14 is not None else 50
        pcr_proxy = 0.6 + (rsi_val / 100) * 0.8  # range 0.6-1.4

        # Context from momentum
        if momentum_5d_pct < -2:
            context = "correction"
        elif momentum_5d_pct < -1:
            context = "weakness"
        elif momentum_5d_pct > 2:
            context = "rally"
        elif momentum_5d_pct > 1:
            context = "strength"
        else:
            context = "normal"

        return MarketInput(
            nifty_spot=close_today,
            nifty_open=row["open"],
            nifty_high=row["high"],
            nifty_low=row["low"],
            nifty_close=close_today,
            india_vix=india_vix,
            fii_flow_5d=round(fii_flow_proxy, 0),
            dii_flow_5d=round(dii_flow_proxy, 0),
            usd_inr=84.0,
            dxy=103.0,
            pcr_index=round(pcr_proxy, 2),
            pcr_stock=1.0,
            max_pain=close_today,
            dte=15,
            rsi_14=rsi_14,
            context=context,
            macd_signal=None,
            historical_prices=historical_closes,
        )

    def _compute_consensus(
        self, final_outputs: Dict
    ) -> Tuple[str, float]:
        """Compute consensus by grouping BUY/SELL families.

        Groups: BUY family (STRONG_BUY, BUY), SELL family (SELL, STRONG_SELL), HOLD.
        The family with the most votes wins. Within that family, uses the strongest
        signal if conviction is high enough.

        Returns:
            (direction, conviction) tuple
        """
        if not final_outputs:
            return ("HOLD", 50.0)

        buy_family = {"STRONG_BUY", "BUY"}
        sell_family = {"SELL", "STRONG_SELL"}

        buy_votes = []
        sell_votes = []
        hold_votes = []

        for resp in final_outputs.values():
            d = resp.direction
            if d in buy_family:
                buy_votes.append(resp.conviction)
            elif d in sell_family:
                sell_votes.append(resp.conviction)
            else:
                hold_votes.append(resp.conviction)

        # Family with most votes wins. Ties: BUY/SELL beat HOLD (actionable > passive)
        families = [
            ("BUY", len(buy_votes), buy_votes),
            ("SELL", len(sell_votes), sell_votes),
            ("HOLD", len(hold_votes), hold_votes),
        ]
        families.sort(key=lambda f: (f[1], sum(f[2]) if f[2] else 0), reverse=True)
        winning_family = families[0][0]
        winning_convictions = families[0][2]

        # Pick specific direction based on avg conviction
        avg_conv = sum(winning_convictions) / len(winning_convictions) if winning_convictions else 50
        if winning_family == "BUY":
            winning_direction = "STRONG_BUY" if avg_conv > 70 else "BUY"
        elif winning_family == "SELL":
            winning_direction = "STRONG_SELL" if avg_conv > 70 else "SELL"
        else:
            winning_direction = "HOLD"

        # Conviction = already computed from winning family
        conviction = avg_conv

        return (winning_direction, conviction)

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
