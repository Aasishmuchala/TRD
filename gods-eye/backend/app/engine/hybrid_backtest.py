"""Hybrid backtest engine — runs quant + parallel agents + HybridScorer + LLMValidator + RiskManager for each day.

Performance target: 1 month (~22 trading days) in under 5 minutes.

Per-day pipeline:
  1. QuantSignalEngine.compute_quant_score()     — deterministic, zero I/O
  2. Orchestrator.run_simulation()               — 6 parallel LLM agent calls (Phase 11)
  3. HybridScorer.fuse()                         — placeholder pass for validator prompt build
  4. LLMValidator.call_validator()               — single validator LLM call (try/except fallback)
  5. HybridScorer.fuse()                         — final fuse with real verdict
  6. RiskManager.compute()                       — deterministic stop/target/lots
"""

import asyncio
import logging
import statistics
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from app.data.historical_store import historical_store
from app.data.technical_signals import TechnicalSignals
from app.engine.quant_signal_engine import QuantInputs, QuantSignalEngine
from app.engine.hybrid_scorer import HybridScorer, LLMValidator, ValidatorVerdict
from app.engine.risk_manager import RiskManager
from app.engine.orchestrator import Orchestrator
from app.api.schemas import MarketInput

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class HybridBacktestDayResult:
    """Per-day result from the hybrid backtest loop.

    Includes quant, agent, validator, and risk-adjusted P&L fields.
    """

    date: str
    direction: str              # from HybridResult (quant-locked)
    hybrid_score: float         # 0-100 fused score
    conviction: float           # post-validation
    tradeable: bool
    tier: str                   # "strong" | "moderate" | "skip"
    quant_score: int            # from quant_breakdown["score"]
    agent_consensus_score: float
    validator_verdict: str      # "confirm" | "adjust" | "skip"
    lots: int                   # from RiskManager (0 when tier==skip)
    actual_move_pct: Optional[float]
    is_correct: Optional[bool]  # None when HOLD or tier==skip
    pnl_points: float           # risk-adjusted (lots * move_pts * LOT_SIZE)


