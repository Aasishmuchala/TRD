"""Promoter/Insider agent - LLM powered."""

import json
from typing import Optional, Dict, List
from app.auth.llm_client import get_llm_client
from app.agents.base_agent import BaseAgent
from app.api.schemas import AgentResponse, MarketInput
from app.config import config


class PromoterAgent(BaseAgent):
    """Company promoter/insider behavior simulation."""

    def __init__(self):
        super().__init__(
            name="Promoter Desk",
            persona="Company promoter/insider tracking stock performance and control implications",
            decision_framework="Pledge ratios, bulk deals, SEBI filings, control maintenance",
            risk_appetite="Conservative",
            time_horizon="Yearly",
            agent_type="LLM",
        )

    async def analyze(
        self,
        market_data: MarketInput,
        round_num: int = 1,
        other_agents_output: Optional[Dict[str, AgentResponse]] = None,
        enriched_context: Optional[str] = None,
    ) -> AgentResponse:
        """Analyze market from promoter perspective."""

        if config.MOCK_MODE:
            from app.agents.mock_responses import MockResponseGenerator
            return MockResponseGenerator.generate(
                "PROMOTER", self.name, self.agent_type, self.time_horizon,
                market_data, round_num, other_agents_output, enriched_context,
            )

        other_context = ""
        if other_agents_output and round_num > 1:
            other_context = "\n\nOther agents' views from Round 1:\n"
            for agent_name, response in other_agents_output.items():
                other_context += f"- {agent_name}: {response.direction} (conviction: {response.conviction})\n"

        prompt = self._build_prompt(market_data, round_num, other_context, enriched_context)

        responses_list = []
        for sample_idx in range(config.SAMPLES_PER_AGENT):
            response_text = await self._call_llm(prompt)
            parsed = self._parse_response(response_text)
            if parsed:
                responses_list.append(parsed)

        if not responses_list:
            return self._fallback_response()

        directions = [r["direction"] for r in responses_list]
        direction = self._consensus_direction(directions)

        convictions = [r["conviction"] for r in responses_list]
        base_conviction = sum(convictions) / len(convictions)

        direction_agreement = directions.count(direction) / len(directions)
        consistency = direction_agreement * 0.7 + 0.3

        final_conviction = base_conviction * consistency

        all_triggers = []
        for r in responses_list:
            all_triggers.extend(r.get("key_triggers", []))

        key_triggers = list(dict.fromkeys(all_triggers))[:5]

        reasoning = responses_list[0].get("reasoning", "")

        return AgentResponse(
            agent_name=self.name,
            agent_type=self.agent_type,
            direction=direction,
            conviction=final_conviction,
            reasoning=reasoning,
            key_triggers=key_triggers,
            time_horizon=self.time_horizon,
            views={
                "yearly": {
                    "direction": direction,
                    "conviction": final_conviction,
                    "control_concern": "Pledge dynamics",
                }
            },
            interaction_effects={
                "amplifies": ["Long-term holders"],
                "dampens": ["Short-term volatility trading"],
            },
            internal_consistency=consistency,
            reproducible=False,
            sample_variance=max(convictions) - min(convictions),
        )

    def _build_prompt(
        self, market_data: MarketInput, round_num: int, other_context: str,
        enriched_context: str = None,
    ) -> str:
        """Short directional signal prompt — single pass, no debate rounds."""

        intel_section = ""
        if enriched_context:
            intel_section = f"\nSIGNAL CONTEXT:\n{enriched_context}\n"

        return f"""You are analyzing promoter and corporate insider behavior as a signal for Nifty direction. Promoters buy when the market is undervalued or when they want to defend their holdings; they trim when valuations are stretched.

MARKET DATA:
- Nifty Spot: {market_data.nifty_spot}
- FII Net Flow (5-day): ${market_data.fii_flow_5d}M (negative = FII selling creates promoter support opportunity)
- DII Net Flow (5-day): ${market_data.dii_flow_5d}M
- India VIX: {market_data.india_vix} (high VIX = promoter buying opportunity to defend pledged shares)
- Market Context: {market_data.context}
{intel_section}
DECISION RULES:
- Heavy FII selling + high VIX → promoters likely supporting → BUY signal
- Low VIX + sustained rally → promoters trimming overvalued stakes → SELL signal
- Moderate FII selling + moderate VIX → promoters holding → HOLD
- Budget or election context: promoters cautious → lower conviction

Respond ONLY with valid JSON (no markdown):
{{
  "direction": "BUY" | "SELL" | "HOLD" | "STRONG_BUY" | "STRONG_SELL",
  "conviction": <0-100>,
  "key_triggers": ["trigger1", "trigger2"],
  "reasoning": "One or two sentences on whether promoter behavior is supportive or distributive given current flow and VIX conditions."
}}"""

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM via OpenAI-compatible API."""
        client = get_llm_client()
        return await client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )

    def _parse_response(self, response_text: str) -> Optional[Dict]:
        """Parse Claude response."""
        try:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start == -1 or json_end <= json_start:
                return None

            json_str = response_text[json_start:json_end]
            data = json.loads(json_str)

            required = ["direction", "conviction", "key_triggers", "reasoning"]
            if not all(field in data for field in required):
                return None

            conviction = max(0, min(100, float(data.get("conviction", 50))))
            data["conviction"] = conviction

            return data
        except (json.JSONDecodeError, ValueError, AttributeError):
            return None

    def _consensus_direction(self, directions: List[str]) -> str:
        """Get consensus direction."""
        direction_strength = {
            "STRONG_BUY": 2,
            "BUY": 1,
            "HOLD": 0,
            "SELL": -1,
            "STRONG_SELL": -2,
        }

        score = sum(direction_strength.get(d, 0) for d in directions)
        avg_score = score / len(directions) if directions else 0

        if avg_score > 1.3:
            return "STRONG_BUY"
        elif avg_score > 0.3:
            return "BUY"
        elif avg_score > -0.3:
            return "HOLD"
        elif avg_score > -1.3:
            return "SELL"
        else:
            return "STRONG_SELL"

    def _fallback_response(self) -> AgentResponse:
        """Fallback response."""
        return AgentResponse(
            agent_name=self.name,
            agent_type=self.agent_type,
            direction="HOLD",
            conviction=40,
            reasoning="Unable to parse control dynamics. Maintaining current position.",
            key_triggers=["Parsing error", "Control stable"],
            time_horizon=self.time_horizon,
            internal_consistency=0.3,
            reproducible=False,
        )
