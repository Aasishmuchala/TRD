"""TDD tests for SignalScorer — 0-100 combined signal scoring.

Tests verify:
  - Scoring formula: 60% sentiment + 40% technical alignment
  - Tier boundaries: >70 strong, >=50 moderate, <50 skip
  - Instrument mapping: NIFTY/BANKNIFTY + direction → CE/PE/NONE
  - HOLD direction always produces score < 50
  - Output shape: ScoreResult dataclass with required fields
  - Clamp: score never < 0 or > 100
"""

import pytest
from app.engine.signal_scorer import SignalScorer, ScoreResult


# ---------------------------------------------------------------------------
# Test 1: BUY with all 4 technicals aligned → score > 70, strong, NIFTY_CE
# ---------------------------------------------------------------------------

def test_buy_full_alignment_strong_tier():
    """BUY direction + all 4 technicals aligned → score > 70 and tier = 'strong'."""
    result = SignalScorer.score(
        direction="BUY",
        conviction=80,
        signals={
            "rsi": 25,                # < 30 supports BUY
            "supertrend": "bullish",  # supports BUY
            "vix_regime": "low",      # supports BUY
            "oi_sentiment": "bullish", # supports BUY
        },
        instrument="NIFTY",
    )
    assert isinstance(result, ScoreResult)
    assert result.score > 70, f"Expected score > 70, got {result.score}"
    assert result.tier == "strong"
    assert result.suggested_instrument == "NIFTY_CE"
    assert result.direction == "BUY"


# ---------------------------------------------------------------------------
# Test 2: HOLD direction → score < 50, tier = 'skip', instrument = 'NONE'
# ---------------------------------------------------------------------------

def test_hold_always_below_50():
    """HOLD direction always produces score < 50 regardless of technicals."""
    result = SignalScorer.score(
        direction="HOLD",
        conviction=90,
        signals={
            "rsi": 25,
            "supertrend": "bullish",
            "vix_regime": "low",
            "oi_sentiment": "bullish",
        },
        instrument="NIFTY",
    )
    assert result.score < 50, f"HOLD must always be < 50, got {result.score}"
    assert result.tier == "skip"
    assert result.suggested_instrument == "NONE"


# ---------------------------------------------------------------------------
# Test 3: SELL with no technicals aligned → score = 30.6, skip, BANKNIFTY_PE
# ---------------------------------------------------------------------------

def test_sell_no_technicals_aligned():
    """SELL + no aligned technicals → sentiment only → 30.6, tier='skip', BANKNIFTY_PE."""
    result = SignalScorer.score(
        direction="SELL",
        conviction=60,
        signals={
            "rsi": 50,              # neutral (not > 70)
            "supertrend": "bullish",  # bullish opposes SELL → not aligned
            "vix_regime": "normal",   # neutral → not aligned
            # oi_sentiment absent
        },
        instrument="BANKNIFTY",
    )
    # sentiment_score = 60 * 0.85 * 0.60 = 30.6
    # technical_score = 0
    assert abs(result.score - 30.6) < 0.1, f"Expected ~30.6, got {result.score}"
    assert result.tier == "skip"
    assert result.suggested_instrument == "BANKNIFTY_PE"


# ---------------------------------------------------------------------------
# Test 4: BUY with 1 technical aligned → score ≈ 38.1, skip
# ---------------------------------------------------------------------------

def test_buy_one_technical_aligned():
    """BUY + only supertrend aligned → score ≈ 38.1, tier='skip'."""
    result = SignalScorer.score(
        direction="BUY",
        conviction=55,
        signals={
            "rsi": 50,              # neutral, not < 30
            "supertrend": "bullish",  # aligned with BUY
            "vix_regime": "normal",   # neutral
            # oi_sentiment absent
        },
        instrument="NIFTY",
    )
    # sentiment = 55 * 0.85 * 0.60 = 28.05
    # technical = 1 * 25 * 0.40 = 10.0
    # score = 38.05 → round to 38.1
    assert abs(result.score - 38.1) < 0.2, f"Expected ~38.1, got {result.score}"
    assert result.tier == "skip"


# ---------------------------------------------------------------------------
# Test 5: ScoreResult dataclass fields
# ---------------------------------------------------------------------------

def test_score_result_fields():
    """score() returns a ScoreResult with all required fields."""
    result = SignalScorer.score(
        direction="BUY",
        conviction=70,
        signals={"rsi": 28, "supertrend": "bullish", "vix_regime": "low"},
        instrument="NIFTY",
    )
    assert hasattr(result, "score")
    assert hasattr(result, "tier")
    assert hasattr(result, "direction")
    assert hasattr(result, "contributing_factors")
    assert hasattr(result, "suggested_instrument")
    assert isinstance(result.score, float)
    assert isinstance(result.tier, str)
    assert isinstance(result.direction, str)
    assert isinstance(result.contributing_factors, list)
    assert isinstance(result.suggested_instrument, str)
    # contributing_factors must include agent conviction
    assert any("conviction" in f.lower() for f in result.contributing_factors), (
        "contributing_factors must include agent conviction entry"
    )


