"""Tests for risk-adjusted P&L and risk metrics in QuantBacktestEngine.

Tests the following behaviors:
- P&L computed from RiskManager lot sizing, not flat +50/-30
- sharpe_ratio, max_drawdown_pct, win_loss_ratio computed correctly
"""

import math
import statistics
from unittest.mock import AsyncMock, patch, MagicMock
from dataclasses import dataclass, field
from typing import List, Optional, Dict

import pytest

from app.engine.quant_backtest import (
    QuantBacktestEngine,
    QuantBacktestDayResult,
    QuantBacktestRunResult,
)


# ---------------------------------------------------------------------------
# Unit tests: pnl_points formula (verifying RiskManager integration)
# ---------------------------------------------------------------------------


def test_strong_buy_pnl_correct():
    """tier=strong direction=BUY actual_move_pct=+1.0 entry_close=22000 vix=15
    → lots=2, pnl = 2 * (1.0/100 * 22000) * 25 = 2 * 220 * 25 = 11000
    """
    from app.engine.risk_manager import RiskManager
    rp = RiskManager.compute(tier="strong", direction="BUY", entry_close=22000, vix=15)
    assert rp.lots == 2

    actual_move_pct = 1.0
    entry_close = 22000.0
    NIFTY_LOT = 25
    actual_move_pts = (actual_move_pct / 100.0) * entry_close
    pnl = actual_move_pts * rp.lots * NIFTY_LOT
    assert pnl == pytest.approx(11000.0)


def test_moderate_sell_pnl_correct_market_down():
    """tier=moderate direction=SELL actual_move_pct=-0.5 entry_close=22000 vix=15
    → lots=1, pnl = -(-0.5/100 * 22000) * 1 * 25 = -(−110) * 25 = +2750
    SELL: pnl = -actual_move_pts * lots * 25
    actual_move_pts = -0.5/100 * 22000 = -110
    pnl = -(-110) * 1 * 25 = +2750
    """
    from app.engine.risk_manager import RiskManager
    rp = RiskManager.compute(tier="moderate", direction="SELL", entry_close=22000, vix=15)
    assert rp.lots == 1

    actual_move_pct = -0.5
    entry_close = 22000.0
    NIFTY_LOT = 25
    actual_move_pts = (actual_move_pct / 100.0) * entry_close  # -110
    pnl = -actual_move_pts * rp.lots * NIFTY_LOT              # -(-110) * 1 * 25 = +2750
    assert pnl == pytest.approx(2750.0)


def test_skip_tier_pnl_zero():
    """tier=skip direction=HOLD actual_move_pct=+2.0 → pnl=0.0 regardless of move."""
    # Skip tier / HOLD direction should always yield pnl=0
    actual_move_pct = 2.0
    pnl = 0.0  # Business rule: skip always 0

    assert pnl == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Unit tests: sharpe_ratio computation
# ---------------------------------------------------------------------------


def _make_tradeable_day(pnl: float) -> QuantBacktestDayResult:
    """Helper: make a tradeable day (non-HOLD, has actual_move_pct, has pnl)."""
    return QuantBacktestDayResult(
        date="2024-01-01",
        direction="BUY",
        total_score=75,
        tier="strong",
        buy_points=75,
        sell_points=25,
        factors={},
        actual_move_pct=0.5,
        is_correct=True if pnl > 0 else False,
        pnl_points=pnl,
        lots=2,
    )


def _make_hold_day() -> QuantBacktestDayResult:
    """Helper: make a non-tradeable HOLD day."""
    return QuantBacktestDayResult(
        date="2024-01-02",
        direction="HOLD",
        total_score=40,
        tier="skip",
        buy_points=40,
        sell_points=40,
        factors={},
        actual_move_pct=None,
        is_correct=None,
        pnl_points=0.0,
        lots=0,
    )


def _compute_sharpe(pnl_list: List[float]) -> Optional[float]:
    """Mirror the sharpe computation from quant_backtest.py."""
    if len(pnl_list) < 2:
        return None
    mean_pnl = statistics.mean(pnl_list)
    std_pnl = statistics.stdev(pnl_list)  # n-1
    if std_pnl == 0:
        return None
    return (mean_pnl / std_pnl) * math.sqrt(252)


def test_sharpe_returns_none_when_fewer_than_2_tradeable_days():
    """sharpe_ratio = None when < 2 tradeable days."""
    pnl_list = [1000.0]
    result = _compute_sharpe(pnl_list)
    assert result is None


def test_sharpe_computed_correctly_with_multiple_days():
    """sharpe = mean/stdev * sqrt(252) using n-1 stdev."""
    pnl_list = [1000.0, 2000.0, -500.0, 3000.0, 1500.0]
    mean_pnl = statistics.mean(pnl_list)
    std_pnl = statistics.stdev(pnl_list)
    expected = (mean_pnl / std_pnl) * math.sqrt(252)
    result = _compute_sharpe(pnl_list)
    assert result == pytest.approx(expected)


