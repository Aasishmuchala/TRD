"""Property-based tests for app.engine.risk_manager.RiskManager.

Properties cover: lot sizing, skip path, distance arithmetic, directional
geometry of stop/target levels, input validation, and constants.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import HealthCheck, assume, given, settings, strategies as st

from app.engine.risk_manager import (
    RISK_REWARD_RATIO,
    STOP_MULTIPLIER,
    RiskManager,
    RiskParams,
)


# Strategies ---------------------------------------------------------------

tiers = st.sampled_from(["strong", "moderate", "skip"])
directions = st.sampled_from(["BUY", "SELL", "HOLD"])
unknown_tiers = st.sampled_from(["", "STRONG", "Strong", "junk", "NONE", "0"])
prices = st.floats(min_value=1.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False)
vixes = st.floats(min_value=0.01, max_value=200.0, allow_nan=False, allow_infinity=False)


# ---- Properties ---------------------------------------------------------

@given(tier=tiers, direction=directions, entry=prices, vix=vixes)
def test_lots_in_expected_set(tier, direction, entry, vix):
    """lots is always one of {0, 1, 2} and matches the tier mapping."""
    r = RiskManager.compute(tier, direction, entry, vix)
    assert r.lots in (0, 1, 2)
    if tier == "strong":
        assert r.lots == 2
    elif tier == "moderate":
        assert r.lots == 1
    else:
        assert r.lots == 0


@given(direction=directions, entry=prices, vix=vixes)
def test_skip_zero_distances_and_levels_equal_entry(direction, entry, vix):
    """When tier=='skip', distances are 0 and stop/target levels equal entry_close."""
    r = RiskManager.compute("skip", direction, entry, vix)
    assert r.stop_distance == 0.0
    assert r.target_distance == 0.0
    assert r.stop_level == entry
    assert r.target_level == entry
    assert r.lots == 0


@given(tier=unknown_tiers, direction=directions, entry=prices, vix=vixes)
def test_unknown_tier_treated_as_skip(tier, direction, entry, vix):
    """Any tier value outside {'strong','moderate','skip'} normalises to skip."""
    r = RiskManager.compute(tier, direction, entry, vix)
    assert r.lots == 0
    assert r.stop_distance == 0.0


@given(tier=st.sampled_from(["strong", "moderate"]), direction=directions,
       entry=prices, vix=vixes)
def test_target_distance_is_rr_times_stop_distance(tier, direction, entry, vix):
    """target_distance == round(stop_distance * RISK_REWARD_RATIO, 1) when not skip."""
    r = RiskManager.compute(tier, direction, entry, vix)
    expected = round(r.stop_distance * RISK_REWARD_RATIO, 1)
    assert math.isclose(r.target_distance, expected, abs_tol=1e-9)


@given(tier=st.sampled_from(["strong", "moderate"]), entry=prices, vix=vixes)
def test_buy_levels_geometry(tier, entry, vix):
    """BUY: stop_level < entry < target_level (when distances are non-zero)."""
    r = RiskManager.compute(tier, "BUY", entry, vix)
    assume(r.stop_distance > 0)
    assert r.stop_level < entry
    assert r.target_level > entry
    assert math.isclose(entry - r.stop_level, r.stop_distance, abs_tol=1e-6)
    assert math.isclose(r.target_level - entry, r.target_distance, abs_tol=1e-6)


@given(tier=st.sampled_from(["strong", "moderate"]), entry=prices, vix=vixes)
def test_sell_levels_geometry(tier, entry, vix):
    """SELL: stop_level > entry > target_level (when distances are non-zero)."""
    r = RiskManager.compute(tier, "SELL", entry, vix)
    assume(r.stop_distance > 0)
    assert r.stop_level > entry
    assert r.target_level < entry
    assert math.isclose(r.stop_level - entry, r.stop_distance, abs_tol=1e-6)
    assert math.isclose(entry - r.target_level, r.target_distance, abs_tol=1e-6)


@given(tier=st.sampled_from(["strong", "moderate"]), entry=prices, vix=vixes)
def test_hold_levels_equal_entry(tier, entry, vix):
    """HOLD direction: stop_level == target_level == entry_close even with non-zero distances."""
    r = RiskManager.compute(tier, "HOLD", entry, vix)
    assert r.stop_level == entry
    assert r.target_level == entry


@given(tier=tiers, direction=directions, entry=prices,
       vix=st.floats(max_value=0.0, allow_nan=False, allow_infinity=False))
def test_nonpositive_vix_raises(tier, direction, entry, vix):
    """vix <= 0 always raises ValueError."""
    with pytest.raises(ValueError):
        RiskManager.compute(tier, direction, entry, vix)


@given(tier=tiers, direction=directions,
       entry=st.floats(max_value=0.0, allow_nan=False, allow_infinity=False),
       vix=vixes)
def test_nonpositive_entry_raises(tier, direction, entry, vix):
    """entry_close <= 0 always raises ValueError."""
    with pytest.raises(ValueError):
        RiskManager.compute(tier, direction, entry, vix)


@given(tier=tiers, direction=directions, entry=prices, vix=vixes)
def test_risk_reward_and_vix_used_are_passthrough(tier, direction, entry, vix):
    """risk_reward is the constant 1.5 and vix_used echoes the input vix."""
    r = RiskManager.compute(tier, direction, entry, vix)
    assert r.risk_reward == RISK_REWARD_RATIO
    assert r.vix_used == vix


@given(direction=st.sampled_from(["BUY", "SELL"]), entry=prices, vix=vixes)
def test_stop_distance_formula(direction, entry, vix):
    """stop_distance == round(vix * STOP_MULTIPLIER, 1) on non-skip tiers."""
    r = RiskManager.compute("strong", direction, entry, vix)
    assert math.isclose(r.stop_distance, round(vix * STOP_MULTIPLIER, 1), abs_tol=1e-9)
