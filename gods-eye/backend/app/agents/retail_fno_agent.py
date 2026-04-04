"""Retail F&O (Futures & Options) agent - LLM powered."""

import json
from typing import Optional, Dict, List
from app.auth.llm_client import get_llm_client
from app.agents.base_agent import BaseAgent
from app.api.schemas import AgentResponse, MarketInput
from app.config import config


class RetailFNOAgent(BaseAgent):
    """Retail F&O trader behavior simulation (Zerodha, Groww, etc.)."""

    def __init__(self):
        super().__init__(
            name="Retail F&O Desk",
            persona="Retail derivatives trader on Zerodha/Groww focused on intraday volatility and expiry plays",
            decision_framework="Technical levels, expiry dynamics, gamma positioning, social sentiment",
            risk_appetite="Aggressive",
            time_horizon="Intraday",
            agent_type="LLM",
        )

    async def analyze(
        self,
        market_data: MarketInput,
        round_num: int = 1,
        other_agents_output: Optional[Dict[str, AgentResponse]] = None,
        enriched_context: Optional[str] = None,
    ) -> AgentResponse:
        """Analyze market from retail F&O perspective."""

        if config.MOCK_MODE:
            from app.agents.mock_responses import MockResponseGenerator
            return MockResponseGenerator.generate(
                "RETAIL_FNO", self.name, self.agent_type, self.time_horizon,
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
        direction_agreement = directions.count(direction) / len(directions)
        consistency = direction_agreement * 0.7 + 0.3  # kept for logging/metadata only
        winning_convictions = [r["conviction"] for r in responses_list if r["direction"] == direction]
        final_conviction = sum(winning_convictions) / len(winning_convictions) if winning_convictions else sum(convictions) / len(convictions)

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
                "intraday": {
                    "direction": direction,
                    "conviction": final_conviction,
                    "dte": f"{market_data.dte} days",
                    "max_pain": market_data.max_pain,
                }
            },
            interaction_effects={
                "amplifies": ["Volatility spikes", "Expiry week dynamics"],
                "dampens": ["Long-term trends"],
            },
            internal_consistency=consistency,
            reproducible=False,
            sample_variance=max(convictions) - min(convictions),
        )

    def _build_prompt(
        self, market_data: MarketInput, round_num: int, other_context: str,
        enriched_context: str = None,
    ) -> str:
        """Build retail F&O analysis prompt with enriched intelligence."""

        intel_section = ""
        if enriched_context:
            intel_section = f"""
INTELLIGENCE BRIEFING (pre-computed signals, knowledge graph, and your track record):
{enriched_context}

USE THIS BRIEFING to ground your analysis. The quantitative signals above are pre-computed
from real market data. Your past accuracy stats show where you've been right and wrong —
adjust your conviction accordingly.
"""

        return f"""You are a retail trader on Zerodha/Groww trading index and stock derivatives (F&O).
You are aggressive, focused on intraday moves and expiry-week gamma plays. You track social media sentiment,
round levels, and max pain dynamics.

CURRENT MARKET DATA:
- Nifty 50 Spot: {market_data.nifty_spot}
- India VIX: {market_data.india_vix}
- Days to Expiry (DTE): {market_data.dte}
- Max Pain Level: {market_data.max_pain}
- Put-Call Ratio: {market_data.pcr_index}
- PCR Stock (average): {market_data.pcr_stock}
- Market Context: {market_data.context}
{intel_section}
RETAIL F&O TRADER FRAMEWORK:
You care about:
1. **Expiry Dynamics**: Max pain, gamma squeezes, pin risk
2. **Technical Levels**: Round numbers (19,900, 20,000, 20,100), support/resistance
3. **VIX Regime**: High VIX = short straddles, low VIX = directional bets
4. **PCR Extremes**: PCR > 1.5 = bullish setup, PCR < 0.8 = bearish
5. **Social Sentiment**: Retail chatter on Twitter/Discord (BULLISH/BEARISH)
6. **Gamma Positioning**: Which way likely to move before expiry?

KEY BEHAVIORS OF RETAIL F&O TRADERS:
- You trade intraday, hold overnight occasionally
- You love momentum and volatility
- Round numbers are magnets (e.g., 20,000)
- Max pain is your "fair value" estimate
- High conviction on short-term moves (next 1-3 days)
- You sell options premium when VIX is high

DECISION REQUIREMENTS:
You MUST take a directional stance — BUY or SELL. HOLD is only acceptable when bullish and bearish signals are perfectly balanced. In real markets, there is almost always a lean. A derivatives trader needs a direction, not indecision.

Respond ONLY with valid JSON (no markdown, no code blocks):
{{
  "direction": "STRONG_BUY" | "BUY" | "SELL" | "STRONG_SELL" | "HOLD",
  "conviction": <0-100>,
  "key_triggers": ["trigger1", "trigger2", "trigger3"],
  "reasoning": "Your analysis in 2-3 sentences. Explain WHY you lean this direction.",
  "expiry_view": "Direction expected by expiry",
  "round_level": "Key round level to watch",
  "interaction_notes": "How others' bets affect yours"
}}

Current round: {round_num}/3
{other_context}

As a retail F&O trader:
- You're directional on short timeframes
- Expiry weeks are your hunting ground
- You follow the crowd when sentiment is extreme
- You take quick profits (don't hold losers)
- Round levels attract options sellers/buyers

Your aggressive assessment:"""

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
            reasoning="Unable to parse signals. Waiting for clear direction.",
            key_triggers=["Parsing error", "No clear setup"],
            time_horizon=self.time_horizon,
            internal_consistency=0.3,
            reproducible=False,
        )
