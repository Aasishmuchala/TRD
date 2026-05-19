"""Property-based tests for app.engine.stop_loss_engine.StopLossEngine."""

from __future__ import annotations

import math

from hypothesis import HealthCheck, assume, given, settings, strategies as st

from app.engine.stop_loss_engine import (
    ATR_PERIOD,
    DEFAULT_ATR_MULTIPLIER,
    DEFAULT_PCT_STOP,
    StopLossEngine,
)


# Strategies ---------------------------------------------------------------

prices = st.floats(min_value=1.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False)
small_pos = st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False)
multipliers = st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False)
pct_stops = st.floats(min_value=0.01, max_value=20.0, allow_nan=False, allow_infinity=False)
tradeable = st.sampled_from(["BUY", "STRONG_BUY", "SELL", "STRONG_SELL"])
all_directions = st.sampled_from(["BUY", "STRONG_BUY", "SELL", "STRONG_SELL", "HOLD", "UNKNOWN"])


@st.composite
def ohlcv_row(draw):
    close = draw(st.floats(min_value=1000.0, max_value=50_000.0, allow_nan=False, allow_infinity=False))
    spread = draw(st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False))
    high = close + spread / 2
    low = max(0.01, close - spread / 2)
    return {"high": high, "low": low, "close": close}


ohlcv_windows = st.lists(ohlcv_row(), min_size=0, max_size=40)


# ---- compute_atr properties ---------------------------------------------

@given(rows=st.lists(ohlcv_row(), max_size=ATR_PERIOD))
def test_atr_insufficient_data_returns_zero(rows):
    """ATR returns 0.0 if there are fewer than ATR_PERIOD+1 rows."""
    assert StopLossEngine.compute_atr(rows) == 0.0


@given(rows=ohlcv_windows)
def test_atr_is_non_negative(rows):
    """ATR is always >= 0 (true ranges are non-negative)."""
    assert StopLossEngine.compute_atr(rows) >= 0.0


# ---- compute_stop properties --------------------------------------------

@given(entry=prices, atr=small_pos, mult=multipliers, pct=pct_stops)
def test_hold_returns_no_stop_sentinel(entry, atr, mult, pct):
    """Non-tradeable directions return method=='none' sentinel."""
    r = StopLossEngine.compute_stop("HOLD", entry, atr, mult, pct)
    assert r.method == "none"
    assert r.stop_distance_pts == 0.0


@given(direction=tradeable, entry=prices, atr=small_pos, mult=multipliers, pct=pct_stops)
def test_stop_distance_is_abs_diff_of_levels(direction, entry, atr, mult, pct):
    """stop_distance_pts == |entry_price - stop_price| (to within rounding)."""
    r = StopLossEngine.compute_stop(direction, entry, atr, mult, pct)
    assume(r.method != "none")
    assert math.isclose(abs(r.entry_price - r.stop_price), r.stop_distance_pts, abs_tol=0.05)


@given(direction=st.sampled_from(["BUY", "STRONG_BUY"]), entry=prices,
       atr=small_pos, mult=multipliers, pct=pct_stops)
def test_buy_stop_is_below_entry(direction, entry, atr, mult, pct):
    """For BUY/STRONG_BUY the stop price must lie below the entry close."""
    r = StopLossEngine.compute_stop(direction, entry, atr, mult, pct)
    assume(r.stop_distance_pts > 0)
    assert r.stop_price < r.entry_price


@given(direction=st.sampled_from(["SELL", "STRONG_SELL"]), entry=prices,
       atr=small_pos, mult=multipliers, pct=pct_stops)
def test_sell_stop_is_above_entry(direction, entry, atr, mult, pct):
    """For SELL/STRONG_SELL the stop price must lie above the entry close."""
    r = StopLossEngine.compute_stop(direction, entry, atr, mult, pct)
    assume(r.stop_distance_pts > 0)
    assert r.stop_price > r.entry_price


@given(direction=tradeable, entry=prices,
       atr=st.floats(min_value=0.01, max_value=500.0, allow_nan=False),
       mult=multipliers, pct=pct_stops)
def test_tighter_of_atr_and_pct_is_chosen(direction, entry, atr, mult, pct):
    """When ATR > 0, the realised distance is min(atr*mult, entry*pct/100)."""
    r = StopLossEngine.compute_stop(direction, entry, atr, mult, pct)
    expected = min(atr * mult, entry * pct / 100.0)
    assert r.stop_distance_pts <= round(expected, 2) + 0.05


@given(direction=tradeable,
       entry=st.floats(max_value=0.0, allow_nan=False, allow_infinity=False),
       atr=small_pos, mult=multipliers, pct=pct_stops)
def test_nonpositive_entry_returns_no_stop(direction, entry, atr, mult, pct):
    """entry_close <= 0 produces the _NO_STOP sentinel."""
    r = StopLossEngine.compute_stop(direction, entry, atr, mult, pct)
    assert r.method == "none"


@given(entry=prices, atr=small_pos, mult=multipliers, pct=pct_stops)
def test_stop_pct_matches_distance_over_entry(entry, atr, mult, pct):
    """stop_pct == stop_distance_pts / entry_price * 100 (within rounding)."""
    r = StopLossEngine.compute_stop("BUY", entry, atr, mult, pct)
    assume(r.method != "none")
    expected = (r.stop_distance_pts / r.entry_price) * 100
    assert math.isclose(r.stop_pct, expected, abs_tol=0.05)


# ---- check_stop_hit properties ------------------------------------------

@given(stop=prices, low=prices, high=prices)
def test_check_stop_hit_buy_triggers_iff_low_le_stop(stop, low, high):
    """BUY stop triggers iff day_low <= stop_price."""
    assume(low <= high)
    assert StopLossEngine.check_stop_hit("BUY", stop, low, high) == (low <= stop)


@given(stop=prices, low=prices, high=prices)
def test_check_stop_hit_sell_triggers_iff_high_ge_stop(stop, low, high):
    """SELL stop triggers iff day_high >= stop_price."""
    assume(low <= high)
    assert StopLossEngine.check_stop_hit("SELL", stop, low, high) == (high >= stop)


@given(stop=prices, low=prices, high=prices)
def test_hold_never_triggers(stop, low, high):
    """HOLD direction never reports a stop hit."""
    assert StopLossEngine.check_stop_hit("HOLD", stop, low, high) is False


# ---- compute_stopped_pnl properties -------------------------------------

@given(direction=tradeable, entry=prices, mult=multipliers, pct=pct_stops,
       atr=small_pos)
def test_stopped_pnl_is_loss_when_stop_is_at_correct_side(direction, entry, atr, mult, pct):
    """When stop is computed by compute_stop (stop on the losing side), pnl <= 0."""
    r = StopLossEngine.compute_stop(direction, entry, atr, mult, pct)
    assume(r.method != "none")
    pnl = StopLossEngine.compute_stopped_pnl(direction, r.entry_price, r.stop_price)
    assert pnl <= 0.0


@given(entry=prices, stop=prices)
def test_hold_pnl_is_zero(entry, stop):
    """compute_stopped_pnl always returns 0.0 for HOLD."""
    assert StopLossEngine.compute_stopped_pnl("HOLD", entry, stop) == 0.0
