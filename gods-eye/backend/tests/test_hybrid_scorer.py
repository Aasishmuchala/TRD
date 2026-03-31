"""TDD tests for HybridScorer — Phase 12 Plan 01.

Tests cover:
  1. Formula correctness (60/40 blend)
  2. Formula clamp at 100
  3. Confirm verdict — conviction unchanged, tradeable=True
  4. Adjust verdict — conviction reduced, direction unchanged
  5. Adjust cannot flip direction (quant wins)
  6. Skip verdict — tradeable=False, tier="skip", conviction=0
  7. HOLD quant + BUY agents — final direction=HOLD (quant wins)
  8. HybridResult has all required fields
"""

import pytest
from app.engine.hybrid_scorer import HybridScorer, HybridResult, ValidatorVerdict
from app.engine.quant_signal_engine import QuantScoreResult
from app.api.schemas import AgentResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_quant_result(
    total_score: int = 70,
    direction: str = "BUY",
    buy_points: int = 70,
    sell_points: int = 0,
    tier: str = "strong",
    instrument_hint: str = "NIFTY_CE",
) -> QuantScoreResult:
    return QuantScoreResult(
        total_score=total_score,
        direction=direction,
        buy_points=buy_points,
        sell_points=sell_points,
        factors={},
        tier=tier,
        instrument_hint=instrument_hint,
    )


def make_agent(
    name: str = "FII",
    direction: str = "BUY",
    conviction: float = 60.0,
) -> AgentResponse:
    return AgentResponse(
        agent_name=name,
        agent_type="LLM",
        direction=direction,
        conviction=conviction,
        reasoning="Test",
        key_triggers=["factor"],
        time_horizon="Intraday",
    )


def make_validator(
    verdict: str = "confirm",
    reasoning: str = "Looks good",
    adjustment_amount: float = 0.0,
) -> ValidatorVerdict:
    return ValidatorVerdict(
        verdict=verdict,
        reasoning=reasoning,
        adjustment_amount=adjustment_amount,
    )


# ---------------------------------------------------------------------------
# Test 1: Formula correctness
# quant=70, agents avg=60 → hybrid = 70*0.6 + 60*0.4 = 42+24 = 66.0
# ---------------------------------------------------------------------------

def test_formula_correct():
    quant = make_quant_result(total_score=70, direction="BUY", buy_points=70, sell_points=0)
    # Single agent with conviction=60, direction=BUY → consensus=60, direction=BUY
    agents = {"agent1": make_agent(direction="BUY", conviction=60.0)}
    validator = make_validator(verdict="confirm")

    result = HybridScorer.fuse(quant, agents, validator)

    assert result.hybrid_score == 66.0, (
        f"Expected 66.0 (70*0.6 + 60*0.4), got {result.hybrid_score}"
    )


# ---------------------------------------------------------------------------
# Test 2: Formula clamp — quant=100, agents avg=100 → hybrid=100.0 (not >100)
# ---------------------------------------------------------------------------

def test_formula_clamp():
    quant = make_quant_result(total_score=100, direction="BUY", buy_points=100, sell_points=0, tier="strong")
    agents = {"agent1": make_agent(direction="BUY", conviction=100.0)}
    validator = make_validator(verdict="confirm")

    result = HybridScorer.fuse(quant, agents, validator)

    assert result.hybrid_score == 100.0, (
        f"Expected 100.0 (clamped), got {result.hybrid_score}"
    )
    assert result.hybrid_score <= 100.0


# ---------------------------------------------------------------------------
# Test 3: Confirm verdict — conviction unchanged, tradeable=True
# ---------------------------------------------------------------------------

def test_confirm_verdict_conviction_unchanged():
    quant = make_quant_result(total_score=70, direction="BUY", tier="strong")
    agents = {"agent1": make_agent(direction="BUY", conviction=60.0)}
    validator = make_validator(verdict="confirm")

    result = HybridScorer.fuse(quant, agents, validator)

    # hybrid_score = 70*0.6 + 60*0.4 = 66.0; conviction = hybrid_score = 66.0
    assert result.tradeable is True
    assert result.validator_verdict == "confirm"
    # conviction should NOT be reduced
    assert result.conviction == result.hybrid_score


# ---------------------------------------------------------------------------
# Test 4: Adjust verdict — conviction reduced by adjustment_amount, direction unchanged
# hybrid=66, conviction=66, adjust by 20 → conviction=46, tradeable=True
# ---------------------------------------------------------------------------

