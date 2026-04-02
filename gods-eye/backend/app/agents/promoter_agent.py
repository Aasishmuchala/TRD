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
        """Build promoter analysis prompt with enriched intelligence."""

        intel_section = ""
        if enriched_context:
            intel_section = f"""
INTELLIGENCE BRIEFING (pre-computed signals, knowledge graph, and your track record):
{enriched_context}

USE THIS BRIEFING to ground your analysis. The quantitative signals above are pre-computed
from real market data. Your past accuracy stats show where you've been right and wrong —
adjust your conviction accordingly.
"""

        return f"""You are a company promoter/insider analyzing your stock's performance and control implications.
Your primary goal is maintaining promoter control while maximizing shareholder value.

CURRENT MARKET DATA:
- Stock Price: {market_data.nifty_spot} (proxy for typical stock)
- Index VIX: {market_data.india_vix}
- Market Liquidity: Reflected by FII/DII flows
- FII Flow (5d): ${market_data.fii_flow_5d}M
- DII Flow (5d): ${market_data.dii_flow_5d}M
- Market Context: {market_data.context}
{intel_section}
PROMOTER DECISION FRAMEWORK:
As a promoter, you focus on:
1. **Pledge Ratios**: If > 35%, you risk losing control in a downturn
2. **Stock Valuation**: Is current price fair? Should you buy more or trim exposure?
3. **Bulk/Block Deals**: Strategic timing for stake increases/decreases
4. **SEBI Disclosure**: Mandatory after 2% change in holding
5. **Control Maintenance**: Keeping >50% ownership (or family + allies)
6. **Capital Raising**: Using stock for fundraising at good valuations

KEY BEHAVIORS OF PROMOTERS:
- You buy when pledged shares are underwater (lower pledge ratio)
- You sell when stock is overvalued (take profits)
- You time SEBI filings strategically
- You react to downside risk (avoid loss of control)
- You support stock through selective buying in downturns
- You monitor competitor actions and hostile takeover risk

DECISION REQUIREMENTS:
You MUST take a directional stance — BUY or SELL. HOLD is only acceptable when bullish and bearish signals are perfectly balanced. In real markets, there is almost always a lean. A derivatives trader needs a direction, not indecision.

Respond ONLY with valid JSON (no markdown, no code blocks):
{{
  "direction": "STRONG_BUY" | "BUY" | "SELL" | "STRONG_SELL" | "HOLD",
  "conviction": <0-100>,
  "key_triggers": ["trigger1", "trigger2", "trigger3"],
  "reasoning": "Your analysis in 2-3 sentences. Explain WHY you lean this direction.",
  "control_status": "Status of control (safe/at_risk/threatened)",
  "action": "Buy/Hold/Trim based on control dynamics",
  "interaction_notes": "How broader market affects control"
}}

Current round: {round_num}/3
{other_context}

As a promoter:
- You're conservative (don't want to lose control)
- You support stock during sharp declines
- You take advantage of rallies to trim overvalued positions
- You coordinate with allies to strengthen control
- You avoid sector-wide downturns becoming company-specific crises

Your strategic assessment:"""

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM via Anthropic-compatible API."""
        client = get_llm_client()
        return await client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a decisive quantitative trading analyst for Indian equity derivatives. You MUST respond with ONLY valid JSON — no markdown, no code fences, no explanation text. You MUST pick BUY or SELL. HOLD is a cop-out — only use it when signals are exactly 50/50. A trader paying for your analysis needs a direction."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=50000,
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
        elif avg_score > 0.17:
            return "BUY"
        elif avg_score > -0.17:
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
