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
        """Short directional signal prompt — single pass, no debate rounds."""

        intel_section = ""
        if enriched_context:
            intel_section = f"\nSIGNAL CONTEXT:\n{enriched_context}\n"

        max_pain_str = f"{market_data.max_pain:.0f}" if market_data.max_pain else "unknown"
        distance_to_max_pain = ""
        if market_data.max_pain:
            diff = market_data.nifty_spot - market_data.max_pain
            distance_to_max_pain = f" (spot is {abs(diff):.0f} pts {'above' if diff > 0 else 'below'} max pain)"

        return f"""You are analyzing retail F&O positioning as a CONTRARIAN signal. Retail traders are usually wrong at extremes — use their positioning to predict the opposite move.

MARKET DATA:
- Nifty Spot: {market_data.nifty_spot}
- Put-Call Ratio (PCR): {market_data.pcr_index} (above 1.2 = retail panic-buying puts = contrarian bullish; below 0.7 = retail buying calls = contrarian bearish)
- Max Pain Level: {max_pain_str}{distance_to_max_pain}
- Days to Expiry (DTE): {market_data.dte}
- India VIX: {market_data.india_vix}
- Market Context: {market_data.context}
{intel_section}
CONTRARIAN DECISION RULES:
- PCR > 1.4 → retail extremely bearish → STRONG_BUY (fade retail)
- PCR 1.2–1.4 → retail bearish → BUY
- PCR 0.8–1.2 → neutral positioning → HOLD
- PCR 0.6–0.8 → retail bullish → SELL (fade retail)
- PCR < 0.6 → retail extremely bullish → STRONG_SELL
- If spot is far from max pain (>150 pts) and DTE < 5, expect reversion toward max pain
- High VIX (>20) amplifies conviction; low VIX (<14) reduces it

Respond ONLY with valid JSON (no markdown):
{{
  "direction": "BUY" | "SELL" | "HOLD" | "STRONG_BUY" | "STRONG_SELL",
  "conviction": <0-100>,
  "key_triggers": ["trigger1", "trigger2"],
  "reasoning": "One or two sentences identifying the contrarian signal from PCR, max pain, and OI positioning."
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
            reasoning="Unable to parse signals. Waiting for clear direction.",
            key_triggers=["Parsing error", "No clear setup"],
            time_horizon=self.time_horizon,
            internal_consistency=0.3,
            reproducible=False,
        )