def test_adjust_verdict_reduces_conviction():
    quant = make_quant_result(total_score=70, direction="BUY", tier="strong")
    agents = {"agent1": make_agent(direction="BUY", conviction=60.0)}
    # hybrid_score will be 66.0; adjust by 20
    validator = make_validator(verdict="adjust", adjustment_amount=20.0)

    result = HybridScorer.fuse(quant, agents, validator)

    assert result.conviction == 46.0, (
        f"Expected conviction=46.0 (66.0 - 20.0), got {result.conviction}"
    )
    assert result.tradeable is True
    assert result.direction == "BUY"  # direction unchanged
    assert result.validator_verdict == "adjust"


# ---------------------------------------------------------------------------
# Test 5: Adjust cannot flip direction
# quant direction=BUY, agent consensus=SELL → final direction=BUY (quant wins)
# ---------------------------------------------------------------------------

def test_adjust_cannot_flip_direction():
    quant = make_quant_result(total_score=70, direction="BUY", buy_points=70, sell_points=0, tier="strong")
    # Agents all bearish — consensus will be SELL
    agents = {
        "agent1": make_agent(direction="SELL", conviction=80.0),
        "agent2": make_agent(direction="SELL", conviction=70.0),
    }
    validator = make_validator(verdict="adjust", adjustment_amount=10.0)

    result = HybridScorer.fuse(quant, agents, validator)

    # Direction must stay BUY regardless of agent consensus
    assert result.direction == "BUY", (
        f"Direction must be quant direction BUY, got {result.direction}"
    )


# ---------------------------------------------------------------------------
# Test 6: Skip verdict — tradeable=False, tier="skip", conviction=0
# ---------------------------------------------------------------------------

def test_skip_verdict():
    quant = make_quant_result(total_score=70, direction="BUY", tier="strong")
    agents = {"agent1": make_agent(direction="BUY", conviction=60.0)}
    validator = make_validator(verdict="skip", reasoning="Market conditions unfavourable")

    result = HybridScorer.fuse(quant, agents, validator)

    assert result.tradeable is False, "Skip verdict must produce tradeable=False"
    assert result.tier == "skip", f"Skip verdict must produce tier='skip', got {result.tier}"
    assert result.conviction == 0, f"Skip verdict must set conviction=0, got {result.conviction}"
    assert result.validator_verdict == "skip"


# ---------------------------------------------------------------------------
# Test 7: HOLD quant + BUY agents → final direction=HOLD (quant wins)
# ---------------------------------------------------------------------------

def test_hold_quant_wins_over_buy_agents():
    quant = make_quant_result(
        total_score=40,
        direction="HOLD",
        buy_points=40,
        sell_points=40,
        tier="skip",
        instrument_hint="NONE",
    )
    agents = {
        "agent1": make_agent(direction="BUY", conviction=90.0),
        "agent2": make_agent(direction="STRONG_BUY", conviction=85.0),
    }
    validator = make_validator(verdict="confirm")

    result = HybridScorer.fuse(quant, agents, validator)

    assert result.direction == "HOLD", (
        f"Quant HOLD must override agent BUY consensus, got {result.direction}"
    )


# ---------------------------------------------------------------------------
# Test 8: HybridResult has all 7 required fields
# ---------------------------------------------------------------------------

def test_hybrid_result_has_all_required_fields():
    quant = make_quant_result()
    agents = {"agent1": make_agent()}
    validator = make_validator()

    result = HybridScorer.fuse(quant, agents, validator)

    # Check all 7 required fields per plan spec
    assert hasattr(result, "direction"), "Missing: direction"
    assert hasattr(result, "hybrid_score"), "Missing: hybrid_score"
    assert hasattr(result, "quant_breakdown"), "Missing: quant_breakdown"
    assert hasattr(result, "agent_breakdown"), "Missing: agent_breakdown"
    assert hasattr(result, "validator_verdict"), "Missing: validator_verdict"
    assert hasattr(result, "validator_reasoning"), "Missing: validator_reasoning"
    assert hasattr(result, "instrument_hint"), "Missing: instrument_hint"

    # Validate types and value ranges
    assert isinstance(result.direction, str)
    assert 0.0 <= result.hybrid_score <= 100.0
    assert isinstance(result.quant_breakdown, dict)
    assert isinstance(result.agent_breakdown, dict)
    assert result.validator_verdict in ("confirm", "adjust", "skip")
    assert isinstance(result.validator_reasoning, str)
    assert isinstance(result.instrument_hint, str)
