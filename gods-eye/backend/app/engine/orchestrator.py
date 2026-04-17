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
from app.data.gap_risk import gap_risk_estimator, GapEstimate


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

        # ── Pre-market gap risk estimation ────────────────────────────
        # Fetches global cues (S&P futures, DXY, crude) + Dhan pre-open
        # before agents run, so gap data can inform NEWS_EVENT and paper trader.
        gap_estimate = None
        try:
            gap_estimate = await gap_risk_estimator.estimate(
                nifty_prev_close=market_data.nifty_spot,
            )
            if gap_estimate and gap_estimate.warnings:
                for w in gap_estimate.warnings:
                    logger.warning("Gap risk: %s", w)
        except Exception as e:
            logger.warning("Gap risk estimation failed (non-fatal): %s", e)

        # Build enriched context for each agent (signals + knowledge + memory)
        agent_contexts = {}
        for agent_key in self.agents:
            agent_contexts[agent_key] = self.profile_generator.build_context(
                agent_key, market_data, round_num=1
            )

        # Inject gap risk data into NEWS_EVENT agent context
        if gap_estimate and gap_estimate.data_source != "none":
            gap_ctx = (
                f"\n\nPRE-MARKET GAP RISK ({gap_estimate.risk_tier}):\n"
                f"  Estimated gap: {gap_estimate.estimated_gap_pct:+.2f}%\n"
                f"  Confidence: {gap_estimate.confidence:.0%}\n"
                f"  Data source: {gap_estimate.data_source}\n"
            )
            if gap_estimate.global_cues:
                gap_ctx += "  Global cues:\n"
                for cue_name, cue_val in gap_estimate.global_cues.items():
                    gap_ctx += f"    - {cue_name}: {cue_val:+.2f}%\n"
            if gap_estimate.risk_tier in ("WARNING", "DANGER"):
                gap_ctx += (
                    "  ⚠ Large gap expected — consider HOLD to avoid adverse opening.\n"
                )
            # Append to NEWS_EVENT context (it's the gatekeeper)
            if "NEWS_EVENT" in agent_contexts:
                agent_contexts["NEWS_EVENT"] += gap_ctx
            # Also give gap context to all agents for awareness
            for key in agent_contexts:
                if key != "NEWS_EVENT":
                    agent_contexts[key] += f"\n[Gap risk: {gap_estimate.risk_tier}, est. {gap_estimate.estimated_gap_pct:+.2f}%]"

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
        # SEC-L5: Wrap in error-handling callback to prevent silent failures
        async def _safe_review():
            try:
                await self.review_engine.review_simulation(
                    simulation_id=simulation_id,
                    market_data=market_data,
                    round1_outputs=round1_outputs,
                    round2_outputs=round2_outputs,
                    round3_outputs=final_outputs if direction_changed else None,
                    aggregator_result={},  # Will be populated by aggregator
                )
            except Exception as exc:
                logger.error("Background review task failed for %s: %s", simulation_id, exc, exc_info=True)

        asyncio.create_task(_safe_review())

        # Serialize gap estimate for API response
        gap_data = None
        if gap_estimate:
            gap_data = {
                "estimated_gap_pct": gap_estimate.estimated_gap_pct,
                "gap_magnitude": gap_estimate.gap_magnitude,
                "risk_tier": gap_estimate.risk_tier,
                "confidence": gap_estimate.confidence,
                "position_multiplier": gap_estimate.position_multiplier,
                "stop_buffer_pct": gap_estimate.stop_buffer_pct,
                "global_cues": gap_estimate.global_cues,
                "warnings": gap_estimate.warnings,
                "data_source": gap_estimate.data_source,
                "timestamp": gap_estimate.timestamp,
            }

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
            "gap_estimate": gap_data,
            "_gap_estimate_obj": gap_estimate,  # Internal: passed to paper trader
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
            else:
                # TRD-M2: Log when an LLM agent fails — its weight is NOT redistributed
                # to other agents, so the remaining agents' weights won't sum to 1.0.
                # This is the conservative approach: redistributing weights could amplify
                # a wrong signal from the surviving agents. The trade-off is that consensus
                # strength is slightly diluted when agents fail.
                logger.warning(
                    "Agent %s returned no result in round %d — excluded from consensus "
                    "(weight not redistributed to other agents)",
                    agent_name, round_num,
                )

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
