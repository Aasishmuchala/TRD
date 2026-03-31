"""Streaming orchestrator — yields events as agents complete in a single round.

Dispatches all 6 agents simultaneously:
- QUANT agent (AlgoQuantAgent): awaited inline — instant, yielded first
- 5 LLM agents: dispatched in parallel via asyncio.wait, yielded as each finishes

Event types emitted (in order):
    simulation_start   — simulation begins, metadata
    round_start        — round 1 begins (only once)
    agent_result       — single agent completed (6 total)
    round_complete     — all agents done for round 1
    aggregation        — final aggregated result
    simulation_end     — all done, timing + metadata
    error              — something went wrong
"""

import asyncio
import time
import uuid
from typing import AsyncGenerator, Dict, List, Optional

from app.agents.base_agent import BaseAgent
from app.agents.algo_agent import AlgoQuantAgent
from app.agents.fii_agent import FIIAgent
from app.agents.dii_agent import DIIAgent
from app.agents.retail_fno_agent import RetailFNOAgent
from app.agents.promoter_agent import PromoterAgent
from app.agents.rbi_policy_agent import RBIPolicyAgent
from app.agents.profile_generator import ProfileGenerator
from app.engine.aggregator import Aggregator
from app.engine.feedback_engine import FeedbackEngine
from app.learning.review_engine import SimulationReviewEngine
from app.memory.agent_memory import AgentMemory
from app.memory.prediction_tracker import PredictionTracker
from app.api.schemas import AgentResponse, MarketInput, SimulationResult
from app.config import config


