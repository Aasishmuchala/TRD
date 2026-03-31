"""RBI Policy agent - LLM powered."""

import json
from typing import Optional, Dict, List
from app.auth.llm_client import get_llm_client
from app.agents.base_agent import BaseAgent
from app.api.schemas import AgentResponse, MarketInput
from app.config import config


class RBIPolicyAgent(BaseAgent):
    """RBI (Reserve Bank of India) policy response simulation."""

    def __init__(self):
        super().__init__(
            name="RBI Policy Desk",
            persona="RBI monetary policy committee focusing on inflation control and financial stability",
            decision_framework="CPI/WPI inflation, forex reserves, repo rate corridor, growth vs inflation",
            risk_appetite="Conservative",
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
        """Analyze market from RBI policy perspective."""

        if config.MOCK_MODE:
            from app.agents.mock_responses import MockResponseGenerator
            return MockResponseGenerator.generate(
                "RBI", self.name, self.agent_type, self.time_horizon,
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
                "quarterly": {
                    "direction": direction,
                    "conviction": final_conviction,
                    "dxy": f"{market_data.dxy}",
                    "usd_inr": f"{market_data.usd_inr}",
                }
            },
            interaction_effects={
                "amplifies": ["Global risk-off events", "Rupee weakness"],
                "dampens": ["Domestic growth concerns"],
            },
            internal_consistency=consistency,
            reproducible=False,
            sample_variance=max(convictions) - min(convictions),
        )

    def _build_prompt(
        self, market_data: MarketInput, round_num: int, other_context: str,
        enriched_context: str = None,
    ) -> str:
        """Build RBI policy analysis prompt with enriched intelligence."""

        intel_section = ""
        if enriched_context:
            intel_section = f"""
INTELLIGENCE BRIEFING (pre-computed signals, knowledge graph, and your track record):
{enriched_context}

USE THIS BRIEFING to ground your analysis. The quantitative signals above are pre-computed
from real market data. Your past accuracy stats show where you've been right and wrong —
adjust your conviction accordingly.
"""

        return f"""You are the RBI (Reserve Bank of India) Monetary Policy Committee analyzing market conditions.
Your mandate is price stability (inflation), financial system stability, and growth support.

CURRENT MACROECONOMIC DATA:
- Nifty 50 Spot: {market_data.nifty_spot}
- India VIX: {market_data.india_vix}
- USD/INR: {market_data.usd_inr} (rupee weakness = inflation risk)
- US Dollar Index (DXY): {market_data.dxy}
- FII Flow (5d): ${market_data.fii_flow_5d}M (large outflows = rupee pressure)
- Market Context: {market_data.context}
{intel_section}
RBI POLICY FRAMEWORK:
You consider:
1. **Inflation Target**: RBI aims for 4% CPI (band: 2-6%)
2. **Repo Rate Corridor**: Repo rate vs reverse repo
3. **Rupee Strength**: If INR weakens > 2% in month, RBI may intervene
4. **Forex Reserves**: If dropping rapidly, RBI cuts off outflows
5. **Growth vs Inflation**: RBI faces rate cut/hike tradeoff
6. **Global Policy**: Fed rate path influences RBI decisions

KEY RBI BEHAVIORS:
- RBI cuts rates if inflation trends down OR growth stalls
- RBI hikes if CPI accelerates (especially food/energy)
- RBI intervenes in forex to defend rupee if needed
- RBI follows a data-dependent approach (next 6-8 months)
- Weak rupee = higher import inflation = hawkish bias
- Strong rupee + low inflation = dovish bias (rate cut potential)

DECISION REQUIREMENTS:
Respond ONLY with valid JSON:
{{
  "direction": "STRONG_BUY" | "BUY" | "HOLD" | "SELL" | "STRONG_SELL",
  "conviction": <0-100>,
  "key_triggers": ["trigger1", "trigger2", "trigger3"],
  "reasoning": "Your analysis in 2-3 sentences.",
  "policy_stance": "Dovish/Neutral/Hawkish",
  "next_action": "Cut/Hold/Hike in next review",
  "interaction_notes": "How market affects RBI decisions"
}}

Current round: {round_num}/3
{other_context}

INTERPRETATION FOR MARKET:
- RBI "STRONG_BUY" = rate cuts coming (bullish for equities)
- RBI "BUY" = cautiously dovish (slight easing)
- RBI "HOLD" = status quo (neutral)
- RBI "SELL" = tightening bias (bearish)
- RBI "STRONG_SELL" = aggressive tightening (very bearish)

As RBI, assess the macroeconomic backdrop and set a policy stance that maintains
inflation control while supporting growth. Remember: RBI decisions take 6-8 weeks
to propagate through the economy.

Your assessment:"""

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
            reasoning="Unable to parse policy signals. RBI maintains status quo.",
            key_triggers=["Parsing error", "Policy on hold"],
            time_horizon=self.time_horizon,
            internal_consistency=0.3,
            reproducible=False,
        )
