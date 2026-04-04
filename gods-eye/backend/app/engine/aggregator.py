"""Aggregator for weighted consensus and conflict detection."""

from typing import Dict
from app.api.schemas import AgentResponse, AggregatorResult
from app.config import config


class Aggregator:
    """Aggregates agent outputs into final market direction."""

    @staticmethod
    def aggregate(
        agents_output: Dict[str, AgentResponse],
        hybrid: bool = True,
        tuned_weights: Dict[str, float] = None,
    ) -> AggregatorResult:
        """Compute weighted consensus from all agents.

        Args:
            agents_output: Dict of agent responses
            hybrid: Use hybrid quant/LLM aggregation
            tuned_weights: Optional accuracy-tuned weights from FeedbackEngine.
                          Falls back to config.AGENT_WEIGHTS if None.
        """
        if not agents_output:
            return Aggregator._neutral_result()

        # Use tuned weights if provided, otherwise config defaults
        if tuned_weights:
            # Temporarily override config weights for this aggregation
            original_weights = dict(config.AGENT_WEIGHTS)
            config.AGENT_WEIGHTS = tuned_weights

        # Separate quant and LLM agents
        quant_agents = {}
        llm_agents = {}

        for agent_name, response in agents_output.items():
            if response.agent_type == "QUANT":
                quant_agents[agent_name] = response
            else:
                llm_agents[agent_name] = response

        if hybrid and quant_agents and llm_agents:
            result = Aggregator._hybrid_aggregate(
                quant_agents, llm_agents, agents_output
            )
        else:
            result = Aggregator._standard_aggregate(agents_output)

        # Restore original weights if we overrode them
        if tuned_weights:
            config.AGENT_WEIGHTS = original_weights

        # Conviction floor: if agents aren't confident enough, sit out.
        # This prevents trading on uncertain days even when the score
        # clears the HOLD band.
        if (result.final_direction != "HOLD"
                and result.final_conviction < config.CONVICTION_FLOOR):
            result.final_direction = "HOLD"

        return result

    @staticmethod
    def _standard_aggregate(agents_output: Dict[str, AgentResponse]) -> AggregatorResult:
        """Standard weighted aggregation."""
        direction_scores = {
            "STRONG_BUY": 1.0,
            "BUY": 0.6,
            "HOLD": 0.0,
            "SELL": -0.6,
            "STRONG_SELL": -1.0,
        }

        total_score = 0.0
        total_weight = 0.0
        direction_distribution = {}

        for agent_name, response in agents_output.items():
            agent_weight = config.AGENT_WEIGHTS.get(agent_name, 0.1)
            score = direction_scores.get(response.direction, 0.0)

            # Conviction adjustment (0-1 scale)
            conviction_factor = (response.conviction / 100.0) ** 0.8

            # Reproducibility bonus: deterministic quant agents get 1.2×,
            # stochastic LLM agents get 0.9× (they vary across samples)
            if response.reproducible:
                conviction_factor *= 1.2
            else:
                conviction_factor *= 0.9

            weighted_score = score * agent_weight * conviction_factor
            total_score += weighted_score
            total_weight += agent_weight

            # Track distribution
            direction_distribution[agent_name] = {
                "direction": response.direction,
                "conviction": response.conviction,
                "weight": agent_weight,
            }

        # Normalize score
        if total_weight > 0:
            consensus_score = (total_score / total_weight) * 100
        else:
            consensus_score = 0.0

        # Clamp to -100, 100
        consensus_score = max(-100, min(100, consensus_score))

        # Convert to final direction
        final_direction = Aggregator._score_to_direction(consensus_score)

        # Compute final conviction
        avg_conviction = sum(r.conviction for r in agents_output.values()) / len(
            agents_output
        )
        final_conviction = min(100, avg_conviction * 0.9)  # Slight penalty

        # Detect conflict
        conflict_level, conflict_gap = Aggregator._detect_conflict(agents_output)

        return AggregatorResult(
            final_direction=final_direction,
            final_conviction=final_conviction,
            consensus_score=consensus_score,
            conflict_level=conflict_level,
            conflict_gap=conflict_gap,
            quant_consensus="N/A",
            llm_consensus="N/A",
            agreement_boost=1.0,
            agent_breakdown=direction_distribution,
        )

    @staticmethod
    def _hybrid_aggregate(
        quant_agents: Dict[str, AgentResponse],
        llm_agents: Dict[str, AgentResponse],
        all_agents: Dict[str, AgentResponse],
    ) -> AggregatorResult:
        """Hybrid aggregation with quant/LLM weighting."""

        # Quant consensus (0.45 weight)
        quant_result = Aggregator._standard_aggregate(quant_agents)
        quant_score = quant_result.consensus_score

        # LLM consensus (0.55 weight)
        llm_result = Aggregator._standard_aggregate(llm_agents)
        llm_score = llm_result.consensus_score

        # Check agreement between quant and LLM
        quant_dir = quant_result.final_direction
        llm_dir = llm_result.final_direction

        direction_scores = {
            "STRONG_BUY": 2,
            "BUY": 1,
            "HOLD": 0,
            "SELL": -1,
            "STRONG_SELL": -2,
        }

        quant_score_num = direction_scores.get(quant_dir, 0)
        llm_score_num = direction_scores.get(llm_dir, 0)

        # Agreement detection
        agreement_gap = abs(quant_score_num - llm_score_num)

        if agreement_gap <= 0.5:
            # Strong agreement
            agreement_boost = 1.15
        elif agreement_gap <= 2:
            # Moderate agreement
            agreement_boost = 1.0
        else:
            # Disagreement
            agreement_boost = 0.70

        # Combined score
        hybrid_score = (quant_score * 0.45 + llm_score * 0.55) * agreement_boost
        hybrid_score = max(-100, min(100, hybrid_score))

        final_direction = Aggregator._score_to_direction(hybrid_score)

        # Conviction from both
        all_convictions = [r.conviction for r in all_agents.values()]
        avg_conviction = sum(all_convictions) / len(all_convictions) if all_convictions else 50
        final_conviction = min(100, avg_conviction * agreement_boost)

        # Conflict detection across all
        conflict_level, conflict_gap = Aggregator._detect_conflict(all_agents)

        direction_distribution = {}
        for agent_name, response in all_agents.items():
            direction_distribution[agent_name] = {
                "direction": response.direction,
                "conviction": response.conviction,
                "weight": config.AGENT_WEIGHTS.get(agent_name, 0.1),
            }

        # Compute quant/LLM agreement as 0-1 score
        # 0 gap = 1.0 (perfect agreement), 4 gap = 0.0 (max disagreement)
        quant_llm_agreement = max(0.0, 1.0 - (agreement_gap / 4.0))

        return AggregatorResult(
            final_direction=final_direction,
            final_conviction=final_conviction,
            consensus_score=hybrid_score,
            conflict_level=conflict_level,
            conflict_gap=conflict_gap,
            quant_consensus=quant_dir,
            llm_consensus=llm_dir,
            agreement_boost=agreement_boost,
            quant_llm_agreement=quant_llm_agreement,
            agent_breakdown=direction_distribution,
        )

    @staticmethod
    def _score_to_direction(score: float) -> str:
        """Convert numeric score to direction.

        HOLD band is controlled by config.HOLD_BAND (default 20).
        Only scores with |score| > HOLD_BAND produce a tradeable direction.
        This filters out marginal consensus — the system waits for meaningful
        agent alignment before committing to a trade.
        """
        band = config.HOLD_BAND
        if score > 45:
            return "STRONG_BUY"
        elif score > band:
            return "BUY"
        elif score > -band:
            return "HOLD"
        elif score > -45:
            return "SELL"
        else:
            return "STRONG_SELL"

    @staticmethod
    def _detect_conflict(agents_output: Dict[str, AgentResponse]) -> tuple:
        """Detect tug-of-war between agents."""
        if not agents_output:
            return "NONE", 0.0

        direction_scores = {
            "STRONG_BUY": 2,
            "BUY": 1,
            "HOLD": 0,
            "SELL": -1,
            "STRONG_SELL": -2,
        }

        scores = [
            direction_scores.get(r.direction, 0) * (r.conviction / 100.0)
            for r in agents_output.values()
        ]

        if not scores:
            return "NONE", 0.0

        max_score = max(scores)
        min_score = min(scores)
        gap = max_score - min_score

        if gap > 2.5:
            conflict_level = "TUG_OF_WAR"
        elif gap > 1.5:
            conflict_level = "MODERATE"
        else:
            conflict_level = "HIGH_AGREEMENT"

        return conflict_level, gap

    @staticmethod
    def _neutral_result() -> AggregatorResult:
        """Return neutral result when no agents present."""
        return AggregatorResult(
            final_direction="HOLD",
            final_conviction=30,
            consensus_score=0.0,
            conflict_level="NONE",
            conflict_gap=0.0,
            quant_consensus="HOLD",
            llm_consensus="HOLD",
            agreement_boost=1.0,
            agent_breakdown={},
        )