# ---------------------------------------------------------------------------
# Test 6: Clamp — score never < 0 or > 100
# ---------------------------------------------------------------------------

def test_score_clamp_max():
    """Score is clamped to [0, 100] — never exceeds 100."""
    result = SignalScorer.score(
        direction="STRONG_BUY",
        conviction=100,
        signals={
            "rsi": 20,
            "supertrend": "bullish",
            "vix_regime": "low",
            "oi_sentiment": "bullish",
        },
        instrument="NIFTY",
    )
    assert result.score <= 100.0


def test_score_clamp_min():
    """Score is clamped to [0, 100] — never goes below 0."""
    result = SignalScorer.score(
        direction="HOLD",
        conviction=0,
        signals={},
        instrument="NIFTY",
    )
    assert result.score >= 0.0


# ---------------------------------------------------------------------------
# Test 7: STRONG_BUY with full alignment → score = 100.0
# ---------------------------------------------------------------------------

def test_strong_buy_full_alignment():
    """STRONG_BUY + full alignment → score = 100, tier = 'strong'."""
    result = SignalScorer.score(
        direction="STRONG_BUY",
        conviction=100,
        signals={
            "rsi": 20,
            "supertrend": "bullish",
            "vix_regime": "low",
            "oi_sentiment": "bullish",
        },
        instrument="NIFTY",
    )
    # sentiment = 100 * 1.0 * 0.60 = 60
    # technical = 4 * 25 * 0.40 = 40
    # score = 100.0
    assert result.score == 100.0, f"Expected 100.0, got {result.score}"
    assert result.tier == "strong"


# ---------------------------------------------------------------------------
# Test 8: Tier boundary checks
# ---------------------------------------------------------------------------

def test_tier_boundary_strong():
    """Score > 70 → tier = 'strong'."""
    result = SignalScorer.score(
        direction="STRONG_BUY",
        conviction=100,
        signals={
            "rsi": 20,
            "supertrend": "bullish",
            "vix_regime": "low",
            "oi_sentiment": "bullish",
        },
        instrument="NIFTY",
    )
    assert result.tier == "strong"
    assert result.score > 70


def test_tier_boundary_moderate():
    """Score in [50, 70] → tier = 'moderate'."""
    # BUY + conviction=80 + 1 technical aligned (supertrend)
    # sentiment = 80 * 0.85 * 0.60 = 40.8
    # technical = 1 * 25 * 0.40 = 10
    # score = 50.8 → moderate
    result = SignalScorer.score(
        direction="BUY",
        conviction=80,
        signals={
            "rsi": 50,              # neutral
            "supertrend": "bullish",  # aligned
            "vix_regime": "normal",   # neutral
        },
        instrument="NIFTY",
    )
    assert result.tier == "moderate", f"Expected 'moderate', got '{result.tier}' (score={result.score})"
    assert 50 <= result.score <= 70


def test_tier_boundary_skip():
    """Score < 50 → tier = 'skip'."""
    result = SignalScorer.score(
        direction="SELL",
        conviction=60,
        signals={"rsi": 50, "supertrend": "bullish", "vix_regime": "normal"},
        instrument="BANKNIFTY",
    )
    assert result.tier == "skip"
    assert result.score < 50


# ---------------------------------------------------------------------------
# Test 9: Instrument mapping — all direction + instrument combos
# ---------------------------------------------------------------------------

def test_instrument_mapping_nifty_buy():
    result = SignalScorer.score("BUY", 70, {"rsi": 50}, "NIFTY")
    assert result.suggested_instrument == "NIFTY_CE"


def test_instrument_mapping_nifty_strong_buy():
    result = SignalScorer.score("STRONG_BUY", 70, {"rsi": 50}, "NIFTY")
    assert result.suggested_instrument == "NIFTY_CE"


def test_instrument_mapping_nifty_sell():
    result = SignalScorer.score("SELL", 70, {"rsi": 50}, "NIFTY")
    assert result.suggested_instrument == "NIFTY_PE"


def test_instrument_mapping_nifty_strong_sell():
    result = SignalScorer.score("STRONG_SELL", 70, {"rsi": 50}, "NIFTY")
    assert result.suggested_instrument == "NIFTY_PE"


def test_instrument_mapping_banknifty_buy():
    result = SignalScorer.score("BUY", 70, {"rsi": 50}, "BANKNIFTY")
    assert result.suggested_instrument == "BANKNIFTY_CE"


