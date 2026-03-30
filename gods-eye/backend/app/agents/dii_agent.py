"""DII (Domestic Institutional Investor) agent - LLM powered."""

import json
from typing import Optional, Dict, List
from app.auth.llm_client import get_llm_client
from app.agents.base_agent import BaseAgent
from app.api.schemas import AgentResponse, MarketInput
from app.config import config


class DIIAgent(BaseAgent):
    """Domestic Institutional Investor behavior simulation."""

    def __init__(self):
        super().__init__(
            name="DII Strategy Desk",
            persona="Large domestic mutual fund/pension manager tracking SIP inflows and sector mandates",
            decision_framework="SIP flows, SEBI mandate compliance, sector rotation, debt markets",
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
        """Analyze market from DII perspective."""

        if config.MOCK_MODE:
            from app.agents.mock_responses import MockResponseGenerator
            return MockResponseGenerator.generate(
                "DII", self.name, self.agent_type, self.time_horizon,
                market_data, round_num, other_agents_output, enriched_context,
            )

        other_context = ""
        if other_agents_output and round_num > 1:
            other_context = "\n\nOther agents' views from Round 1:\n"
            for agent_name, response in other_agents_output.items():
                other_context += f"- {agent_name}: {response.direction} (conviction: {response.conviction})\n"

        prompt = self._build_prompt(market_data, round_num, other_context, enriched_context)

        # Collect 3 parallel samples
        responses_list = []
        for sample_idx in range(config.SAMPLES_PER_AGENT):
            response_text = await self._call_llm(prompt)
            parsed = self._parse_response(response_text)
            if parsed:
                responses_list.append(parsed)

        if not responses_list:
            return self._fallback_response()

        # Consensus direction
        directions = [r["direction"] for r in responses_list]
        direction = self._consensus_direction(directions)

        # Average conviction with consistency penalty
        convictions = [r["conviction"] for r in responses_list]
        base_conviction = sum(convictions) / len(convictions)

        direction_agreement = directions.count(direction) / len(directions)
        consistency = direction_agreement * 0.7 + 0.3

        final_conviction = base_conviction * consistency

        # Aggregate
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
                    "sip_flow": f"${market_data.dii_flow_5d}M/5d",
                }
            },
            interaction_effects={
                "amplifies": ["Budget announcements", "RBI rate cuts"],
                "dampens": ["Short-term volatility"],
            },
            internal_consistency=consistency,
            reproducible=False,
            sample_variance=max(convictions) - min(convictions),
        )

    def _build_prompt(
        self, market_data: MarketInput, round_num: int, other_context: str,
        enriched_context: str = None,
    ) -> str:
        """Build DII-specific analysis prompt with enriched intelligence."""

        intel_section = ""
        if enriched_context:
            intel_section = f"""
INTELLIGENCE BRIEFING (pre-computed signals, knowledge graph, and your track record):
{enriched_context}

USE THIS BRIEFING to ground your analysis. The quantitative signals above are pre-computed
from real market data. Your past accuracy stats show where you've been right and wrong —
adjust your conviction accordingly.
"""

        return f"""You are a portfolio manager at a large Domestic Institutional Investor (DII) - think SBI MF, HDFC AMC, LIC,
UTI. You manage substantial AUM with SIP (Systematic Investment Plan) inflows from retail and institutional clients.

CURRENT MARKET DATA:
- Nifty 50 Spot: {market_data.nifty_spot}
- India VIX: {market_data.india_vix}
- 5-Day DII Flow: ${market_data.dii_flow_5d}M
- 5-Day FII Flow: ${market_data.fii_flow_5d}M
- USD/INR: {market_data.usd_inr}
- Put-Call Ratio: {market_data.pcr_index}
- Market Context: {market_data.context}
{intel_section}
DECISION FRAMEWORK:
As a DII, you focus on:
1. **SIP Flows**: Steady monthly inflows from 50M+ SIP accounts
2. **Mandate Compliance**: Sector allocation limits, debt/equity ratios
3. **Valuation**: Nifty P/E, dividend yield, earnings growth
4. **Interest Rates**: RBI repo rate (affects bond allocation)
5. **Fund Performance**: Benchmark tracking (BSE 200)
6. **Regulatory**: SEBI disclosure rules, sector caps

KEY CONSIDERATIONS FOR DIIs:
- You have predictable monthly SIP inflows (stabilizing force)
- You track Nifty dividend yield vs 10-year gilt yields
- You avoid concentrated bets (sector exposure limits)
- You rebalance when P/E becomes extreme
- You're long-term holders (benefit from equity risk premium)

DECISION REQUIREMENTS:
Respond ONLY with valid JSON:
{{
  "direction": "STRONG_BUY" | "BUY" | "HOLD" | "SELL" | "STRONG_SELL",
  "conviction": <0-100>,
  "key_triggers": ["trigger1", "trigger2", "trigger3"],
  "reasoning": "Your analysis in 2-3 sentences.",
  "sip_impact": "How SIP flows affect your view",
  "valuation_assessment": "Fair value assessment",
  "interaction_notes": "How other agents' views matter"
}}

Current round: {round_num}/3
{other_context}

As a DII manager:
- You deploy SIP inflows gradually (don't time market)
- You rebalance occasionally but not aggressively
- You care about dividend yield and earnings quality
- You prefer stable, quality stocks
- You reduce exposure if valuations become extreme

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
            conviction=35,
            reasoning="Unable to parse signals. Deploying SIP inflows at current levels.",
            key_triggers=["Parsing error", "Continuing SIP"],
            time_horizon=self.time_horizon,
            internal_consistency=0.3,
            reproducible=False,
        )