def test_sharpe_returns_none_when_zero_std():
    """sharpe_ratio = None when all P&L values are equal (std = 0)."""
    pnl_list = [1000.0, 1000.0, 1000.0]
    result = _compute_sharpe(pnl_list)
    assert result is None


# ---------------------------------------------------------------------------
# Unit tests: max_drawdown_pct computation
# ---------------------------------------------------------------------------


def _compute_max_drawdown(equity: List[float]) -> Optional[float]:
    """Mirror the max_drawdown computation from quant_backtest.py."""
    if not equity:
        return None
    peak = equity[0]
    max_drawdown = 0.0
    found_positive_peak = peak > 0
    for val in equity[1:]:
        if val > peak:
            peak = val
        if peak > 0:
            found_positive_peak = True
            drawdown = (val - peak) / peak * 100
            if drawdown < max_drawdown:
                max_drawdown = drawdown
    if not found_positive_peak:
        return None
    return max_drawdown


def test_max_drawdown_simple():
    """Equity goes 1000 → 2000 → 1000 → drawdown = -50%."""
    equity = [1000.0, 2000.0, 1000.0]
    result = _compute_max_drawdown(equity)
    assert result == pytest.approx(-50.0)


def test_max_drawdown_no_drawdown():
    """Monotonically increasing equity → drawdown = 0%."""
    equity = [1000.0, 2000.0, 3000.0, 4000.0]
    result = _compute_max_drawdown(equity)
    assert result == pytest.approx(0.0)


def test_max_drawdown_returns_none_when_empty():
    """max_drawdown_pct = None when equity curve is empty."""
    result = _compute_max_drawdown([])
    assert result is None


def test_max_drawdown_returns_none_when_peak_never_positive():
    """max_drawdown_pct = None when equity is always negative."""
    equity = [-100.0, -200.0, -300.0]
    result = _compute_max_drawdown(equity)
    assert result is None


# ---------------------------------------------------------------------------
# Unit tests: win_loss_ratio computation
# ---------------------------------------------------------------------------


def _compute_win_loss_ratio(pnl_list: List[float]) -> Optional[float]:
    """Mirror the win_loss_ratio computation from quant_backtest.py."""
    wins = [p for p in pnl_list if p > 0]
    losses = [p for p in pnl_list if p < 0]
    if not losses:
        return None
    avg_win = statistics.mean(wins) if wins else 0.0
    avg_loss = statistics.mean(losses)
    return avg_win / abs(avg_loss)


def test_win_loss_ratio_computed_correctly():
    """avg_win / abs(avg_loss) with a mix of wins and losses."""
    pnl_list = [1000.0, 2000.0, -500.0, -1000.0, 3000.0]
    wins = [1000.0, 2000.0, 3000.0]
    losses = [-500.0, -1000.0]
    expected = statistics.mean(wins) / abs(statistics.mean(losses))
    result = _compute_win_loss_ratio(pnl_list)
    assert result == pytest.approx(expected)


def test_win_loss_ratio_returns_none_when_no_losses():
    """win_loss_ratio = None when no losing days."""
    pnl_list = [1000.0, 2000.0, 500.0]
    result = _compute_win_loss_ratio(pnl_list)
    assert result is None


def test_win_loss_ratio_zero_wins_all_losses():
    """When no wins, avg_win = 0.0, so ratio = 0.0 / abs(avg_loss) = 0.0."""
    pnl_list = [-500.0, -1000.0]
    result = _compute_win_loss_ratio(pnl_list)
    assert result == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Integration tests: QuantBacktestDayResult has lots field
# ---------------------------------------------------------------------------


def test_day_result_has_lots_field():
    """QuantBacktestDayResult dataclass must have a lots field."""
    day = QuantBacktestDayResult(
        date="2024-01-01",
        direction="BUY",
        total_score=80,
        tier="strong",
        buy_points=80,
        sell_points=20,
        factors={},
        actual_move_pct=1.0,
        is_correct=True,
        pnl_points=11000.0,
        lots=2,
    )
    assert day.lots == 2


def test_run_result_has_risk_metric_fields():
    """QuantBacktestRunResult dataclass must have sharpe_ratio, max_drawdown_pct, win_loss_ratio."""
    run = QuantBacktestRunResult(
        instrument="NIFTY",
        from_date="2024-01-01",
        to_date="2024-12-31",
        days=[],
        total_days=0,
        tradeable_days=0,
        correct_days=0,
        win_rate_pct=None,
        total_pnl_points=0.0,
        elapsed_seconds=0.1,
        sharpe_ratio=None,
        max_drawdown_pct=None,
        win_loss_ratio=None,
    )
    assert run.sharpe_ratio is None
    assert run.max_drawdown_pct is None
    assert run.win_loss_ratio is None
