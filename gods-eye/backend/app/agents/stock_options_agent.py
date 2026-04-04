"""Stock Options Desk agent — qualitative analysis for NIFTY50 stock options.

This agent focuses on individual stock options rather than index options:
- IV rank and premium cheapness for 1–5 day positional plays
- Upcoming catalysts (results, management commentary, sector rotation)
- Stock-level FII/DII flows and bulk/block deal patterns
- Lot-size affordability filtering for ₹10,000 capital

Weight: 0.07 (drawn from DII reduction: 0.25 → 0.18)
Expiry preference: weekly (conviction ≥ 75) or monthly (conviction 70–74)
Universe: top 25 NIFTY50 stocks by options open interest
"""

import json
from typing import Optional, Dict, List

from app.auth.llm_client import get_llm_client
from app.agents.base_agent import BaseAgent
from app.api.schemas import AgentResponse, MarketInput
from app.config import config
from app.engine.options_pnl import (
    STOCK_LOT_SIZES, select_dte, estimate_atm_premium,
    max_affordable_lots, NIFTY_LOT_SIZE,
)


# Top 25 NIFTY50 stocks by options OI — most liquid for ₹10k trades
TOP_25_STOCKS = list(STOCK_LOT_SIZES.keys())

# Premium budget limit: never recommend a lot costing more than ₹9,000
MAX_LOT_COST_INR = 9_000.0


