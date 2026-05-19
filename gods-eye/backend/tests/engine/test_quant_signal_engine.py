"""TDD tests for QuantSignalEngine -- RED phase.

All tests must FAIL until quant_signal_engine.py is created and implemented.
Run with: cd gods-eye/backend && python -m pytest app/engine/test_quant_signal_engine.py -v
"""
import pytest
from app.engine.quant_signal_engine import QuantInputs, QuantSignalEngine, QuantScoreResult


def _inputs(**kwargs) -> QuantInputs:
    """Neutral base inputs (all signals inactive)."""
    defaults = dict(
        fii_net_cr=0.0,
        dii_net_cr=0.0,
        pcr=1.0,
        rsi=50.0,
        vix=18.0,
        vix_5d_avg=18.0,
        supertrend="bullish",
    )
    defaults.update(kwargs)
    return QuantInputs(**defaults)


# ---------------------------------------------------------------------------
# Individual rule tests
# ---------------------------------------------------------------------------


def test_fii_buy_signal_adds_25_buy_points():
    """fii_net_cr > 1000 → +25 buy points."""
    inp = _inputs(fii_net_cr=2000.0, supertrend="bearish")  # supertrend neutral
    result = QuantSignalEngine.compute_quant_score(inp)
    assert result.buy_points == 25
    assert result.factors["fii_flow"]["points"] == 25
    assert result.factors["fii_flow"]["threshold_hit"] is True
    assert result.factors["fii_flow"]["side"] == "buy"


def test_fii_sell_signal_adds_25_sell_points():
    """fii_net_cr < -1000 → +25 sell points."""
    inp = _inputs(fii_net_cr=-2000.0, supertrend="bearish")
    result = QuantSignalEngine.compute_quant_score(inp)
    assert result.sell_points >= 25
    assert result.factors["fii_flow"]["points"] == 25
    assert result.factors["fii_flow"]["threshold_hit"] is True
    assert result.factors["fii_flow"]["side"] == "sell"


def test_dii_absorption_adds_10_buy_points_only_when_fii_negative():
    """dii_net_cr > 0 AND fii_net_cr < 0 → +10 buy points (dii_absorption).
    When fii is positive, dii_absorption should NOT trigger.
    """
    # Should trigger: fii negative, dii positive
    inp_trigger = _inputs(fii_net_cr=-500.0, dii_net_cr=800.0, supertrend="bearish")
    result_trigger = QuantSignalEngine.compute_quant_score(inp_trigger)
    assert result_trigger.factors["dii_absorption"]["points"] == 10
    assert result_trigger.factors["dii_absorption"]["threshold_hit"] is True
    assert result_trigger.factors["dii_absorption"]["side"] == "buy"

    # Should NOT trigger: fii positive
    inp_no_trigger = _inputs(fii_net_cr=200.0, dii_net_cr=800.0, supertrend="bearish")
    result_no_trigger = QuantSignalEngine.compute_quant_score(inp_no_trigger)
    assert result_no_trigger.factors["dii_absorption"]["threshold_hit"] is False
    assert result_no_trigger.factors["dii_absorption"]["points"] == 0


def test_pcr_bullish_above_1_2_adds_15_buy_points():
    """pcr > 1.2 → +15 buy points (put-heavy = contrarian bullish)."""
    inp = _inputs(pcr=1.5, supertrend="bearish")
    result = QuantSignalEngine.compute_quant_score(inp)
    assert result.factors["pcr"]["points"] == 15
    assert result.factors["pcr"]["threshold_hit"] is True
    assert result.factors["pcr"]["side"] == "buy"


def test_pcr_bearish_below_0_7_adds_15_sell_points():
    """pcr < 0.7 → +15 sell points (call-heavy = contrarian bearish)."""
    inp = _inputs(pcr=0.5, supertrend="bearish")
    result = QuantSignalEngine.compute_quant_score(inp)
    assert result.factors["pcr"]["points"] == 15
    assert result.factors["pcr"]["threshold_hit"] is True
    assert result.factors["pcr"]["side"] == "sell"


def test_rsi_oversold_below_30_adds_20_buy_points():
    """rsi < 30 → +20 buy points (oversold)."""
    inp = _inputs(rsi=25.0, supertrend="bearish")
    result = QuantSignalEngine.compute_quant_score(inp)
    assert result.factors["rsi"]["points"] == 20
    assert result.factors["rsi"]["threshold_hit"] is True
    assert result.factors["rsi"]["side"] == "buy"


def test_rsi_overbought_above_70_adds_20_sell_points():
    """rsi > 70 → +20 sell points (overbought)."""
    inp = _inputs(rsi=75.0, supertrend="bearish")
    result = QuantSignalEngine.compute_quant_score(inp)
    assert result.factors["rsi"]["points"] == 20
    assert result.factors["rsi"]["threshold_hit"] is True
    assert result.factors["rsi"]["side"] == "sell"


