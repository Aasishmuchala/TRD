"""TDD tests for RiskManager — Phase 13 Plan 01.

Tests cover:
  1. strong + BUY: lots=2, stop_distance=100.0, target_distance=150.0, levels correct
  2. moderate + SELL: lots=1, stop_distance=70.0, target_distance=105.0, levels correct
  3. skip + BUY: lots=0, distances=0.0, levels == entry_close
  4. strong + HOLD: lots=2, distances computed, levels == entry_close (no direction)
  5. VIX=25: stop_distance=125.0, target_distance=187.5
  6. vix=0 raises ValueError
  7. entry_close=0 raises ValueError
  8. risk_reward == 1.5 always (any valid inputs)
"""

import pytest
from app.engine.risk_manager import RiskManager, RiskParams


# ---------------------------------------------------------------------------
# Test 1: strong + BUY + close=22000 + VIX=20
#   lots=2, stop=100.0, target=150.0, stop_level=21900.0, target_level=22150.0
# ---------------------------------------------------------------------------

def test_strong_buy_standard_values():
    params = RiskManager.compute("strong", "BUY", 22000.0, 20.0)

    assert params.lots == 2
    assert params.stop_distance == 100.0
    assert params.target_distance == 150.0
    assert params.stop_level == 21900.0,  f"Expected stop_level=21900.0, got {params.stop_level}"
    assert params.target_level == 22150.0, f"Expected target_level=22150.0, got {params.target_level}"
    assert params.vix_used == 20.0
    assert params.risk_reward == 1.5


# ---------------------------------------------------------------------------
# Test 2: moderate + SELL + close=22000 + VIX=14
#   lots=1, stop=70.0, target=105.0, stop_level=22070.0, target_level=21895.0
# ---------------------------------------------------------------------------

def test_moderate_sell_standard_values():
    params = RiskManager.compute("moderate", "SELL", 22000.0, 14.0)

    assert params.lots == 1
    assert params.stop_distance == 70.0
    assert params.target_distance == 105.0
    assert params.stop_level == 22070.0,  f"Expected stop_level=22070.0, got {params.stop_level}"
    assert params.target_level == 21895.0, f"Expected target_level=21895.0, got {params.target_level}"
    assert params.vix_used == 14.0
    assert params.risk_reward == 1.5


# ---------------------------------------------------------------------------
# Test 3: skip + BUY + close=22000 + VIX=20
#   lots=0, all distances=0, levels == entry_close
# ---------------------------------------------------------------------------

def test_skip_produces_zero_lots_and_levels():
    params = RiskManager.compute("skip", "BUY", 22000.0, 20.0)

    assert params.lots == 0
    assert params.stop_distance == 0.0,   f"Expected stop_distance=0.0, got {params.stop_distance}"
    assert params.target_distance == 0.0, f"Expected target_distance=0.0, got {params.target_distance}"
    assert params.stop_level == 22000.0,  f"Expected stop_level=22000.0, got {params.stop_level}"
    assert params.target_level == 22000.0, f"Expected target_level=22000.0, got {params.target_level}"
    assert params.risk_reward == 1.5


# ---------------------------------------------------------------------------
# Test 4: strong + HOLD + close=22000 + VIX=20
#   lots=2, distances computed (100.0/150.0), but levels == entry_close (no direction)
# ---------------------------------------------------------------------------

def test_strong_hold_no_directional_levels():
    params = RiskManager.compute("strong", "HOLD", 22000.0, 20.0)

    assert params.lots == 2
    assert params.stop_distance == 100.0
    assert params.target_distance == 150.0
    # HOLD means no directional offset — levels stay at entry_close
    assert params.stop_level == 22000.0,   f"Expected stop_level=22000.0 for HOLD, got {params.stop_level}"
    assert params.target_level == 22000.0, f"Expected target_level=22000.0 for HOLD, got {params.target_level}"


# ---------------------------------------------------------------------------
# Test 5: VIX=25 → stop_distance=125.0, target_distance=187.5
# ---------------------------------------------------------------------------

def test_vix_25_stop_and_target():
    params = RiskManager.compute("strong", "BUY", 22000.0, 25.0)

    assert params.stop_distance == 125.0,   f"Expected stop_distance=125.0, got {params.stop_distance}"
    assert params.target_distance == 187.5, f"Expected target_distance=187.5, got {params.target_distance}"
    assert params.vix_used == 25.0


# ---------------------------------------------------------------------------
# Test 6: vix=0 raises ValueError
# ---------------------------------------------------------------------------

def test_zero_vix_raises_value_error():
    with pytest.raises(ValueError, match="VIX must be positive"):
        RiskManager.compute("strong", "BUY", 22000.0, 0.0)


# ---------------------------------------------------------------------------
# Test 7: entry_close=0 raises ValueError
# ---------------------------------------------------------------------------

def test_zero_entry_close_raises_value_error():
    with pytest.raises(ValueError, match="entry_close must be positive"):
        RiskManager.compute("strong", "BUY", 0.0, 20.0)


# ---------------------------------------------------------------------------
# Test 8: risk_reward == 1.5 always
# ---------------------------------------------------------------------------

def test_risk_reward_always_1_5():
    for tier, direction, close, vix in [
        ("strong", "BUY", 22000.0, 20.0),
        ("moderate", "SELL", 18000.0, 14.0),
        ("skip", "BUY", 22000.0, 20.0),
        ("strong", "HOLD", 22000.0, 25.0),
    ]:
        params = RiskManager.compute(tier, direction, close, vix)
        assert params.risk_reward == 1.5, (
            f"risk_reward must always be 1.5, got {params.risk_reward} "
            f"for tier={tier}, direction={direction}"
        )


# ---------------------------------------------------------------------------
# Test 9: Unknown tier treated as skip
# ---------------------------------------------------------------------------

def test_unknown_tier_treated_as_skip():
    params = RiskManager.compute("unknown_tier", "BUY", 22000.0, 20.0)

    assert params.lots == 0, f"Unknown tier must produce lots=0, got {params.lots}"
    assert params.stop_distance == 0.0
    assert params.target_distance == 0.0
    assert params.stop_level == 22000.0
    assert params.target_level == 22000.0


# ---------------------------------------------------------------------------
# Test 10: negative vix raises ValueError
# ---------------------------------------------------------------------------

def test_negative_vix_raises_value_error():
    with pytest.raises(ValueError, match="VIX must be positive"):
        RiskManager.compute("strong", "BUY", 22000.0, -5.0)