class StockOptionsAgent(BaseAgent):
    """Stock Options Desk — positional stock options for 1–5 day holds."""

    def __init__(self):
        super().__init__(
            name="Stock Options Desk",
            persona=(
                "Prop desk trader specialising in NIFTY50 stock options for "
                "1–5 day positional trades. Expert at finding underpriced volatility, "
                "reading FII block flows at stock level, and timing entry around "
                "events (results, AGMs, bulk deals, sector rotation)."
            ),
            decision_framework=(
                "IV rank analysis, upcoming catalysts, sector momentum, "
                "lot-size affordability within ₹10,000 capital"
            ),
            risk_appetite="Aggressive",
            time_horizon="Short-Term",
            agent_type="LLM",
        )

    async def analyze(
        self,
        market_data: MarketInput,
        round_num: int = 1,
        other_agents_output: Optional[Dict[str, AgentResponse]] = None,
        enriched_context: Optional[str] = None,
    ) -> AgentResponse:
        """Analyse which stock options offer the best 1–5 day setup."""

        if config.MOCK_MODE:
            from app.agents.mock_responses import MockResponseGenerator
            return MockResponseGenerator.generate(
                "STOCK_OPTIONS", self.name, self.agent_type, self.time_horizon,
                market_data, round_num, other_agents_output, enriched_context,
            )

        other_context = ""
        if other_agents_output and round_num > 1:
            # Align with macro direction from FII and DII
            macro_agents = ["FII Flows Analyst", "DII Strategy Desk"]
            other_context = "\n\nMacro agents' consensus from Round 1:\n"
            for agent_name, response in other_agents_output.items():
                if any(m in agent_name for m in macro_agents):
                    other_context += (
                        f"- {agent_name}: {response.direction} "
                        f"(conviction: {response.conviction:.0f})\n"
                    )
            if not other_context.strip().endswith("1:\n"):
                other_context += "\nAlign stock picks with macro direction above.\n"

        prompt = self._build_prompt(market_data, round_num, other_context, enriched_context)

        responses_list = []
        for _ in range(config.SAMPLES_PER_AGENT):
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
        top_stock = responses_list[0].get("top_stock_pick", "")
        iv_rank = responses_list[0].get("iv_rank_estimate", 50)
        expiry_pref = responses_list[0].get("expiry_preference", "weekly")

        return AgentResponse(
            agent_name=self.name,
            agent_type=self.agent_type,
            direction=direction,
            conviction=final_conviction,
            reasoning=reasoning,
            key_triggers=key_triggers,
            time_horizon=self.time_horizon,
            views={
                "stock_options": {
                    "direction": direction,
                    "conviction": final_conviction,
                    "top_stock_pick": top_stock,
                    "iv_rank_estimate": iv_rank,
                    "expiry_preference": expiry_pref,
                    "dte_recommendation": select_dte(final_conviction),
                }
            },
            interaction_effects={
                "amplifies": ["FII stock-level flows", "Sector momentum", "Event catalysts"],
                "dampens": ["Macro headwinds opposing stock trend"],
            },
            internal_consistency=consistency,
            reproducible=False,
            sample_variance=max(convictions) - min(convictions) if len(convictions) > 1 else 0.0,
        )

    def _build_prompt(
        self,
        market_data: MarketInput,
        round_num: int,
        other_context: str,
        enriched_context: Optional[str],
    ) -> str:
        """Build the stock options analysis prompt."""

        intel_section = ""
        if enriched_context:
            intel_section = f"""
INTELLIGENCE BRIEFING (pre-computed signals, macro context, agent accuracy stats):
{enriched_context}

Use this briefing to identify which sectors or stocks align with today's macro setup.
"""

        # Build affordable lot info for context
        vix = market_data.india_vix or 15.0
        spot = market_data.nifty_spot or 22_000.0
        affordable_stocks = []
        for stock, lot_sz in STOCK_LOT_SIZES.items():
            # Approximate stock price as NIFTY × relative_weight (rough proxy)
            # Use ₹500–₹3000 range as typical NIFTY50 stock price range
            approx_price = 1500.0  # median NIFTY50 stock price
            prem = estimate_atm_premium(approx_price, vix, dte=5)
            cost = prem * lot_sz
            if cost <= MAX_LOT_COST_INR:
                affordable_stocks.append(f"{stock}(lot={lot_sz})")

        affordable_str = ", ".join(affordable_stocks[:15]) if affordable_stocks else "NIFTY index options"

        return f"""You are the Stock Options Desk at a prop trading firm in Mumbai.
You specialise in NIFTY50 stock options for 1–5 day positional trades with ₹10,000 capital.

CAPITAL CONSTRAINT: ₹10,000. Max 1 lot per trade. Only recommend stocks where 1 ATM lot ≤ ₹9,000.
Affordable universe today: {affordable_str}

CURRENT MARKET CONDITIONS:
- Nifty 50 Spot: {market_data.nifty_spot}
- India VIX: {market_data.india_vix} (higher VIX = more expensive premium — prefer stock options when VIX is calm)
- PCR Index: {market_data.pcr_index}
- PCR Stock (aggregate): {market_data.pcr_stock}
- DTE to expiry: {market_data.dte} days
- Market Context: {market_data.context}
{intel_section}
YOUR ANALYTICAL FRAMEWORK:

1. **IV Rank** (estimate from VIX and stock news):
   - IV rank < 30 → options CHEAP → good to BUY premium (directional)
   - IV rank > 70 → options EXPENSIVE → avoid buying, let IV mean-revert
   - IV rank 30–70 → neutral → only trade if catalyst is strong

2. **Catalyst Screening** (prioritise in this order):
   a) Results/earnings in next 5 days → high vol, strong directional move likely
   b) Sector rotation: which NIFTY50 sector is FII buying/selling today?
   c) Bulk/block deals in last 2 sessions → institutional conviction signal
   d) Technical breakout/breakdown from a key level

3. **Stock Selection Criteria** (must meet all 3):
   - Active options with tight bid-ask spread
   - Clear directional bias (at least 2 of 3 signals agree)
   - 1 ATM lot cost ≤ ₹9,000

4. **Direction Decision**:
   - BUY → buy CE on bullish stock setup
   - SELL → buy PE on bearish stock setup
   - HOLD → no clear stock setup OR VIX too high (options too expensive)

5. **Expiry Logic**:
   - High conviction (>75): weekly expiry (3–5 DTE) for max leverage
   - Moderate conviction (70–75): monthly expiry (15–20 DTE) for more buffer

DECISION REQUIREMENTS:
Pick the 1 BEST stock options setup for today. If no stock has a convincing setup,
say HOLD — capital preservation matters more than forcing a trade.
NIFTY index options are always an alternative if stocks have poor setups.

Round: {round_num}/3
{other_context}

Respond ONLY with valid JSON (no markdown, no code blocks):
{{
  "direction": "STRONG_BUY" | "BUY" | "SELL" | "STRONG_SELL" | "HOLD",
  "conviction": <0-100>,
  "top_stock_pick": "RELIANCE" or "NIFTY" (index) or "NONE",
  "option_type": "CE" | "PE" | "NONE",
  "iv_rank_estimate": <0-100>,
  "expiry_preference": "weekly" | "monthly",
  "key_triggers": ["trigger1", "trigger2", "trigger3"],
  "reasoning": "Your analysis in 2–3 sentences. WHY this stock, WHY this direction.",
  "risk_note": "What would invalidate this setup"
}}"""

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM via Anthropic-compatible API."""
        client = get_llm_client()
        return await client.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a decisive stock options trader for Indian equity derivatives. "
                        "You MUST respond with ONLY valid JSON — no markdown, no code fences. "
                        "Pick BUY or SELL when there is a clear edge. HOLD only when no stock "
                        "offers a clean risk/reward setup within ₹10,000 capital."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=50000,
        )

    def _parse_response(self, response_text: str) -> Optional[Dict]:
        """Parse LLM JSON response."""
        try:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start == -1 or json_end <= json_start:
                return None

            data = json.loads(response_text[json_start:json_end])

            required = ["direction", "conviction", "key_triggers", "reasoning"]
            if not all(f in data for f in required):
                return None

            data["conviction"] = max(0.0, min(100.0, float(data.get("conviction", 50))))
            return data

        except (json.JSONDecodeError, ValueError, AttributeError):
            return None

    def _consensus_direction(self, directions: List[str]) -> str:
        """Get consensus direction from multiple samples."""
        strength = {"STRONG_BUY": 2, "BUY": 1, "HOLD": 0, "SELL": -1, "STRONG_SELL": -2}
        score = sum(strength.get(d, 0) for d in directions)
        avg = score / len(directions) if directions else 0
        if avg > 1.3:
            return "STRONG_BUY"
        elif avg > 0.17:
            return "BUY"
        elif avg > -0.17:
            return "HOLD"
        elif avg > -1.3:
            return "SELL"
        else:
            return "STRONG_SELL"

    def _fallback_response(self) -> AgentResponse:
        """Fallback when LLM parsing fails."""
        return AgentResponse(
            agent_name=self.name,
            agent_type=self.agent_type,
            direction="HOLD",
            conviction=35.0,
            reasoning="No clear stock options setup identified. Preserving capital.",
            key_triggers=["Parsing failure", "No clean risk/reward", "Capital preservation"],
            time_horizon=self.time_horizon,
            views={"stock_options": {"direction": "HOLD", "top_stock_pick": "NONE"}},
            interaction_effects={},
            internal_consistency=0.3,
            reproducible=False,
            sample_variance=0.0,
        )