def test_vix_calm_below_14_and_falling_adds_10_buy_points():
    """vix < 14 AND vix < vix_5d_avg → +10 buy points (calm + falling)."""
    inp = _inputs(vix=12.0, vix_5d_avg=13.0, supertrend="bearish")
    result = QuantSignalEngine.compute_quant_score(inp)
    assert result.factors["vix"]["points"] == 10
    assert result.factors["vix"]["threshold_hit"] is True
    assert result.factors["vix"]["side"] == "buy"


def test_vix_fear_above_20_and_rising_adds_10_sell_points():
    """vix > 20 AND vix > vix_5d_avg → +10 sell points (fear + rising)."""
    inp = _inputs(vix=25.0, vix_5d_avg=22.0, supertrend="bearish")
    result = QuantSignalEngine.compute_quant_score(inp)
    assert result.factors["vix"]["points"] == 10
    assert result.factors["vix"]["threshold_hit"] is True
    assert result.factors["vix"]["side"] == "sell"


def test_supertrend_bullish_adds_10_buy_points():
    """supertrend == 'bullish' → +10 buy points."""
    inp = _inputs(supertrend="bullish")
    result = QuantSignalEngine.compute_quant_score(inp)
    assert result.factors["supertrend"]["points"] == 10
    assert result.factors["supertrend"]["threshold_hit"] is True
    assert result.factors["supertrend"]["side"] == "buy"


def test_supertrend_bearish_adds_10_sell_points():
    """supertrend == 'bearish' → +10 sell points."""
    inp = _inputs(supertrend="bearish")
    result = QuantSignalEngine.compute_quant_score(inp)
    assert result.factors["supertrend"]["points"] == 10
    assert result.factors["supertrend"]["threshold_hit"] is True
    assert result.factors["supertrend"]["side"] == "sell"


# ---------------------------------------------------------------------------
# Combined signal tests
# ---------------------------------------------------------------------------


def test_all_buy_signals_strong_direction_is_buy():
    """fii=+2000, pcr=1.5, rsi=25, vix=12/5d=13, supertrend=bullish
    → buy_points=80, direction=BUY, tier=strong.

    Rules triggered: fii_buy(25) + pcr_bullish(15) + rsi_oversold(20) + vix_calm(10) + supertrend_bull(10) = 80
    Note: dii_absorption does NOT trigger because fii is positive.
    """
    inp = _inputs(
        fii_net_cr=2000.0,
        pcr=1.5,
        rsi=25.0,
        vix=12.0,
        vix_5d_avg=13.0,
        supertrend="bullish",
    )
    result = QuantSignalEngine.compute_quant_score(inp)
    assert result.buy_points == 80
    assert result.direction == "BUY"
    assert result.tier == "strong"
    assert result.total_score == 80


def test_all_sell_signals_strong_direction_is_sell():
    """fii=-2000, pcr=0.5, rsi=75, vix=25/5d=22, supertrend=bearish
    → sell_points=80, direction=SELL, tier=strong.

    Rules triggered: fii_sell(25) + pcr_bearish(15) + rsi_overbought(20) + vix_fear(10) + supertrend_bear(10) = 80
    """
    inp = _inputs(
        fii_net_cr=-2000.0,
        pcr=0.5,
        rsi=75.0,
        vix=25.0,
        vix_5d_avg=22.0,
        supertrend="bearish",
    )
    result = QuantSignalEngine.compute_quant_score(inp)
    assert result.sell_points == 80
    assert result.direction == "SELL"
    assert result.tier == "strong"
    assert result.total_score == 80


def test_no_signals_returns_hold_skip():
    """All neutral inputs → direction=HOLD, tier=skip, instrument_hint=NONE.

    Only supertrend=bullish adds 10 buy points (since default is bullish).
    To get truly no signals, set supertrend=bearish with all neutrals gives sell 10.
    Use custom neutral: fii=0, dii=0, pcr=1.0, rsi=50, vix=18/18, supertrend=bearish
    → sell_points=10, buy_points=0, but 10 < 50 → HOLD.
    """
    inp = _inputs(supertrend="bearish")
    result = QuantSignalEngine.compute_quant_score(inp)
    assert result.direction == "HOLD"
    assert result.tier == "skip"
    assert result.instrument_hint == "NONE"


def test_buy_points_exactly_50_is_hold():
    """Boundary: buy_points == 50 is NOT strictly > 50 → direction=HOLD.

    Arrange: rsi_oversold(20) + pcr_bullish(15) + supertrend_bullish(10) + vix_calm(10) = 55.
    Need exactly 50: rsi_oversold(20) + pcr_bullish(15) + supertrend_bullish(10) + vix_calm... no.
    Use: fii_buy(25) + rsi_oversold(20) + vix_calm(10) = 55 → too much.
    Use: pcr_bullish(15) + rsi_oversold(20) + supertrend_bullish(10) + vix_calm(5)... vix is binary.
    Exactly 50: rsi_oversold(20) + pcr_bullish(15) + supertrend_bullish(10) + vix_calm(5)... not possible.

    Alternative: fii_buy(25) + pcr_bullish(15) + supertrend_bullish(10) = 50.
    fii=+2000, pcr=1.5, rsi=50 (not oversold), vix=18/18 (not calm), supertrend=bullish.
    """
    inp = _inputs(
        fii_net_cr=2000.0,
        pcr=1.5,
        rsi=50.0,
        vix=18.0,
        vix_5d_avg=18.0,
        supertrend="bullish",
    )
    result = QuantSignalEngine.compute_quant_score(inp)
    assert result.buy_points == 50
    assert result.direction == "HOLD"


