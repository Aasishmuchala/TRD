"""Streaming orchestrator — yields events as agents complete each round.

Same logic as Orchestrator, but instead of gathering all results and
returning at the end, it yields JSON-serializable event dicts that can
be pushed over WebSocket in real-time.

Event types:
    simulation_start   — simulation begins, metadata
    round_start        — round N begins
    agent_result       — single agent completed this round
    round_complete     — all agents done for this round
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
from app.agents.stock_options_agent import StockOptionsAgent
from app.agents.news_event_agent import NewsEventAgent
from app.agents.profile_generator import ProfileGenerator
from app.engine.aggregator import Aggregator
from app.engine.feedback_engine import FeedbackEngine
from app.learning.review_engine import SimulationReviewEngine
from app.memory.agent_memory import AgentMemory
from app.memory.prediction_tracker import PredictionTracker
from app.api.schemas import AgentResponse, MarketInput, SimulationResult
from app.config import config


class StreamingOrchestrator:
    """Orchestrates 3-round simulation, yielding events as they happen."""

    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {
            "ALGO": AlgoQuantAgent(),
            "FII": FIIAgent(),
            "DII": DIIAgent(),
            "RETAIL_FNO": RetailFNOAgent(),
            "PROMOTER": PromoterAgent(),
            "RBI": RBIPolicyAgent(),
            "STOCK_OPTIONS": StockOptionsAgent(),
            "NEWS_EVENT": NewsEventAgent(),
        }
        self.agent_memory = AgentMemory(db_path=config.DATABASE_PATH)
        self.profile_generator = ProfileGenerator(agent_memory=self.agent_memory)
        self.feedback_engine = FeedbackEngine(agent_memory=self.agent_memory)
        self.review_engine = SimulationReviewEngine(agent_memory=self.agent_memory)
        self.tracker = PredictionTracker()

    async def stream_simulation(
        self, market_data: MarketInput, data_source: str = "fallback"
    ) -> AsyncGenerator[dict, None]:
        """Yield simulation events as agents complete.

        Usage:
            async for event in orchestrator.stream_simulation(market_input):
                await websocket.send_json(event)
        """
        start_time = time.time()
        simulation_id = f"sim_{uuid.uuid4().hex[:12]}"
        round_history = []

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

        # ============== ROUND 1: Independent Analysis ==============
        yield {"type": "round_start", "round": 1, "description": "Independent Analysis"}

        round1_outputs = {}
        round1_data = {"round": 1, "agents": {}}

        async for agent_name, response in self._stream_round(
            market_data, 1, None, agent_contexts
        ):
            round1_outputs[agent_name] = response
            round1_data["agents"][agent_name] = {
                "direction": response.direction,
                "conviction": response.conviction,
                "type": response.agent_type,
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

        round_history.append(round1_data)
        yield {"type": "round_complete", "round": 1, "agents_completed": len(round1_outputs)}

        # ============== ROUND 2: React to Others ==============
        yield {"type": "round_start", "round": 2, "description": "Reacting to Other Agents"}

        round2_outputs = {}
        round2_data = {"round": 2, "agents": {}}

        async for agent_name, response in self._stream_round(
            market_data, 2, round1_outputs, agent_contexts
        ):
            round2_outputs[agent_name] = response
            round2_data["agents"][agent_name] = {
                "direction": response.direction,
                "conviction": response.conviction,
                "type": response.agent_type,
            }
            # Include direction change info
            changed = (
                agent_name in round1_outputs
                and round1_outputs[agent_name].direction != response.direction
            )
            yield {
                "type": "agent_result",
                "round": 2,
                "agent_name": agent_name,
                "agent_type": response.agent_type,
                "direction": response.direction,
                "conviction": response.conviction,
                "reasoning": response.reasoning,
                "key_triggers": response.key_triggers,
                "time_horizon": response.time_horizon,
                "direction_changed": changed,
                "previous_direction": round1_outputs.get(agent_name, None)
                and round1_outputs[agent_name].direction,
            }

        round_history.append(round2_data)
        yield {"type": "round_complete", "round": 2, "agents_completed": len(round2_outputs)}

        # ============== ROUND 3 (if needed): Equilibrium ==============
        direction_changed = self._check_direction_changes(round1_outputs, round2_outputs)
        final_outputs = round2_outputs
        round3_outputs = None  # Initialize — only populated if Round 3 runs

        if direction_changed:
            yield {"type": "round_start", "round": 3, "description": "Finding Equilibrium"}

            round3_outputs = {}
            round3_data = {"round": 3, "agents": {}}

            async for agent_name, response in self._stream_round(
                market_data, 3, round2_outputs, agent_contexts
            ):
                round3_outputs[agent_name] = response
                round3_data["agents"][agent_name] = {
                    "direction": response.direction,
                    "conviction": response.conviction,
                    "type": response.agent_type,
                }
                yield {
                    "type": "agent_result",
                    "round": 3,
                    "agent_name": agent_name,
                    "agent_type": response.agent_type,
                    "direction": response.direction,
                    "conviction": response.conviction,
                    "reasoning": response.reasoning,
                    "key_triggers": response.key_triggers,
                    "time_horizon": response.time_horizon,
                }

            round_history.append(round3_data)
            final_outputs = round3_outputs
            yield {"type": "round_complete", "round": 3, "agents_completed": len(round3_outputs)}
        else:
            yield {"type": "round_skipped", "round": 3, "reason": "All agents held direction — consensus reached in Round 2"}

        # ============== AGGREGATION ==============
        aggregator_result = Aggregator.aggregate(
            final_outputs, hybrid=True, tuned_weights=tuned_weights
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
        final_round = 3 if direction_changed else 2
        for agent_key, response in final_outputs.items():
            self.agent_memory.log_agent_prediction(
                simulation_id=simulation_id,
                agent_key=agent_key,
                direction=response.direction,
                conviction=response.conviction,
                reasoning=response.reasoning,
                key_triggers=response.key_triggers,
                context=market_data.context,
                round_num=final_round,
            )

        # Build and log full result
        from datetime import datetime

        sim_result = SimulationResult(
            simulation_id=simulation_id,
            timestamp=datetime.now(),
            market_input=market_data,
            agents_output=final_outputs,
            round_history=round_history,
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
                round1_outputs=round1_outputs,
                round2_outputs=round2_outputs,
                round3_outputs=round3_outputs,
                aggregator_result=agg_dict,
            )
        )

        # --- simulation_end ---
        yield {
            "type": "simulation_end",
            "simulation_id": simulation_id,
            "execution_time_ms": round(execution_time_ms, 1),
            "total_rounds": final_round,
            "model_used": config.MODEL,
            "feedback_active": feedback_active,
            "learning_enabled": config.LEARNING_ENABLED,
            "data_source": data_source,
        }

    async def _stream_round(
        self,
        market_data: MarketInput,
        round_num: int,
        other_agents: Optional[Dict[str, AgentResponse]],
        agent_contexts: Dict[str, str],
    ) -> AsyncGenerator[tuple, None]:
        """Run a round, yielding (agent_name, response) as each completes.

        QUANT agents complete instantly (yielded first).
        LLM agents run in parallel but yield individually as they finish.
        """
        # QUANT agents first (instant)
        for agent_name, agent in self.agents.items():
            if agent.agent_type == "QUANT":
                response = await agent.analyze(
                    market_data, round_num, other_agents,
                    enriched_context=agent_contexts.get(agent_name, ""),
                )
                yield agent_name, response

        # LLM agents in parallel, yielding as each completes
        llm_items = [
            (name, agent)
            for name, agent in self.agents.items()
            if agent.agent_type == "LLM"
        ]

        if not llm_items:
            return

        # Run LLM agents sequentially to avoid overwhelming the proxy
        # (parallel calls cause 502 errors on rate-limited proxies)
        for agent_name, agent in llm_items:
            try:
                response = await agent.analyze(
                    market_data, round_num, other_agents,
                    enriched_context=agent_contexts.get(agent_name, ""),
                )
                if isinstance(response, AgentResponse):
                    yield agent_name, response
            except Exception as e:
                yield agent_name, AgentResponse(
                    agent_name=agent_name,
                    agent_type="LLM",
                    direction="HOLD",
                    conviction=25.0,
                    reasoning=f"Agent error: {str(e)}",
                    key_triggers=["error"],
                    time_horizon="Unknown",
                )

    @staticmethod
    def _check_direction_changes(
        round1: Dict[str, AgentResponse],
        round2: Dict[str, AgentResponse],
    ) -> bool:
        for name in round1:
            if name in round2 and round1[name].direction != round2[name].direction:
                return True
        return False
