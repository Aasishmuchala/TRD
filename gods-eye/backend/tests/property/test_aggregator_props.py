"""Property-based tests for app.engine.aggregator.Aggregator."""

from __future__ import annotations

from typing import Dict, List

from hypothesis import HealthCheck, assume, given, settings, strategies as st

from app.api.schemas import AgentResponse
from app.config import config
from app.engine.aggregator import Aggregator


# Known agent names — use the configured weight map so weights actually apply.
AGENT_NAMES: List[str] = list(config.AGENT_WEIGHTS.keys())
QUANT_AGENTS = {"ALGO"}  # only ALGO is QUANT per repo
DIRECTIONS = ["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]
FLIP = {
    "STRONG_BUY": "STRONG_SELL",
    "BUY": "SELL",
    "HOLD": "HOLD",
    "SELL": "BUY",
    "STRONG_SELL": "STRONG_BUY",
}


def _make_resp(name: str, direction: str, conviction: float) -> AgentResponse:
    return AgentResponse(
        agent_name=name,
        agent_type="QUANT" if name in QUANT_AGENTS else "LLM",
        direction=direction,
        conviction=conviction,
        reasoning="prop-test",
        key_triggers=["x"],
        time_horizon="Intraday",
    )


@st.composite
def agents_dict(draw, min_agents=1, max_agents=None):
    max_agents = max_agents or len(AGENT_NAMES)
    n = draw(st.integers(min_value=min_agents, max_value=max_agents))
    names = draw(st.lists(st.sampled_from(AGENT_NAMES), min_size=n, max_size=n, unique=True))
    out: Dict[str, AgentResponse] = {}
    for name in names:
        d = draw(st.sampled_from(DIRECTIONS))
        c = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False))
        out[name] = _make_resp(name, d, c)
    return out


# ---- Output-shape invariants --------------------------------------------

@given(agents=agents_dict())
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_final_direction_is_in_allowed_set(agents):
    """final_direction is always one of the 5 known direction labels."""
    r = Aggregator.aggregate(agents, hybrid=True)
    assert r.final_direction in DIRECTIONS


@given(agents=agents_dict(), hybrid=st.booleans())
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_consensus_score_within_bounds(agents, hybrid):
    """consensus_score is always within [-100, 100]."""
    r = Aggregator.aggregate(agents, hybrid=hybrid)
    assert -100.0 <= r.consensus_score <= 100.0


@given(agents=agents_dict(), hybrid=st.booleans())
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_final_conviction_within_bounds(agents, hybrid):
    """final_conviction is always within [0, 100]."""
    r = Aggregator.aggregate(agents, hybrid=hybrid)
    assert 0.0 <= r.final_conviction <= 100.0


@given(agents=agents_dict(), hybrid=st.booleans())
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_conflict_gap_non_negative(agents, hybrid):
    """conflict_gap is always >= 0 (it is max-min of signed scores)."""
    r = Aggregator.aggregate(agents, hybrid=hybrid)
    assert r.conflict_gap >= 0.0


def test_empty_input_returns_neutral_hold():
    """Empty agent dict yields the neutral HOLD result."""
    r = Aggregator.aggregate({}, hybrid=True)
    assert r.final_direction == "HOLD"
    assert r.consensus_score == 0.0


# ---- Semantic invariants ------------------------------------------------

@given(conv=st.floats(min_value=90.0, max_value=100.0))
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_unanimous_strong_buy_gives_positive_score(conv):
    """If every agent says STRONG_BUY with high conviction, consensus_score > 0."""
    agents = {n: _make_resp(n, "STRONG_BUY", conv) for n in AGENT_NAMES}
    r = Aggregator.aggregate(agents, hybrid=False)
    assert r.consensus_score > 0
    assert r.final_direction in ("BUY", "STRONG_BUY", "HOLD")  # HOLD only via conviction floor


@given(conv=st.floats(min_value=90.0, max_value=100.0))
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_unanimous_strong_sell_gives_negative_score(conv):
    """If every agent says STRONG_SELL with high conviction, consensus_score < 0."""
    agents = {n: _make_resp(n, "STRONG_SELL", conv) for n in AGENT_NAMES}
    r = Aggregator.aggregate(agents, hybrid=False)
    assert r.consensus_score < 0
    assert r.final_direction in ("SELL", "STRONG_SELL", "HOLD")


@given(agents=agents_dict(min_agents=2))
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_direction_flip_negates_consensus_score(agents):
    """Flipping every BUY<->SELL (and STRONG variants) negates the consensus score."""
    flipped = {
        n: _make_resp(n, FLIP[a.direction], a.conviction)
        for n, a in agents.items()
    }
    r1 = Aggregator.aggregate(agents, hybrid=False)
    r2 = Aggregator.aggregate(flipped, hybrid=False)
    # Within float tolerance after clamping and float math
    assert abs(r1.consensus_score + r2.consensus_score) < 1e-6


@given(agents=agents_dict())
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_all_hold_yields_hold(agents):
    """If every agent says HOLD, the final direction is HOLD."""
    hold_agents = {n: _make_resp(n, "HOLD", a.conviction) for n, a in agents.items()}
    r = Aggregator.aggregate(hold_agents, hybrid=False)
    assert r.final_direction == "HOLD"
    assert r.consensus_score == 0.0


@given(agents=agents_dict(min_agents=2))
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_hybrid_quant_llm_agreement_in_unit_interval(agents):
    """quant_llm_agreement (when set by hybrid path) is in [0, 1]."""
    # Force hybrid path: ensure both ALGO (quant) and at least one LLM are present.
    agents = dict(agents)
    if "ALGO" not in agents:
        agents["ALGO"] = _make_resp("ALGO", "BUY", 60.0)
    if not any(n != "ALGO" for n in agents):
        agents["FII"] = _make_resp("FII", "BUY", 60.0)
    r = Aggregator.aggregate(agents, hybrid=True)
    if r.quant_llm_agreement is not None:
        assert 0.0 <= r.quant_llm_agreement <= 1.0


@given(agents=agents_dict())
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_conviction_floor_forces_hold_when_low(agents):
    """If every agent has conviction below CONVICTION_FLOOR, final_direction must be HOLD."""
    # Force conviction strictly below floor
    floor = config.CONVICTION_FLOOR
    low_agents = {
        n: _make_resp(n, a.direction, max(0.0, floor - 10.0))
        for n, a in agents.items()
    }
    r = Aggregator.aggregate(low_agents, hybrid=False)
    # final_conviction is avg*0.9 of <=floor-10 -> below floor -> HOLD via floor logic
    if r.final_conviction < config.CONVICTION_FLOOR and r.final_direction != "HOLD":
        # Should have been forced to HOLD
        assert False, f"Conviction {r.final_conviction} < floor {floor} but direction {r.final_direction}"


@given(agents=agents_dict())
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_conflict_level_in_known_set(agents):
    """conflict_level is one of the documented labels."""
    r = Aggregator.aggregate(agents, hybrid=True)
    assert r.conflict_level in ("HIGH_AGREEMENT", "MODERATE", "TUG_OF_WAR", "NONE")
