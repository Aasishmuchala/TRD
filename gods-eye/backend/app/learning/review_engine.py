"""Background review engine — analyzes completed simulations to extract learnings.

After each simulation, a background task reviews the results and determines
if any agent discovered a reusable pattern worth saving as a skill.

Adapted from NousResearch/hermes-agent's background skill review system.

The key insight: agents that "remember" what worked and what failed
compound intelligence over time. This engine is the mechanism that
converts raw simulation experience into structured, retrievable skills.

Learning triggers:
  - Agent changed direction between rounds (adapted to new info)
  - Agent was significantly wrong (high conviction, wrong direction)
  - Consensus was unusual (all agree, or high conflict)
  - Market context created unexpected agent behavior
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from app.api.schemas import AgentResponse, MarketInput
from app.learning.skill_store import Skill, get_skill_store
from app.memory.agent_memory import AgentMemory
from app.config import config

logger = logging.getLogger(__name__)


class SimulationReviewEngine:
    """Reviews completed simulations and extracts learnable patterns.

    Runs as a background task after each simulation completes.
    Does NOT call the LLM — it uses rule-based heuristics to detect
    patterns and create skills. This keeps it fast and free.
    """

    def __init__(self, agent_memory: AgentMemory):
        self.memory = agent_memory
        self.skill_store = get_skill_store()

    async def review_simulation(
        self,
        simulation_id: str,
        market_data: MarketInput,
        round1_outputs: Dict[str, AgentResponse],
        round2_outputs: Dict[str, AgentResponse],
        round3_outputs: Optional[Dict[str, AgentResponse]],
        aggregator_result: Dict[str, Any],
    ):
        """Analyze a completed simulation for learnable patterns.

        This runs in the background (fire-and-forget) so it doesn't
        slow down the simulation response.
        """
        if not config.LEARNING_ENABLED:
            return

        try:
            learnings = []

            # 1. Direction change analysis
            direction_changes = self._analyze_direction_changes(
                round1_outputs, round2_outputs, round3_outputs
            )
            learnings.extend(direction_changes)

            # 2. Conviction calibration patterns
            calibration = self._analyze_conviction_patterns(
                round2_outputs or round1_outputs, market_data
            )
            learnings.extend(calibration)

            # 3. Consensus anomalies
            consensus = self._analyze_consensus(
                round2_outputs or round1_outputs, aggregator_result
            )
            learnings.extend(consensus)

            # 4. Context-specific patterns
            context_patterns = self._analyze_context_patterns(
                market_data, round2_outputs or round1_outputs
            )
            learnings.extend(context_patterns)

            # Save any new skills discovered
            for learning in learnings:
                self._save_if_novel(learning)

            if learnings:
                logger.info(
                    f"Review of {simulation_id}: found {len(learnings)} potential learnings"
                )

        except Exception as e:
            logger.error(f"Review engine error for {simulation_id}: {e}")

    def _analyze_direction_changes(
        self,
        round1: Dict[str, AgentResponse],
        round2: Dict[str, AgentResponse],
        round3: Optional[Dict[str, AgentResponse]],
    ) -> List[Skill]:
        """Detect when agents changed direction between rounds.

        A direction change means the agent learned from other agents'
        perspectives. If this change is consistent (happens in similar
        market conditions), it's worth saving as a skill.
        """
        skills = []
        final = round3 or round2

        for agent_key in round1:
            if agent_key not in round2:
                continue

            r1_dir = round1[agent_key].direction
            r2_dir = round2[agent_key].direction

            if r1_dir != r2_dir:
                # Agent changed direction — extract the pattern
                r1_reasoning = round1[agent_key].reasoning or ""
                r2_reasoning = round2[agent_key].reasoning or ""
                triggers = round2[agent_key].key_triggers or []

                # What convinced them to change?
                skill_content = (
                    f"When initially calling {r1_dir}, the agent revised to {r2_dir} "
                    f"after seeing other agents' perspectives.\n\n"
                    f"Original reasoning: {r1_reasoning[:150]}\n"
                    f"Revised reasoning: {r2_reasoning[:150]}\n"
                    f"Key triggers for revision: {', '.join(triggers[:3])}\n\n"
                    f"This suggests the agent's initial {r1_dir} signal was "
                    f"{'too bullish' if 'BUY' in r1_dir else 'too bearish' if 'SELL' in r1_dir else 'uncertain'} "
                    f"and should be tempered in similar conditions."
                )

                skills.append(Skill(
                    name=f"{agent_key} direction revision {r1_dir} to {r2_dir}",
                    agent=agent_key,
                    description=f"{agent_key} tends to revise from {r1_dir} to {r2_dir} after inter-agent deliberation",
                    content=skill_content,
                    trigger_conditions=[],  # Will be refined with more data
                    created=datetime.now().isoformat(),
                ))

        return skills

    def _analyze_conviction_patterns(
        self, final_outputs: Dict[str, AgentResponse], market_data: MarketInput
    ) -> List[Skill]:
        """Detect conviction calibration issues.

        High conviction + HOLD = confused agent
        Very low conviction on everything = agent needs more context
        All agents with same high conviction = possible echo chamber
        """
        skills = []

        for agent_key, response in final_outputs.items():
            if response.agent_type == "QUANT":
                continue  # Quant agents are deterministic

            # High conviction HOLD — confused
            if response.direction == "HOLD" and response.conviction > 65:
                skills.append(Skill(
                    name=f"{agent_key} confused HOLD pattern",
                    agent=agent_key,
                    description=f"{agent_key} calls HOLD with high conviction ({response.conviction:.0f}%), suggesting confusion",
                    content=(
                        f"The agent called HOLD at {response.conviction:.0f}% conviction, "
                        f"which is contradictory — high conviction should mean a directional bet. "
                        f"Market context was '{market_data.context}' with VIX at {market_data.india_vix}. "
                        f"Consider: does HOLD genuinely mean conviction, or is the agent hedging?"
                    ),
                    trigger_conditions=[f"india_vix >= {market_data.india_vix - 2}"],
                ))

            # Extreme conviction (>90) — overconfidence flag
            if response.conviction > 90:
                skills.append(Skill(
                    name=f"{agent_key} extreme conviction alert",
                    agent=agent_key,
                    description=f"{agent_key} showing extreme conviction (>{response.conviction:.0f}%)",
                    content=(
                        f"Agent called {response.direction} at {response.conviction:.0f}% conviction. "
                        f"Historically, extreme conviction predictions have lower accuracy than "
                        f"moderate conviction ones (60-80%). This may indicate overconfidence bias. "
                        f"Consider capping conviction at 85% unless evidence is truly overwhelming."
                    ),
                    trigger_conditions=[],
                ))

        return skills

    def _analyze_consensus(
        self,
        final_outputs: Dict[str, AgentResponse],
        aggregator_result: Dict[str, Any],
    ) -> List[Skill]:
        """Detect consensus anomalies."""
        skills = []

        directions = [r.direction for r in final_outputs.values()]

        # Check for perfect agreement (rare and informative)
        buy_count = sum(1 for d in directions if "BUY" in d)
        sell_count = sum(1 for d in directions if "SELL" in d)

        if buy_count == len(directions):
            skills.append(Skill(
                name="unanimous bullish consensus",
                agent="ALL",
                description="All agents agreed on BUY — rare and potentially significant",
                content=(
                    f"All {len(directions)} agents converged on a bullish signal. This level of agreement "
                    "is statistically unusual and typically occurs during strong trending markets "
                    "or after significant positive catalysts. Historically, unanimous consensus "
                    "may indicate either a strong trend continuation OR a contrarian reversal setup. "
                    "Track the outcome to determine which pattern applies in this market regime."
                ),
                trigger_conditions=[],
            ))
        elif sell_count == len(directions):
            skills.append(Skill(
                name="unanimous bearish consensus",
                agent="ALL",
                description="All agents agreed on SELL — rare and potentially significant",
                content=(
                    f"All {len(directions)} agents converged on a bearish signal. This level of agreement "
                    "is rare. In Indian markets, extreme bearish consensus often coincides "
                    "with capitulation lows (contrarian buy signal) OR genuine structural breaks. "
                    "Track whether this predicted a bottom or continuation."
                ),
                trigger_conditions=[],
            ))

        # High conflict — agents strongly disagree
        conflict_level = aggregator_result.get("conflict_level", "")
        if conflict_level == "TUG_OF_WAR":
            # Find the two most opposing agents
            bullish = [(k, r) for k, r in final_outputs.items() if "BUY" in r.direction]
            bearish = [(k, r) for k, r in final_outputs.items() if "SELL" in r.direction]

            if bullish and bearish:
                bull_leader = max(bullish, key=lambda x: x[1].conviction)
                bear_leader = max(bearish, key=lambda x: x[1].conviction)

                skills.append(Skill(
                    name=f"tug of war {bull_leader[0]} vs {bear_leader[0]}",
                    agent="ALL",
                    description=f"Strong disagreement between {bull_leader[0]} (bullish) and {bear_leader[0]} (bearish)",
                    content=(
                        f"{bull_leader[0]} called {bull_leader[1].direction} at {bull_leader[1].conviction:.0f}% "
                        f"while {bear_leader[0]} called {bear_leader[1].direction} at {bear_leader[1].conviction:.0f}%. "
                        f"This tug-of-war pattern suggests the market is at an inflection point. "
                        f"Track which agent was right to calibrate future weight adjustments."
                    ),
                    trigger_conditions=[],
                ))

        return skills

    def _analyze_context_patterns(
        self,
        market_data: MarketInput,
        final_outputs: Dict[str, AgentResponse],
    ) -> List[Skill]:
        """Detect market-context-specific patterns."""
        skills = []
        context = market_data.context

        # VIX spike + bullish consensus = potential contrarian signal
        if market_data.india_vix > 22:
            bullish_agents = [
                k for k, r in final_outputs.items()
                if "BUY" in r.direction and r.conviction > 60
            ]
            if len(bullish_agents) >= 4:
                skills.append(Skill(
                    name="bullish consensus in high VIX",
                    agent="ALL",
                    description="Multiple agents bullish despite high VIX — contrarian or brave?",
                    content=(
                        f"With VIX at {market_data.india_vix}, {len(bullish_agents)} out of {len(final_outputs)} agents "
                        f"called BUY with >60% conviction. High VIX typically signals fear, but "
                        f"bullish consensus in fear often marks market bottoms in Indian markets. "
                        f"Track outcome to determine if this is a reliable contrarian signal."
                    ),
                    trigger_conditions=["india_vix > 22"],
                ))

        # FII heavy selling + market context
        if market_data.fii_flow_5d < -500:
            skills.append(Skill(
                name=f"extreme FII outflow in {context}",
                agent="FII",
                description=f"Extreme FII selling (>{abs(market_data.fii_flow_5d):.0f}M) during {context}",
                content=(
                    f"FII 5-day outflow hit ${market_data.fii_flow_5d:.0f}M during '{context}' context. "
                    f"This level of selling is in the 95th percentile historically. "
                    f"Track whether this marked a capitulation bottom or start of extended outflow."
                ),
                trigger_conditions=[f"fii_flow_5d < {market_data.fii_flow_5d + 100}"],
            ))

        return skills

    def _save_if_novel(self, skill: Skill):
        """Save a skill only if a similar one doesn't already exist."""
        existing = self.skill_store.load_skills(skill.agent)

        # Check for duplicates by name similarity
        for existing_skill in existing:
            if self._skills_similar(skill, existing_skill):
                # Update existing skill instead of creating duplicate
                existing_skill.times_applied += 1
                existing_skill.updated = datetime.now().isoformat()
                # Merge content if meaningfully different
                if len(skill.content) > len(existing_skill.content):
                    existing_skill.content = skill.content
                self.skill_store.save_skill(existing_skill)
                logger.debug(f"Updated existing skill: {existing_skill.name}")
                return

        # Novel skill — save it
        self.skill_store.save_skill(skill)
        logger.info(f"Created new skill: {skill.name}")

    @staticmethod
    def _skills_similar(a: Skill, b: Skill) -> bool:
        """Check if two skills are about the same pattern."""
        # Same agent and similar name
        if a.agent != b.agent:
            return False

        # ARCH-M3: Simple word overlap check — may merge unrelated skills if they
        # share common words (e.g. "FII direction revision BUY to SELL" vs
        # "FII direction revision SELL to BUY"). Consider semantic similarity
        # or structured key comparison in a future iteration.
        a_words = set(a.name.lower().split())
        b_words = set(b.name.lower().split())
        overlap = len(a_words & b_words) / max(len(a_words | b_words), 1)
        return overlap > 0.5