def test_instrument_mapping_banknifty_sell():
    result = SignalScorer.score("SELL", 70, {"rsi": 50}, "BANKNIFTY")
    assert result.suggested_instrument == "BANKNIFTY_PE"


def test_instrument_mapping_hold_any():
    """HOLD always produces NONE regardless of instrument."""
    result_nifty = SignalScorer.score("HOLD", 70, {"rsi": 50}, "NIFTY")
    result_banknifty = SignalScorer.score("HOLD", 70, {"rsi": 50}, "BANKNIFTY")
    assert result_nifty.suggested_instrument == "NONE"
    assert result_banknifty.suggested_instrument == "NONE"


def test_instrument_case_insensitive():
    """Instrument param is case-insensitive."""
    result_lower = SignalScorer.score("BUY", 70, {"rsi": 50}, "nifty")
    result_upper = SignalScorer.score("BUY", 70, {"rsi": 50}, "NIFTY")
    assert result_lower.suggested_instrument == result_upper.suggested_instrument == "NIFTY_CE"


# ---------------------------------------------------------------------------
# Test 10: Unknown direction treated as HOLD
# ---------------------------------------------------------------------------

def test_unknown_direction_treated_as_hold():
    """Unknown direction string → treated as HOLD (safe default)."""
    result = SignalScorer.score(
        direction="SIDEWAYS",
        conviction=80,
        signals={"rsi": 25, "supertrend": "bullish"},
        instrument="NIFTY",
    )
    assert result.score < 50, "Unknown direction should behave like HOLD"
    assert result.suggested_instrument == "NONE"


# ---------------------------------------------------------------------------
# Test 11: contributing_factors includes aligned signals
# ---------------------------------------------------------------------------

def test_contributing_factors_populated():
    """contributing_factors lists only aligned signals plus agent conviction."""
    result = SignalScorer.score(
        direction="BUY",
        conviction=72.0,
        signals={
            "rsi": 28.3,
            "supertrend": "bullish",
            "vix_regime": "normal",   # not aligned → should not appear
            "oi_sentiment": "bearish", # opposes BUY → should not appear
        },
        instrument="NIFTY",
    )
    text = " ".join(result.contributing_factors).lower()
    assert "rsi" in text, "RSI oversold should appear in contributing_factors"
    assert "supertrend" in text, "Supertrend bullish should appear in contributing_factors"
    assert "72.0" in " ".join(result.contributing_factors) or "72" in " ".join(result.contributing_factors)


# ---------------------------------------------------------------------------
# Test 12: SELL technical alignment (rsi > 70, supertrend bearish, vix high)
# ---------------------------------------------------------------------------

def test_sell_full_alignment():
    """SELL + rsi > 70 + bearish supertrend + high vix → 3 technicals aligned."""
    result = SignalScorer.score(
        direction="SELL",
        conviction=80,
        signals={
            "rsi": 75,              # > 70 supports SELL
            "supertrend": "bearish",  # supports SELL
            "vix_regime": "high",     # supports SELL
        },
        instrument="NIFTY",
    )
    # sentiment = 80 * 0.85 * 0.60 = 40.8
    # technical = 3 * 25 * 0.40 = 30
    # score = 70.8 → strong
    assert abs(result.score - 70.8) < 0.1, f"Expected ~70.8, got {result.score}"
    assert result.tier == "strong"
    assert result.suggested_instrument == "NIFTY_PE"


# ---------------------------------------------------------------------------
# Test 13: Missing signals dict → no crash (empty signals = 0 technicals)
# ---------------------------------------------------------------------------

def test_empty_signals_no_crash():
    """score() handles empty signals dict without error."""
    result = SignalScorer.score(
        direction="BUY",
        conviction=50,
        signals={},
        instrument="NIFTY",
    )
    assert isinstance(result, ScoreResult)
    assert result.score >= 0


# ---------------------------------------------------------------------------
# Test 14: OI sentiment absent → treated as neutral (no crash)
# ---------------------------------------------------------------------------

def test_oi_absent_neutral():
    """Absent oi_sentiment key is treated as neutral — no crash, 0 contribution."""
    result_with = SignalScorer.score(
        direction="BUY",
        conviction=60,
        signals={"rsi": 25, "supertrend": "bullish", "vix_regime": "low", "oi_sentiment": "bullish"},
        instrument="NIFTY",
    )
    result_without = SignalScorer.score(
        direction="BUY",
        conviction=60,
        signals={"rsi": 25, "supertrend": "bullish", "vix_regime": "low"},
        instrument="NIFTY",
    )
    # With OI aligned should score higher than without
    assert result_with.score > result_without.score
