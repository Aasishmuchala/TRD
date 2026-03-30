"""Tests for BacktestEngine, BacktestDayResult, and BacktestRunResult."""

import pytest
from app.engine.backtest_engine import BacktestDayResult, BacktestRunResult, BacktestEngine


# ---------------------------------------------------------------------------
# Task 1: Dataclass instantiation
# ---------------------------------------------------------------------------

def test_backtest_day_result_instantiation():
    """BacktestDayResult can be created with all required fields."""
    result = BacktestDayResult(
        date="2025-01-10",
        next_date="2025-01-11",
        nifty_close=22000.0,
        nifty_next_close=22220.0,
        actual_move_pct=1.0,
        predicted_direction="BUY",
        predicted_conviction=72.5,
        direction_correct=True,
        pnl_points=660.0,
        per_agent_directions={"FII": "BUY", "DII": "HOLD"},
        round_history=[],
        signals={"rsi": 55.0, "supertrend": "bullish"},
    )
    assert result.date == "2025-01-10"
    assert result.next_date == "2025-01-11"
    assert result.nifty_close == 22000.0
    assert result.nifty_next_close == 22220.0
    assert result.actual_move_pct == 1.0
    assert result.predicted_direction == "BUY"
    assert result.predicted_conviction == 72.5
    assert result.direction_correct is True
    assert result.pnl_points == 660.0
    assert result.per_agent_directions == {"FII": "BUY", "DII": "HOLD"}
    assert result.round_history == []
    assert result.signals == {"rsi": 55.0, "supertrend": "bullish"}


def test_backtest_run_result_instantiation():
    """BacktestRunResult can be created with all required fields."""
    day = BacktestDayResult(
        date="2025-01-10",
        next_date="2025-01-11",
        nifty_close=22000.0,
        nifty_next_close=22220.0,
        actual_move_pct=1.0,
        predicted_direction="BUY",
        predicted_conviction=72.5,
        direction_correct=True,
        pnl_points=660.0,
        per_agent_directions={"FII": "BUY"},
        round_history=[],
        signals={},
    )
    run = BacktestRunResult(
        run_id="test-run-123",
        instrument="NIFTY",
        from_date="2025-01-01",
        to_date="2025-01-31",
        mock_mode=True,
        days=[day],
        overall_accuracy=1.0,
        per_agent_accuracy={"FII": 1.0},
        total_pnl_points=660.0,
        created_at="2025-01-31T00:00:00Z",
    )
    assert run.run_id == "test-run-123"
    assert run.instrument == "NIFTY"
    assert len(run.days) == 1
    assert run.mock_mode is True
    assert run.overall_accuracy == 1.0
    assert run.total_pnl_points == 660.0


# ---------------------------------------------------------------------------
# Task 1: direction_correct semantics via BacktestEngine._is_correct
# ---------------------------------------------------------------------------

def test_is_correct_buy_positive_move():
    engine = BacktestEngine()
    assert engine._is_correct("BUY", 0.5) is True


def test_is_correct_buy_negative_move():
    engine = BacktestEngine()
    assert engine._is_correct("BUY", -0.2) is False


def test_is_correct_hold_excluded():
    engine = BacktestEngine()
    assert engine._is_correct("HOLD", 0.5) is None


def test_is_correct_sell_negative_move():
    engine = BacktestEngine()
    assert engine._is_correct("SELL", -0.5) is True


def test_is_correct_strong_buy_positive():
    engine = BacktestEngine()
    assert engine._is_correct("STRONG_BUY", 0.5) is True


def test_is_correct_strong_sell_negative():
    engine = BacktestEngine()
    assert engine._is_correct("STRONG_SELL", -0.5) is True


def test_is_correct_buy_below_threshold():
    """BUY requires >0.1% move — exactly 0.05% should be False."""
    engine = BacktestEngine()
    assert engine._is_correct("BUY", 0.05) is False


def test_is_correct_sell_above_threshold():
    """SELL requires < -0.1% move — exactly -0.05% should be False."""
    engine = BacktestEngine()
    assert engine._is_correct("SELL", -0.05) is False


# ---------------------------------------------------------------------------
# Task 2: _compute_pnl
# ---------------------------------------------------------------------------

def test_compute_pnl_buy():
    """BUY: pnl = actual_move_pct * 3.0 * (close / 100)."""
    engine = BacktestEngine()
    result = engine._compute_pnl("BUY", 1.0, 22000.0)
    assert abs(result - 660.0) < 0.001


def test_compute_pnl_hold():
    """HOLD: pnl = 0."""
    engine = BacktestEngine()
    assert engine._compute_pnl("HOLD", 0.5, 22000.0) == 0.0


def test_compute_pnl_sell():
    """SELL: profits from negative move — pnl = -actual_move_pct * 3.0 * (close / 100)."""
    engine = BacktestEngine()
    result = engine._compute_pnl("SELL", -1.0, 22000.0)
    assert abs(result - 660.0) < 0.001


def test_compute_pnl_buy_negative_move():
    """BUY when market falls = negative pnl."""
    engine = BacktestEngine()
    result = engine._compute_pnl("BUY", -0.5, 22000.0)
    assert result < 0


def test_compute_pnl_strong_buy():
    """STRONG_BUY uses same formula as BUY."""
    engine = BacktestEngine()
    assert engine._compute_pnl("STRONG_BUY", 1.0, 22000.0) == engine._compute_pnl("BUY", 1.0, 22000.0)


# ---------------------------------------------------------------------------
# Task 2: _compute_consensus
# ---------------------------------------------------------------------------

def _make_agent_response(direction: str, conviction: float):
    """Helper to create a minimal agent response dict-like object."""
    class FakeResponse:
        pass
    r = FakeResponse()
    r.direction = direction
    r.conviction = conviction
    return r


def test_compute_consensus_majority_buy():
    """4 of 6 agents saying BUY -> direction=BUY."""
    engine = BacktestEngine()
    final_outputs = {
        "FII": _make_agent_response("BUY", 70.0),
        "DII": _make_agent_response("BUY", 65.0),
        "RETAIL_FNO": _make_agent_response("BUY", 60.0),
        "ALGO": _make_agent_response("BUY", 55.0),
        "PROMOTER": _make_agent_response("SELL", 50.0),
        "RBI": _make_agent_response("HOLD", 40.0),
    }
    direction, conviction = engine._compute_consensus(final_outputs)
    assert direction == "BUY"
    assert conviction == pytest.approx((70.0 + 65.0 + 60.0 + 55.0) / 4, rel=0.01)


def test_compute_consensus_sell_majority():
    """3 SELL vs 2 BUY vs 1 HOLD -> SELL wins."""
    engine = BacktestEngine()
    final_outputs = {
        "FII": _make_agent_response("SELL", 80.0),
        "DII": _make_agent_response("SELL", 75.0),
        "RETAIL_FNO": _make_agent_response("SELL", 70.0),
        "ALGO": _make_agent_response("BUY", 60.0),
        "PROMOTER": _make_agent_response("BUY", 55.0),
        "RBI": _make_agent_response("HOLD", 50.0),
    }
    direction, conviction = engine._compute_consensus(final_outputs)
    assert direction == "SELL"


def test_compute_consensus_hold_when_all_hold():
    """All HOLD -> direction=HOLD."""
    engine = BacktestEngine()
    final_outputs = {
        "FII": _make_agent_response("HOLD", 50.0),
        "DII": _make_agent_response("HOLD", 45.0),
    }
    direction, conviction = engine._compute_consensus(final_outputs)
    assert direction == "HOLD"
