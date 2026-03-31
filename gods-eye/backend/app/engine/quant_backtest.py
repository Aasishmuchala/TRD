"""Rules-only backtest loop. Reads OHLCV + VIX from SQLite once,
iterates all trading days without further I/O.
Zero LLM calls. Zero agent calls.
Performance target: 250 trading days in under 10 seconds.
"""

import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

from app.data.historical_store import historical_store
from app.data.technical_signals import TechnicalSignals
from app.engine.quant_signal_engine import QuantInputs, QuantSignalEngine


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class QuantBacktestDayResult:
    """Per-day result from the quant-only backtest loop."""

    date: str
    direction: str
    total_score: int
    tier: str
    buy_points: int
    sell_points: int
    factors: Dict
    actual_move_pct: Optional[float]
    is_correct: Optional[bool]
    pnl_points: float


@dataclass
class QuantBacktestRunResult:
    """Aggregate result for a completed QuantBacktestEngine run."""

    instrument: str
    from_date: str
    to_date: str
    days: List[QuantBacktestDayResult]
    total_days: int
    tradeable_days: int
    correct_days: int
    win_rate_pct: Optional[float]
    total_pnl_points: float
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class QuantBacktestEngine:
    """Runs a rules-only backtest over a date range using only SQLite data.

    No network calls inside the loop. Fetches all OHLCV + VIX data once
    (without date filter so RSI/Supertrend lookback has full history before
    from_date), then iterates trading days in a single synchronous Python loop.
    """

    async def run_quant_backtest(
        self,
        instrument: str,
        from_date: str,
        to_date: str,
    ) -> QuantBacktestRunResult:
        """Run quant backtest over [from_date, to_date] inclusive.

        Parameters
        ----------
        instrument:
            "NIFTY" or "BANKNIFTY"
        from_date:
            Start date "YYYY-MM-DD" (inclusive).
        to_date:
            End date "YYYY-MM-DD" (inclusive).

        Returns
        -------
        QuantBacktestRunResult with per-day breakdown and aggregate metrics.
        """
        t0 = time.time()

        # Fetch all rows without date filter so indicator lookback
        # (RSI-14, Supertrend-10) has enough history before from_date.
        all_rows = await historical_store.get_ohlcv(instrument)
        all_vix = await historical_store.get_vix_closes()

        # Build O(1) lookups
        row_by_date = {r["date"]: r for r in all_rows}
        vix_by_date = {v["date"]: v["close"] for v in all_vix}
        all_dates = sorted(row_by_date.keys())

        # VIX dates list for 5-day average computation (sorted ASC)
        vix_dates = [v["date"] for v in all_vix]

        # Trading days within the requested range
        date_range = [d for d in all_dates if from_date <= d <= to_date]

        results: List[QuantBacktestDayResult] = []

        for i, date in enumerate(date_range):
            # All closes and rows up to (and including) current date — no future leakage
            closes_up_to = [r["close"] for r in all_rows if r["date"] <= date]
            rows_up_to = [r for r in all_rows if r["date"] <= date]

            rsi = TechnicalSignals.compute_rsi(closes_up_to)
            supertrend = TechnicalSignals.compute_supertrend(rows_up_to)

            # VIX: use actual historical value or default to 18.0 if missing
            vix = vix_by_date.get(date, 18.0)

            # 5-day VIX average from previous closes (not including current day)
            prev_vix = [vix_by_date[d] for d in vix_dates if d < date]
            vix_5d_avg = float(sum(prev_vix[-5:]) / len(prev_vix[-5:])) if prev_vix else vix

            # 5-day momentum proxy (requires at least 6 closes)
            momentum_5d = (
                (closes_up_to[-1] / closes_up_to[-6] - 1.0) * 100
                if len(closes_up_to) >= 6
                else 0.0
            )

            inputs = QuantInputs(
                fii_net_cr=momentum_5d * 1500,
                dii_net_cr=-momentum_5d * 800,
                pcr=0.6 + (rsi / 100) * 0.8,
                rsi=rsi,
                vix=vix,
                vix_5d_avg=vix_5d_avg,
                supertrend=supertrend,
            )
            sr = QuantSignalEngine.compute_quant_score(inputs, instrument)

            # Next-day actual move — None for the last day in the range
            actual_move_pct: Optional[float] = None
            if i + 1 < len(date_range):
                next_date = date_range[i + 1]
                next_close = row_by_date[next_date]["close"]
                today_close = closes_up_to[-1]
                actual_move_pct = (next_close / today_close - 1.0) * 100

            # Correctness and P&L
            is_correct: Optional[bool] = None
            pnl_points = 0.0
            if sr.direction != "HOLD" and actual_move_pct is not None:
                if sr.direction == "BUY":
                    is_correct = actual_move_pct > 0
                else:
                    is_correct = actual_move_pct < 0
                pnl_points = 50.0 if is_correct else -30.0

            results.append(
                QuantBacktestDayResult(
                    date=date,
                    direction=sr.direction,
                    total_score=sr.total_score,
                    tier=sr.tier,
                    buy_points=sr.buy_points,
                    sell_points=sr.sell_points,
                    factors=sr.factors,
                    actual_move_pct=actual_move_pct,
                    is_correct=is_correct,
                    pnl_points=pnl_points,
                )
            )

        # Aggregate metrics
        tradeable = [
            r for r in results
            if r.direction != "HOLD" and r.actual_move_pct is not None
        ]
        correct = [r for r in tradeable if r.is_correct]

        return QuantBacktestRunResult(
            instrument=instrument,
            from_date=from_date,
            to_date=to_date,
            days=results,
            total_days=len(results),
            tradeable_days=len(tradeable),
            correct_days=len(correct),
            win_rate_pct=(len(correct) / len(tradeable) * 100) if tradeable else None,
            total_pnl_points=sum(r.pnl_points for r in results),
            elapsed_seconds=time.time() - t0,
        )


# Module-level singleton — mirrors the pattern in historical_store.py
quant_backtest_engine = QuantBacktestEngine()