@dataclass
class HybridBacktestRunResult:
    """Aggregate result for a completed HybridBacktestEngine run."""

    instrument: str
    from_date: str
    to_date: str
    days: List[HybridBacktestDayResult]
    total_days: int
    tradeable_days: int
    correct_days: int
    win_rate_pct: Optional[float]
    total_pnl_points: float
    sharpe_ratio: Optional[float]
    max_drawdown_pct: Optional[float]
    win_loss_ratio: Optional[float]
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class HybridBacktestEngine:
    """Runs a hybrid backtest over a date range.

    Each day runs the full pipeline:
      quant score + 6 parallel agents + HybridScorer + LLMValidator + RiskManager.

    Orchestrator is instantiated once in __init__ to reuse connection pools.
    """

    NIFTY_LOT = 25

    def __init__(self) -> None:
        self._orchestrator = Orchestrator()

    async def run_hybrid_backtest(
        self,
        instrument: str,
        from_date: str,
        to_date: str,
    ) -> HybridBacktestRunResult:
        """Run hybrid backtest over [from_date, to_date] inclusive.

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
        HybridBacktestRunResult with per-day breakdown and aggregate risk metrics.
        """
        t0 = time.time()

        # ── Load all OHLCV + VIX once (no date filter — ensures RSI/Supertrend
        #    lookback has full history before from_date) ────────────────────────
        all_rows = await historical_store.get_ohlcv(instrument)
        all_vix = await historical_store.get_vix_closes()

        # O(1) lookups
        row_by_date = {r["date"]: r for r in all_rows}
        vix_by_date = {v["date"]: v["close"] for v in all_vix}
        all_dates = sorted(row_by_date.keys())

        # VIX dates list for 5-day average (sorted ASC)
        vix_dates = [v["date"] for v in all_vix]

        # Trading days within the requested range
        date_range = [d for d in all_dates if from_date <= d <= to_date]

        results: List[HybridBacktestDayResult] = []

        for i, date in enumerate(date_range):
            # ── All closes and rows up to (and including) current date — no future leakage
            closes_up_to = [r["close"] for r in all_rows if r["date"] <= date]
            rows_up_to = [r for r in all_rows if r["date"] <= date]

            # ── Technical indicators ────────────────────────────────────────
            rsi = TechnicalSignals.compute_rsi(closes_up_to)
            supertrend = TechnicalSignals.compute_supertrend(rows_up_to)

            # VIX: use actual historical value or default to 18.0 if missing
            vix = vix_by_date.get(date, 18.0)

            # 5-day VIX average from previous closes (strict d < date — no same-day leakage)
            prev_vix = [vix_by_date[d] for d in vix_dates if d < date]
            vix_5d_avg = float(sum(prev_vix[-5:]) / len(prev_vix[-5:])) if prev_vix else vix

            # 5-day momentum proxy (requires at least 6 closes)
            momentum_5d = (
                (closes_up_to[-1] / closes_up_to[-6] - 1.0) * 100
                if len(closes_up_to) >= 6
                else 0.0
            )

            # ── Build QuantInputs ───────────────────────────────────────────
            inputs = QuantInputs(
                fii_net_cr=momentum_5d * 1500,
                dii_net_cr=-momentum_5d * 800,
                pcr=0.6 + (rsi / 100) * 0.8,
                rsi=rsi,
                vix=vix,
                vix_5d_avg=vix_5d_avg,
                supertrend=supertrend,
            )

            # ── Quant score ─────────────────────────────────────────────────
            quant_result = QuantSignalEngine.compute_quant_score(inputs, instrument)

            # ── Build MarketInput for agents (same proxy formula as hybrid route) ─
            nifty_close = closes_up_to[-1]
            market_input = MarketInput(
                nifty_spot=nifty_close,
                india_vix=vix,
                fii_flow_5d=inputs.fii_net_cr / 1500 if inputs.fii_net_cr else 0.0,
                dii_flow_5d=inputs.dii_net_cr / 800 * -1 if inputs.dii_net_cr else 0.0,
                pcr_index=inputs.pcr,
                rsi_14=rsi,
            )

            # ── Dispatch 6 parallel agents via Orchestrator ─────────────────
            try:
                sim_result = await self._orchestrator.run_simulation(market_input)
                final_outputs = sim_result["final_outputs"]
            except Exception as exc:
                logger.warning("Agent simulation failed for %s on %s: %s", instrument, date, exc)
                final_outputs = {}

            # ── Placeholder fuse for LLMValidator prompt ────────────────────
            placeholder = ValidatorVerdict(
                verdict="confirm", reasoning="", adjustment_amount=0.0
            )
            pre_hybrid = HybridScorer.fuse(quant_result, final_outputs, placeholder)

            # ── LLM Validator call (try/except confirm-fallback) ─────────────
            try:
                verdict = await LLMValidator.call_validator(pre_hybrid, instrument, date)
            except Exception:
                verdict = ValidatorVerdict(
                    verdict="confirm",
                    reasoning="Validator unavailable.",
                    adjustment_amount=0.0,
                )

            # ── Final fuse with real verdict ────────────────────────────────
            hybrid = HybridScorer.fuse(quant_result, final_outputs, verdict)

            # ── Next-day actual move — None for the last day in the range ───
            actual_move_pct: Optional[float] = None
            if i + 1 < len(date_range):
                next_date = date_range[i + 1]
                next_close = row_by_date[next_date]["close"]
                actual_move_pct = (next_close / nifty_close - 1.0) * 100

            # ── Correctness ─────────────────────────────────────────────────
            is_correct: Optional[bool] = None
            if (
                hybrid.direction != "HOLD"
                and hybrid.tier != "skip"
                and actual_move_pct is not None
            ):
                if hybrid.direction == "BUY":
                    is_correct = actual_move_pct > 0
                elif hybrid.direction == "SELL":
                    is_correct = actual_move_pct < 0
                else:
                    is_correct = False

            # ── Risk-adjusted P&L ───────────────────────────────────────────
            pnl_points = 0.0
            lots = 0
            if hybrid.tradeable and hybrid.direction != "HOLD" and actual_move_pct is not None:
                vix_for_risk = vix if vix > 0 else 15.0
                rp = RiskManager.compute(hybrid.tier, hybrid.direction, nifty_close, vix_for_risk)
                lots = rp.lots
                actual_move_pts = (actual_move_pct / 100.0) * nifty_close
                if hybrid.direction == "BUY":
                    pnl_points = actual_move_pts * lots * self.NIFTY_LOT
                elif hybrid.direction == "SELL":
                    pnl_points = -actual_move_pts * lots * self.NIFTY_LOT

            results.append(
                HybridBacktestDayResult(
                    date=date,
                    direction=hybrid.direction,
                    hybrid_score=hybrid.hybrid_score,
                    conviction=hybrid.conviction,
                    tradeable=hybrid.tradeable,
                    tier=hybrid.tier,
                    quant_score=hybrid.quant_breakdown.get("score", 0),
                    agent_consensus_score=hybrid.agent_consensus_score,
                    validator_verdict=hybrid.validator_verdict,
                    lots=lots,
                    actual_move_pct=actual_move_pct,
                    is_correct=is_correct,
                    pnl_points=pnl_points,
                )
            )

        # ── Aggregate metrics ────────────────────────────────────────────────
        tradeable = [r for r in results if r.is_correct is not None]
        correct = [r for r in tradeable if r.is_correct]

        win_rate_pct = (len(correct) / len(tradeable) * 100) if tradeable else None

        total_pnl_points = sum(r.pnl_points for r in results)

        # Sharpe ratio — (mean / stdev) of per-day P&L over tradeable days
        sharpe_ratio: Optional[float] = None
        if len(tradeable) >= 2:
            pnl_vals = [r.pnl_points for r in tradeable]
            mean_pnl = statistics.mean(pnl_vals)
            stdev_pnl = statistics.stdev(pnl_vals)  # sample stdev (n-1)
            if stdev_pnl > 0:
                sharpe_ratio = round(mean_pnl / stdev_pnl, 4)

        # Max drawdown — peak-to-trough decline as % of peak cumulative P&L
        max_drawdown_pct: Optional[float] = None
        if results:
            cum_pnl = 0.0
            peak = 0.0
            max_dd = 0.0
            for r in results:
                cum_pnl += r.pnl_points
                if cum_pnl > peak:
                    peak = cum_pnl
                drawdown = peak - cum_pnl
                if drawdown > max_dd:
                    max_dd = drawdown
            max_drawdown_pct = round((max_dd / peak * 100) if peak > 0 else 0.0, 4)

        # Win/loss ratio — avg winning P&L / abs(avg losing P&L)
        win_loss_ratio: Optional[float] = None
        if tradeable:
            wins = [r.pnl_points for r in tradeable if r.pnl_points > 0]
            losses = [r.pnl_points for r in tradeable if r.pnl_points < 0]
            if wins and losses:
                avg_win = statistics.mean(wins)
                avg_loss = abs(statistics.mean(losses))
                win_loss_ratio = round(avg_win / avg_loss, 4) if avg_loss > 0 else None

        return HybridBacktestRunResult(
            instrument=instrument,
            from_date=from_date,
            to_date=to_date,
            days=results,
            total_days=len(results),
            tradeable_days=len(tradeable),
            correct_days=len(correct),
            win_rate_pct=win_rate_pct,
            total_pnl_points=total_pnl_points,
            sharpe_ratio=sharpe_ratio,
            max_drawdown_pct=max_drawdown_pct,
            win_loss_ratio=win_loss_ratio,
            elapsed_seconds=time.time() - t0,
        )


# Module-level singleton — mirrors the pattern in quant_backtest.py
hybrid_backtest_engine = HybridBacktestEngine()