class StreamingOrchestrator:
    """Orchestrates single-round parallel simulation, yielding events as they happen."""

    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {
            "ALGO": AlgoQuantAgent(),
            "FII": FIIAgent(),
            "DII": DIIAgent(),
            "RETAIL_FNO": RetailFNOAgent(),
            "PROMOTER": PromoterAgent(),
            "RBI": RBIPolicyAgent(),
        }
        self.agent_memory = AgentMemory(db_path=config.DATABASE_PATH)
        self.profile_generator = ProfileGenerator(agent_memory=self.agent_memory)
        self.feedback_engine = FeedbackEngine(agent_memory=self.agent_memory)
        self.review_engine = SimulationReviewEngine(agent_memory=self.agent_memory)
        self.tracker = PredictionTracker()

    async def stream_simulation(
        self, market_data: MarketInput, data_source: str = "fallback"
    ) -> AsyncGenerator[dict, None]:
        """Single-round parallel simulation — yield events as each agent completes.

        Usage:
            async for event in orchestrator.stream_simulation(market_input):
                await websocket.send_json(event)
        """
        start_time = time.time()
        simulation_id = f"sim_{uuid.uuid4().hex[:12]}"

        # Build enriched context
        agent_contexts = {}
        for agent_key in self.agents:
            agent_contexts[agent_key] = self.profile_generator.build_context(
                agent_key, market_data, round_num=1
            )

        tuned_weights = self.feedback_engine.get_tuned_weights()
        feedback_active = self.feedback_engine.should_activate()

        # --- simulation_start ---
        yield {
            "type": "simulation_start",
            "simulation_id": simulation_id,
            "total_agents": len(self.agents),
            "agent_names": list(self.agents.keys()),
            "mock_mode": config.MOCK_MODE,
            "feedback_active": feedback_active,
        }

        yield {"type": "round_start", "round": 1, "description": "Parallel Signal Analysis"}

        round_outputs = {}
        round_data = {"round": 1, "agents": {}}

        # QUANT agent — instant, yield first
        for agent_name, agent in self.agents.items():
            if agent.agent_type == "QUANT":
                response = await agent.analyze(
                    market_data, 1, None,
                    enriched_context=agent_contexts.get(agent_name, ""),
                )
                round_outputs[agent_name] = response
                round_data["agents"][agent_name] = {
                    "direction": response.direction,
                    "conviction": response.conviction,
                    "type": "QUANT",
                }
                yield {
                    "type": "agent_result",
                    "round": 1,
                    "agent_name": agent_name,
                    "agent_type": response.agent_type,
                    "direction": response.direction,
                    "conviction": response.conviction,
                    "reasoning": response.reasoning,
                    "key_triggers": response.key_triggers,
                    "time_horizon": response.time_horizon,
                }

        # LLM agents — dispatch all simultaneously, yield as each completes
        llm_items = [
            (name, agent)
            for name, agent in self.agents.items()
            if agent.agent_type == "LLM"
        ]

        if llm_items:
            tasks = {}
            for agent_name, agent in llm_items:
                task = asyncio.create_task(
                    agent.analyze(
                        market_data, 1, None,
                        enriched_context=agent_contexts.get(agent_name, ""),
                    )
                )
                tasks[task] = agent_name

            pending = set(tasks.keys())
            while pending:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    agent_name = tasks[task]
                    try:
                        response = task.result()
                        if isinstance(response, AgentResponse):
                            round_outputs[agent_name] = response
                            round_data["agents"][agent_name] = {
                                "direction": response.direction,
                                "conviction": response.conviction,
                                "type": "LLM",
                            }
                            yield {
                                "type": "agent_result",
                                "round": 1,
                                "agent_name": agent_name,
                                "agent_type": response.agent_type,
                                "direction": response.direction,
                                "conviction": response.conviction,
                                "reasoning": response.reasoning,
                                "key_triggers": response.key_triggers,
                                "time_horizon": response.time_horizon,
                            }
                    except Exception as e:
                        yield {
                            "type": "agent_result",
                            "round": 1,
                            "agent_name": agent_name,
                            "agent_type": "LLM",
                            "direction": "HOLD",
                            "conviction": 25.0,
                            "reasoning": f"Agent error: {str(e)}",
                            "key_triggers": ["error"],
                            "time_horizon": "Unknown",
                        }

        yield {"type": "round_complete", "round": 1, "agents_completed": len(round_outputs)}

        # ============== AGGREGATION ==============
        aggregator_result = Aggregator.aggregate(
            round_outputs, hybrid=True, tuned_weights=tuned_weights
        )

        yield {
            "type": "aggregation",
            "final_direction": aggregator_result.final_direction,
            "final_conviction": aggregator_result.final_conviction,
            "consensus_score": aggregator_result.consensus_score,
            "conflict_level": aggregator_result.conflict_level,
            "quant_llm_agreement": aggregator_result.quant_llm_agreement,
            "agent_breakdown": aggregator_result.agent_breakdown,
        }

        # ============== LOGGING & CLEANUP ==============
        execution_time_ms = (time.time() - start_time) * 1000

        # Log per-agent predictions
        for agent_key, response in round_outputs.items():
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

        # Build and log full result
        from datetime import datetime

        sim_result = SimulationResult(
            simulation_id=simulation_id,
            timestamp=datetime.now(),
            market_input=market_data,
            agents_output=round_outputs,
            round_history=[round_data],
            aggregator_result=aggregator_result,
            execution_time_ms=execution_time_ms,
            model_used=config.MODEL,
            feedback_active=feedback_active,
            tuned_weights=tuned_weights,
        )
        self.tracker.log_simulation(sim_result)
        self.tracker.log_prediction(sim_result)

        # Fire-and-forget: background review for auto-learning
        agg_dict = {
            "final_direction": aggregator_result.final_direction,
            "final_conviction": aggregator_result.final_conviction,
            "consensus_score": aggregator_result.consensus_score,
            "conflict_level": aggregator_result.conflict_level,
        }
        asyncio.create_task(
            self.review_engine.review_simulation(
                simulation_id=simulation_id,
                market_data=market_data,
                round1_outputs=round_outputs,
                round2_outputs=round_outputs,
                round3_outputs=None,
                aggregator_result=agg_dict,
            )
        )

        # --- simulation_end ---
        yield {
            "type": "simulation_end",
            "simulation_id": simulation_id,
            "execution_time_ms": round(execution_time_ms, 1),
            "total_rounds": 1,
            "model_used": config.MODEL,
            "feedback_active": feedback_active,
            "learning_enabled": config.LEARNING_ENABLED,
            "data_source": data_source,
        }

    @staticmethod
    def _check_direction_changes(
        round1: Dict[str, AgentResponse],
        round2: Dict[str, AgentResponse],
    ) -> bool:
        """Check if any agent changed direction between rounds.

        Kept for backward compatibility — no longer called in single-round design.
        """
        for name in round1:
            if name in round2 and round1[name].direction != round2[name].direction:
                return True
        return False
