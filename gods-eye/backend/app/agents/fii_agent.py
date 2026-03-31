"""FII (Foreign Institutional Investor) agent - LLM powered."""

import json
from typing import Optional, Dict, List
from app.agents.base_agent import BaseAgent
from app.api.schemas import AgentResponse, MarketInput
from app.auth.llm_client import get_llm_client
from app.config import config


class FIIAgent(BaseAgent):
    """Foreign Institutional Investor behavior simulation."""

    def __init__(self):
        super().__init__(
            name="FII Flows Analyst",
            persona="Foreign Institutional Investor managing Asia-Pacific allocations",
            decision_framework="Capital allocation based on yield spreads, FX outlook, EM sentiment",
            risk_appetite="Moderate",
            time_horizon="Quarterly",
            agent_type="LLM",
        )

    async def analyze(
        self,
        market_data: MarketInput,
        round_num: int = 1,
        other_agents_output: Optional[Dict[str, AgentResponse]] = None,
        enriched_context: Optional[str] = None,
    ) -> AgentResponse:
        """Analyze market from FII perspective."""

        # Use mock mode if no API key
        if config.MOCK_MODE:
            from app.agents.mock_responses import MockResponseGenerator
            return MockResponseGenerator.generate(
                "FII", self.name, self.agent_type, self.time_horizon,
                market_data, round_num, other_agents_output, enriched_context,
            )

        # Build context from other agents
        other_context = ""
        if other_agents_output and round_num > 1:
            other_context = "\n\nOther agents' views from Round 1:\n"
            for agent_name, response in other_agents_output.items():
                other_context += f"- {agent_name}: {response.direction} (conviction: {response.conviction})\n"

        prompt = self._build_prompt(market_data, round_num, other_context, enriched_context)

        # Collect 3 parallel samples for consensus
        responses_list = []
        for sample_idx in range(config.SAMPLES_PER_AGENT):
            response_text = await self._call_llm(prompt)
            parsed = self._parse_response(response_text)
            if parsed:
                responses_list.append(parsed)

        # Consensus logic
        if not responses_list:
            return self._fallback_response()

        # Get consensus direction
        directions = [r["direction"] for r in responses_list]
        direction = self._consensus_direction(directions)

        # Average conviction, penalized by consistency
        convictions = [r["conviction"] for r in responses_list]
        base_conviction = sum(convictions) / len(convictions)

        # Calculate consistency score (0-1)
        direction_agreement = directions.count(direction) / len(directions)
        consistency = direction_agreement * 0.7 + 0.3  # Min 0.3, max 1.0

        final_conviction = base_conviction * consistency

        # Aggregate reasoning and triggers
        all_triggers = []
        all_reasoning = []
        for r in responses_list:
            all_triggers.extend(r.get("key_triggers", []))
            all_reasoning.append(r.get("reasoning", ""))

        # Deduplicate triggers
        key_triggers = list(dict.fromkeys(all_triggers))[:5]

        reasoning = all_reasoning[0]  # Use first sample's reasoning

        return AgentResponse(
            agent_name=self.name,
            agent_type=self.agent_type,
            direction=direction,
            conviction=final_conviction,
            reasoning=reasoning,
            key_triggers=key_triggers,
            time_horizon=self.time_horizon,
            views={
                "quarterly": {
                    "direction": direction,
                    "conviction": final_conviction,
                    "usd_inr_outlook": f"DXY at {market_data.dxy}",
                }
            },
            interaction_effects={
                "amplifies": ["RBI policy changes", "US rate decisions"],
                "dampens": ["Retail sentiment"],
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

        return f"""You are analyzing FII (Foreign Institutional Investor) behavior for the Indian market. Answer one question: based on the data below, will FIIs buy or sell Indian equities tomorrow?

MARKET DATA:
- Nifty Spot: {market_data.nifty_spot}
- FII Net Flow (5-day): ${market_data.fii_flow_5d}M (positive = net buying)
- USD/INR: {market_data.usd_inr} (rising = rupee weakening = FII headwind)
- DXY (US Dollar Index): {market_data.dxy} (above 104 = strong dollar = EM outflows)
- India VIX: {market_data.india_vix}
- Market Context: {market_data.context}
{intel_section}
DECISION RULES:
- Continuing 5-day buying trend + DXY below 104 + stable rupee → BUY signal
- Continuing 5-day selling + DXY above 104 + rupee weakening → SELL signal
- Mixed signals or flow reversal → HOLD
- High VIX (>20) amplifies selling pressure, reduces buying conviction

Respond ONLY with valid JSON (no markdown):
{{
  "direction": "BUY" | "SELL" | "HOLD" | "STRONG_BUY" | "STRONG_SELL",
  "conviction": <0-100>,
  "key_triggers": ["trigger1", "trigger2"],
  "reasoning": "One or two sentences stating what the FII flow and forex data predict for tomorrow."
}}"""

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM via OpenAI-compatible API."""
        client = get_llm_client()
        return await client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )

    def _parse_response(self, response_text: str) -> Optional[Dict]:
        """Parse Claude response to structured format."""
        try:
            # Extract JSON from response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start == -1 or json_end <= json_start:
                return None

            json_str = response_text[json_start:json_end]
            data = json.loads(json_str)

            # Validate required fields
            required = ["direction", "conviction", "key_triggers", "reasoning"]
            if not all(field in data for field in required):
                return None

            # Clamp conviction
            conviction = max(0, min(100, float(data.get("conviction", 50))))
            data["conviction"] = conviction

            return data
        except (json.JSONDecodeError, ValueError, AttributeError):
            return None

    def _consensus_direction(self, directions: List[str]) -> str:
        """Get consensus direction from multiple samples."""
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
        """Fallback response if parsing fails."""
        return AgentResponse(
            agent_name=self.name,
            agent_type=self.agent_type,
            direction="HOLD",
            conviction=30,
            reasoning="Unable to parse market signals. Holding neutral position.",
            key_triggers=["Parsing error", "Reverting to neutral"],
            time_horizon=self.time_horizon,
            internal_consistency=0.3,
            reproducible=False,
        )
