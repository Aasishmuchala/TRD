"""Orchestrator for 3-round agent simulation with MiroFish accuracy layer."""

import asyncio
import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)
from app.agents.base_agent import BaseAgent
from app.agents.algo_agent import AlgoQuantAgent
from app.agents.fii_agent import FIIAgent
from app.agents.dii_agent import DIIAgent
from app.agents.retail_fno_agent import RetailFNOAgent
from app.agents.promoter_agent import PromoterAgent
from app.agents.rbi_policy_agent import RBIPolicyAgent
from app.agents.stock_options_agent import StockOptionsAgent
from app.agents.news_event_agent import NewsEventAgent
from app.agents.profile_generator import ProfileGenerator
from app.memory.agent_memory import AgentMemory
from app.engine.feedback_engine import FeedbackEngine
from app.learning.review_engine import SimulationReviewEngine
from app.api.schemas import AgentResponse, MarketInput
from app.config import config


class Orchestrator:
    """Orchestrates 3-round agent simulation with interaction effects.

    Now integrates MiroFish patterns:
    - ProfileGenerator builds agent-specific signal + knowledge context
    - AgentMemory tracks per-agent predictions for accuracy
    - FeedbackEngine auto-tunes weights from accuracy data
    """

    def __init__(self):
        """Initialize all agents and accuracy layer."""
        self.agents: Dict[str, BaseAgent] = {
            "ALGO": AlgoQuantAgent(),
            "FII": FIIAgent(),
            "DII": DIIAgent(),
            "RETAIL_FNO": RetailFNOAgent(),
            "PROMOTER": PromoterAgent(),
            "RBI": RBIPolicyAgent(),
            "STOCK_OPTIONS": StockOptionsAgent(),
            "NEWS_EVENT": NewsEventAgent(),  # Event risk gatekeeper — veto power on binary events
        }

        # MiroFish accuracy layer
        self.agent_memory = AgentMemory(db_path=config.DATABASE_PATH)
        self.profile_generator = ProfileGenerator(agent_memory=self.agent_memory)
        self.feedback_engine = FeedbackEngine(agent_memory=self.agent_memory)

        # Auto-learning engine
        self.review_engine = SimulationReviewEngine(agent_memory=self.agent_memory)

        # Track outputs across rounds
        self.round_history: List[Dict] = []
        self.start_time = None

    async def run_simulation(self, market_data: MarketInput) -> Dict:
        """Run 3-round simulation with agent interaction and accuracy layer."""
        self.start_time = time.time()

        # Build enriched context for each agent (signals + knowledge + memory)
        agent_contexts = {}
        for agent_key in self.agents:
            agent_contexts[agent_key] = self.profile_generator.build_context(
                agent_key, market_data, round_num=1
            )

        # Determine current VIX regime for regime-stratified weight tuning
        vix_regime = self._classify_vix_regime(market_data.india_vix)

        # Get accuracy-tuned weights (falls back to defaults if insufficient data)
        tuned_weights = self.feedback_engine.get_tuned_weights(vix_regime=vix_regime)

        # Round 1: All agents analyze independently (with enriched context)
        round1_outputs = await self._run_round(
            market_data, round_num=1, agent_contexts=agent_contexts
        )

        # Round 2: Agents receive Round 1 outputs, adjust
        round2_outputs = await self._run_round(
            market_data, round_num=2, other_agents=round1_outputs,
            agent_contexts=agent_contexts,
        )

        # Determine if Round 3 needed (if any direction changed)
        direction_changed = self._check_direction_changes(round1_outputs, round2_outputs)

        if direction_changed:
            # Round 3: Confirmation round
            round3_outputs = await self._run_round(
                market_data, round_num=3, other_agents=round2_outputs,
                agent_contexts=agent_contexts,
            )
            final_outputs = round3_outputs
        else:
            final_outputs = round2_outputs

        execution_time_ms = (time.time() - self.start_time) * 1000

        # Log per-agent predictions to memory (for accuracy tracking)
        simulation_id = f"sim_{int(time.time())}"
        for agent_key, response in final_outputs.items():
            self.agent_memory.log_agent_prediction(
                simulation_id=simulation_id,
                agent_key=agent_key,
                direction=response.direction,
                conviction=response.conviction,
                reasoning=response.reasoning,
                key_triggers=response.key_triggers,
                context=market_data.context,
                round_num=3 if direction_changed else 2,
            )

        # Fire-and-forget: background review for auto-learning
        asyncio.create_task(
            self.review_engine.review_simulation(
                simulation_id=simulation_id,
                market_data=market_data,
                round1_outputs=round1_outputs,
                round2_outputs=round2_outputs,
                round3_outputs=final_outputs if direction_changed else None,
                aggregator_result={},  # Will be populated by aggregator
            )
        )

        return {
            "round1": round1_outputs,
            "round2": round2_outputs,
            "round3": final_outputs if direction_changed else None,
            "final_outputs": final_outputs,
            "round_history": self.round_history,
            "execution_time_ms": execution_time_ms,
            "tuned_weights": tuned_weights,
            "feedback_active": self.feedback_engine.should_activate(),
            "learning_enabled": config.LEARNING_ENABLED,
        }

    async def _run_round(
        self,
        market_data: MarketInput,
        round_num: int,
        other_agents: Dict[str, AgentResponse] = None,
        agent_contexts: Dict[str, str] = None,
    ) -> Dict[str, AgentResponse]:
        """Run a single round of agent analysis with enriched context."""
        outputs = {}
        round_data = {"round": round_num, "agents": {}}

        # Run quant agents first (instant)
        for agent_name, agent in self.agents.items():
            if agent.agent_type == "QUANT":
                response = await agent.analyze(
                    market_data, round_num, other_agents,
                    enriched_context=agent_contexts.get(agent_name, "") if agent_contexts else None,
                )
                outputs[agent_name] = response
                round_data["agents"][agent_name] = {
                    "direction": response.direction,
                    "conviction": response.conviction,
                    "type": "QUANT",
                }

        # Run LLM agents in parallel — streaming keeps connections alive through
        # the proxy, and the semaphore in llm_client.py caps burst concurrency.
        llm_agents = {
            name: agent for name, agent in self.agents.items()
            if agent.agent_type == "LLM"
        }

        async def _run_llm_agent(agent_name: str, agent):
            """Run a single LLM agent, returning (name, response) or (name, None)."""
            try:
                response = await agent.analyze(
                    market_data, round_num, other_agents,
                    enriched_context=agent_contexts.get(agent_name, "") if agent_contexts else None,
                )
                if isinstance(response, AgentResponse):
                    return agent_name, response
                logger.warning(f"LLM agent {agent_name} returned non-AgentResponse in round {round_num}")
                return agent_name, None
            except Exception as exc:
                logger.error(
                    f"LLM agent {agent_name} failed in round {round_num}: "
                    f"{type(exc).__name__}: {exc}",
                    exc_info=True,
                )
                return agent_name, None

        llm_results = await asyncio.gather(
            *[_run_llm_agent(name, agent) for name, agent in llm_agents.items()],
            return_exceptions=False,
        )

        for agent_name, response in llm_results:
            if response is not None:
                outputs[agent_name] = response
                round_data["agents"][agent_name] = {
                    "direction": response.direction,
                    "conviction": response.conviction,
                    "type": "LLM",
                }

        self.round_history.append(round_data)
        return outputs

    @staticmethod
    def _classify_vix_regime(india_vix: float) -> Optional[str]:
        """Classify current VIX into a regime bucket for weight tuning.

        Returns None if VIX data is missing/zero (falls back to non-regime tuning).
        """
        if not india_vix or india_vix <= 0:
            return None
        if india_vix < 15:
            return "low_vix"
        elif india_vix < 20:
            return "normal_vix"
        elif india_vix < 30:
            return "elevated_vix"
        else:
            return "high_vix"

    def _check_direction_changes(
        self,
        round1: Dict[str, AgentResponse],
        round2: Dict[str, AgentResponse],
    ) -> bool:
        """Check if any agent changed direction or had a large conviction swing.

        Triggers Round 3 if:
        - Any agent flipped direction between rounds, OR
        - Any agent's conviction swung by >30 points (signals instability)
        """
        for agent_name in round1:
            if agent_name in round2:
                # Direction flip
                if round1[agent_name].direction != round2[agent_name].direction:
                    return True
                # Conviction swing > 30 points
                delta = abs(round1[agent_name].conviction - round2[agent_name].conviction)
                if delta > 30:
                    return True
        return False
