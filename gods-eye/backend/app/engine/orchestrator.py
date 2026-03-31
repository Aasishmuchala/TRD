"""Orchestrator for single-round parallel agent simulation with MiroFish accuracy layer."""

import asyncio
import time
from typing import Dict, List, Optional
from app.agents.base_agent import BaseAgent
from app.agents.algo_agent import AlgoQuantAgent
from app.agents.fii_agent import FIIAgent
from app.agents.dii_agent import DIIAgent
from app.agents.retail_fno_agent import RetailFNOAgent
from app.agents.promoter_agent import PromoterAgent
from app.agents.rbi_policy_agent import RBIPolicyAgent
from app.agents.profile_generator import ProfileGenerator
from app.memory.agent_memory import AgentMemory
from app.engine.feedback_engine import FeedbackEngine
from app.learning.review_engine import SimulationReviewEngine
from app.api.schemas import AgentResponse, MarketInput
from app.config import config


class Orchestrator:
    """Orchestrates single-round parallel simulation with interaction effects.

    All 6 agents are dispatched once:
    - QUANT agent (AlgoQuantAgent): awaited inline — instant, no network I/O
    - 5 LLM agents: dispatched simultaneously via asyncio.gather

    Integrates MiroFish patterns:
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
        """Run single-round parallel simulation — all 6 agents dispatched once."""
        self.start_time = time.time()
        self.round_history = []

        # Build enriched context for each agent (signals + knowledge + memory)
        agent_contexts = {}
        for agent_key in self.agents:
            agent_contexts[agent_key] = self.profile_generator.build_context(
                agent_key, market_data, round_num=1
            )

        tuned_weights = self.feedback_engine.get_tuned_weights()

        # Single round — all agents in parallel
        final_outputs = await self._run_single_round(market_data, agent_contexts)

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
                round_num=1,
            )

        # Fire-and-forget: background review for auto-learning
        asyncio.create_task(
            self.review_engine.review_simulation(
                simulation_id=simulation_id,
                market_data=market_data,
                round1_outputs=final_outputs,
                round2_outputs=final_outputs,
                round3_outputs=None,
                aggregator_result={},
            )
        )

        return {
            "round1": final_outputs,
            "round2": None,
            "round3": None,
            "final_outputs": final_outputs,
            "round_history": self.round_history,
            "execution_time_ms": execution_time_ms,
            "tuned_weights": tuned_weights,
            "feedback_active": self.feedback_engine.should_activate(),
            "learning_enabled": config.LEARNING_ENABLED,
        }

    async def _run_single_round(
        self,
        market_data: MarketInput,
        agent_contexts: Dict[str, str],
    ) -> Dict[str, AgentResponse]:
        """Dispatch QUANT agent first (instant), then all LLM agents in parallel."""
        outputs = {}
        round_data = {"round": 1, "agents": {}}

        # QUANT agent — instant, no network I/O
        for agent_name, agent in self.agents.items():
            if agent.agent_type == "QUANT":
                response = await agent.analyze(
                    market_data, 1, None,
                    enriched_context=agent_contexts.get(agent_name, ""),
                )
                outputs[agent_name] = response
                round_data["agents"][agent_name] = {
                    "direction": response.direction,
                    "conviction": response.conviction,
                    "type": "QUANT",
                }

        # LLM agents — all dispatched simultaneously
        llm_agent_names = [
            name for name, agent in self.agents.items()
            if agent.agent_type == "LLM"
        ]
        llm_tasks = [
            self.agents[name].analyze(
                market_data, 1, None,
                enriched_context=agent_contexts.get(name, ""),
            )
            for name in llm_agent_names
        ]

        if llm_tasks:
            llm_responses = await asyncio.gather(*llm_tasks, return_exceptions=True)
            for agent_name, response in zip(llm_agent_names, llm_responses):
                if isinstance(response, AgentResponse):
                    outputs[agent_name] = response
                    round_data["agents"][agent_name] = {
                        "direction": response.direction,
                        "conviction": response.conviction,
                        "type": "LLM",
                    }

        self.round_history.append(round_data)
        return outputs

    @staticmethod
    def _check_direction_changes(
        round1: Dict[str, AgentResponse],
        round2: Dict[str, AgentResponse],
    ) -> bool:
        """Check if any agent changed direction between rounds.

        Kept for backward compatibility — no longer called in single-round design.
        """
        for agent_name in round1:
            if agent_name in round2:
                if round1[agent_name].direction != round2[agent_name].direction:
                    return True
        return False
