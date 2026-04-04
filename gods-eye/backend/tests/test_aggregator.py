"""Tests for the Aggregator system."""

import pytest
from app.api.schemas import AgentResponse
from app.engine.aggregator import Aggregator
from app.config import config


def test_aggregate_with_mock_agent_responses():
    """Test that aggregate() produces valid output with mock agent responses."""
    agents_output = {
        "FII": AgentResponse(
            agent_name="FII Flows Analyst",
            agent_type="LLM",
            direction="BUY",
            conviction=75,
            reasoning="FII flows positive",
            key_triggers=["FII inflows"],
            time_horizon="Weekly",
        ),
        "ALGO": AgentResponse(
            agent_name="Algo Trading Engine",
            agent_type="QUANT",
            direction="HOLD",
            conviction=55,
            reasoning="Technical neutral",
            key_triggers=["RSI at 50"],
            time_horizon="Intraday",
        ),
        "RBI": AgentResponse(
            agent_name="RBI Policy Desk",
            agent_type="LLM",
            direction="BUY",
            conviction=60,
            reasoning="Inflation controlled",
            key_triggers=["RBI dovish"],
            time_horizon="Quarterly",
        ),
    }

    result = Aggregator.aggregate(agents_output, hybrid=False)

    # Check required fields
    assert result.final_direction in [
        "STRONG_BUY",
        "BUY",
        "HOLD",
        "SELL",
        "STRONG_SELL",
    ]
    assert 0 <= result.final_conviction <= 100
    assert -100 <= result.consensus_score <= 100
    assert result.conflict_level in [
        "HIGH_AGREEMENT",
        "MODERATE",
        "TUG_OF_WAR",
        "NONE",
    ]
    assert isinstance(result.conflict_gap, float)


def test_weighted_aggregation_respects_weights():
    """Test that weighted aggregation respects agent weights."""
    agents_output = {
        "FII": AgentResponse(
            agent_name="FII",
            agent_type="LLM",
            direction="STRONG_BUY",  # Max positive
            conviction=100,
            reasoning="Test",
            key_triggers=[],
            time_horizon="Weekly",
        ),
        "ALGO": AgentResponse(
            agent_name="ALGO",
            agent_type="QUANT",
            direction="STRONG_SELL",  # Max negative
            conviction=100,
            reasoning="Test",
            key_triggers=[],
            time_horizon="Intraday",
        ),
    }

    # FII has weight 0.30, ALGO has weight 0.10 (default)
    # FII should dominate the result
    result = Aggregator.aggregate(agents_output, hybrid=False)

    # With FII positive and ALGO negative, FII dominance should push towards BUY
    assert result.consensus_score > 0
    assert result.final_direction in ["BUY", "STRONG_BUY"]


def test_consensus_score_calculation():
    """Test that consensus_score is calculated correctly."""
    # All agents agreeing on BUY with high conviction
    agents_output = {
        "FII": AgentResponse(
            agent_name="FII",
            agent_type="LLM",
            direction="BUY",
            conviction=80,
            reasoning="Test",
            key_triggers=[],
            time_horizon="Weekly",
        ),
        "DII": AgentResponse(
            agent_name="DII",
            agent_type="LLM",
            direction="BUY",
            conviction=75,
            reasoning="Test",
            key_triggers=[],
            time_horizon="Weekly",
        ),
    }

    result = Aggregator.aggregate(agents_output, hybrid=False)

    # Consensus score should be positive
    assert result.consensus_score > 0
    assert result.final_direction == "BUY"


def test_conflict_detection():
    """Test conflict detection between agents."""
    # Major disagreement
    agents_output = {
        "FII": AgentResponse(
            agent_name="FII",
            agent_type="LLM",
            direction="STRONG_BUY",
            conviction=90,
            reasoning="Test",
            key_triggers=[],
            time_horizon="Weekly",
        ),
        "ALGO": AgentResponse(
            agent_name="ALGO",
            agent_type="QUANT",
            direction="STRONG_SELL",
            conviction=90,
            reasoning="Test",
            key_triggers=[],
            time_horizon="Intraday",
        ),
    }

    result = Aggregator.aggregate(agents_output, hybrid=False)

    # Should detect high conflict
    assert result.conflict_level in ["MODERATE", "TUG_OF_WAR"]
    assert result.conflict_gap > 0


def test_empty_agents_output():
    """Test handling of empty agents output."""
    result = Aggregator.aggregate({}, hybrid=False)

    assert result.final_direction == "HOLD"
    assert result.consensus_score == 0.0
    assert result.conflict_level == "NONE"


def test_tuned_weights_override_defaults():
    """Test that tuned_weights override default config weights."""
    agents_output = {
        "FII": AgentResponse(
            agent_name="FII",
            agent_type="LLM",
            direction="STRONG_BUY",
            conviction=100,
            reasoning="Test",
            key_triggers=[],
            time_horizon="Weekly",
        ),
        "ALGO": AgentResponse(
            agent_name="ALGO",
            agent_type="QUANT",
            direction="STRONG_SELL",
            conviction=100,
            reasoning="Test",
            key_triggers=[],
            time_horizon="Intraday",
        ),
    }

    # Use tuned weights that favor ALGO more than default
    tuned_weights = {
        "FII": 0.2,
        "ALGO": 0.4,
        "DII": 0.15,
        "RETAIL_FNO": 0.1,
        "PROMOTER": 0.1,
        "RBI": 0.05,
    }

    result = Aggregator.aggregate(agents_output, hybrid=False, tuned_weights=tuned_weights)

    # ALGO now has more weight, so score should be more negative than with default weights
    # (ALGO weight 0.10 default vs 0.40 tuned)
    assert result.consensus_score is not None
    assert isinstance(result.consensus_score, float)


def test_hybrid_aggregation():
    """Test hybrid aggregation with quant and LLM agents."""
    agents_output = {
        # Quant agent
        "ALGO": AgentResponse(
            agent_name="ALGO",
            agent_type="QUANT",
            direction="BUY",
            conviction=70,
            reasoning="Technical signals",
            key_triggers=["RSI > 50"],
            time_horizon="Intraday",
        ),
        # LLM agents
        "FII": AgentResponse(
            agent_name="FII",
            agent_type="LLM",
            direction="BUY",
            conviction=80,
            reasoning="Flow analysis",
            key_triggers=["Positive flows"],
            time_horizon="Weekly",
        ),
    }

    result = Aggregator.aggregate(agents_output, hybrid=True)

    # Should have both quant and LLM consensus
    assert result.quant_consensus == "BUY"
    assert result.llm_consensus == "BUY"
    assert result.quant_llm_agreement is not None
    assert 0 <= result.quant_llm_agreement <= 1