def test_buy_points_51_is_buy():
    """Boundary: buy_points == 51 (> 50 AND > sell_points) → direction=BUY.

    Arrange buy_points = 51: need a combination that sums to exactly 51.
    fii_buy(25) + pcr_bullish(15) + supertrend_bullish(10) = 50... then add 1 more.
    There's no 1-point rule. Instead use fii_buy(25) + rsi_oversold(20) + supertrend_bullish(10) = 55,
    minus vix_calm not active (vix=18) = 55. Need exactly 51 which isn't possible with these rules.

    Use fii_buy(25) + dii_absorption(10) + supertrend_bullish(10) + pcr=neutral = 45... still not 51.

    Actually per plan spec: "buy exactly 51: arrange buy_points=51 → direction=BUY"
    The closest achievable with these rules is checking that 52 works as BUY:
    fii_buy(25) + pcr_bullish(15) + supertrend_bullish(10) + dii_absorption(10, fii must be negative for dii... contradiction).

    Simpler valid arrangement for > 50:
    rsi_oversold(20) + pcr_bullish(15) + supertrend_bullish(10) + vix_calm(10) = 55 > 50 → BUY.
    """
    inp = _inputs(
        fii_net_cr=0.0,
        dii_net_cr=0.0,
        pcr=1.5,
        rsi=25.0,
        vix=12.0,
        vix_5d_avg=13.0,
        supertrend="bullish",
    )
    result = QuantSignalEngine.compute_quant_score(inp)
    assert result.buy_points > 50
    assert result.direction == "BUY"


# ---------------------------------------------------------------------------
# Instrument hint tests
# ---------------------------------------------------------------------------


def test_instrument_banknifty_buy_returns_banknifty_ce():
    """BUY signal with instrument=BANKNIFTY → instrument_hint=BANKNIFTY_CE."""
    inp = _inputs(
        fii_net_cr=2000.0,
        pcr=1.5,
        rsi=25.0,
        vix=12.0,
        vix_5d_avg=13.0,
        supertrend="bullish",
    )
    result = QuantSignalEngine.compute_quant_score(inp, instrument="BANKNIFTY")
    assert result.direction == "BUY"
    assert result.instrument_hint == "BANKNIFTY_CE"


def test_instrument_banknifty_sell_returns_banknifty_pe():
    """SELL signal with instrument=BANKNIFTY → instrument_hint=BANKNIFTY_PE."""
    inp = _inputs(
        fii_net_cr=-2000.0,
        pcr=0.5,
        rsi=75.0,
        vix=25.0,
        vix_5d_avg=22.0,
        supertrend="bearish",
    )
    result = QuantSignalEngine.compute_quant_score(inp, instrument="BANKNIFTY")
    assert result.direction == "SELL"
    assert result.instrument_hint == "BANKNIFTY_PE"


# ---------------------------------------------------------------------------
# Structure tests
# ---------------------------------------------------------------------------


def test_factors_dict_contains_all_evaluated_rules():
    """factors dict must contain entries for all evaluated rules."""
    inp = _inputs()
    result = QuantSignalEngine.compute_quant_score(inp)

    required_keys = {
        "fii_flow",
        "dii_absorption",
        "pcr",
        "rsi",
        "vix",
        "supertrend",
    }
    assert required_keys.issubset(set(result.factors.keys())), (
        f"Missing keys: {required_keys - set(result.factors.keys())}"
    )
    for key in required_keys:
        entry = result.factors[key]
        assert "points" in entry, f"factors['{key}'] missing 'points'"
        assert "threshold_hit" in entry, f"factors['{key}'] missing 'threshold_hit'"
        assert "side" in entry, f"factors['{key}'] missing 'side'"


def test_total_score_is_max_of_buy_and_sell_clamped_to_100():
    """total_score = max(buy_points, sell_points) clamped to [0, 100]."""
    # BUY scenario: buy_points=80
    inp_buy = _inputs(
        fii_net_cr=2000.0,
        pcr=1.5,
        rsi=25.0,
        vix=12.0,
        vix_5d_avg=13.0,
        supertrend="bullish",
    )
    result_buy = QuantSignalEngine.compute_quant_score(inp_buy)
    assert result_buy.total_score == max(result_buy.buy_points, result_buy.sell_points)
    assert 0 <= result_buy.total_score <= 100

    # SELL scenario: sell_points=80
    inp_sell = _inputs(
        fii_net_cr=-2000.0,
        pcr=0.5,
        rsi=75.0,
        vix=25.0,
        vix_5d_avg=22.0,
        supertrend="bearish",
    )
    result_sell = QuantSignalEngine.compute_quant_score(inp_sell)
    assert result_sell.total_score == max(result_sell.buy_points, result_sell.sell_points)
    assert 0 <= result_sell.total_score <= 100
