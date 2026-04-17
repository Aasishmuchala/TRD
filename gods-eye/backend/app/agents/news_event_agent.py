"""NewsEvent Agent — macro event risk and news flow specialist.

This agent reasons about binary events (elections, RBI policy, budget, global shocks)
and VIX regime to determine whether directional trades should be taken at all.

Two modes:
  VETO mode  (pre-event / high VIX): outputs HOLD with high conviction to block the trade
  AMPLIFIER mode (post-event / clear outcome): outputs directional signal with context

This agent has veto power via BacktestEngine._compute_consensus():
  if NEWS_EVENT outputs HOLD with conviction >= 70, it overrides other agents.

Weight: 0.07 (smaller than core agents but with special override capability)
"""

import json
from typing import Optional, Dict
from app.agents.base_agent import BaseAgent
from app.api.schemas import AgentResponse, MarketInput
from app.auth.llm_client import get_llm_client
from app.config import config
from app.data.event_calendar import (
    classify_vix_regime,
    get_event_description,
    BLACKOUT_EVENT_TYPES,
    EXPIRY_WEEK,
)


class NewsEventAgent(BaseAgent):
    """News and macro event risk specialist for Indian equity derivatives."""

    def __init__(self):
        super().__init__(
            name="News & Event Risk Analyst",
            persona="Macro event specialist tracking binary event risk, VIX regime, and news flow for Indian markets",
            decision_framework=(
                "Event calendar awareness, VIX regime classification, "
                "pre/post-event binary risk assessment, news flow impact on market direction"
            ),
            risk_appetite="Conservative",
            time_horizon="Weekly",
            agent_type="LLM",
        )

    async def analyze(
        self,
        market_data: MarketInput,
        round_num: int = 1,
        other_agents_output: Optional[Dict[str, AgentResponse]] = None,
        enriched_context: Optional[str] = None,
    ) -> AgentResponse:
        """Analyze event risk and VIX regime."""

        if config.MOCK_MODE:
            from app.agents.mock_responses import MockResponseGenerator
            return MockResponseGenerator.generate(
                "NEWS_EVENT", self.name, self.agent_type, self.time_horizon,
                market_data, round_num, other_agents_output, enriched_context,
            )

        other_context = ""
        if other_agents_output and round_num > 1:
            other_context = "\n\nOther agents' views:\n"
            for agent_name, response in other_agents_output.items():
                other_context += f"- {agent_name}: {response.direction} (conviction: {response.conviction:.0f})\n"

        prompt = self._build_prompt(market_data, round_num, other_context, enriched_context)
        response_text = await self._call_llm(prompt)
        parsed = self._parse_response(response_text)

        if not parsed:
            return self._fallback_response(market_data)

        direction = parsed["direction"]
        conviction = float(parsed.get("conviction", 50))
        conviction = max(0.0, min(100.0, conviction))

        return AgentResponse(
            agent_name=self.name,
            agent_type=self.agent_type,
            direction=direction,
            conviction=conviction,
            reasoning=parsed.get("reasoning", ""),
            key_triggers=parsed.get("key_triggers", [])[:5],
            time_horizon=self.time_horizon,
            views={},
            interaction_effects={
                "amplifies": ["Event-driven volatility awareness"],
                "dampens": ["Directional conviction during binary events"],
            },
            internal_consistency=1.0,
            reproducible=True,
        )

    def _build_prompt(
        self,
        market_data: MarketInput,
        round_num: int,
        other_context: str,
        enriched_context: Optional[str],
    ) -> str:
        """Build NewsEvent-specific prompt."""

        vix = market_data.india_vix
        vix_regime = classify_vix_regime(vix)
        event_risk = market_data.event_risk or "none"

        # Determine if this is a known blackout event
        is_blackout = (
            event_risk == "pre_event_blackout"
            or any(event_risk == et.lower() for et in BLACKOUT_EVENT_TYPES)
        )
        is_post_event = event_risk.startswith("post_") if event_risk else False

        # Event description for context
        event_desc = ""
        if event_risk and event_risk != "none":
            # Map event_risk string back to type for description
            for etype in list(BLACKOUT_EVENT_TYPES) + [EXPIRY_WEEK]:
                if event_risk == etype.lower() or event_risk == f"post_{etype.lower()}":
                    event_desc = get_event_description(etype)
                    break
            if not event_desc:
                event_desc = f"Event context: {event_risk}"

        # VIX regime guidance
        vix_guidance = {
            "low":      "VIX is low — premium is cheap, directional trades have good R/R. Support directional signal.",
            "normal":   "VIX is in normal range — standard trading conditions. Evaluate signal normally.",
            "elevated": "VIX is elevated (16-20%) — options premiums are expensive. Raise your bar. Only support very high-conviction directional trades.",
            "high":     "VIX is HIGH (20-25%) — market is pricing in significant uncertainty. Recommend HOLD unless there is a post-event directional clarity.",
            "extreme":  "VIX is EXTREME (>25%) — options premiums are prohibitively expensive. Strong recommendation: HOLD. Do NOT take directional positions.",
        }.get(vix_regime, "")

        blackout_instruction = ""
        if is_blackout:
            blackout_instruction = """
CRITICAL: This date has a HIGH-IMPACT BINARY EVENT (election, budget, RBI policy, or shock).
Binary events have UNKNOWN outcomes. Directional options positions cannot predict the result.
The correct action is HOLD with HIGH CONVICTION (80-90).
You must output HOLD with conviction 80-90 to veto other agents' directional positions.
"""
        elif vix_regime in ("high", "extreme"):
            blackout_instruction = """
VIX is in high/extreme territory. The market is pricing in significant uncertainty.
Unless you have clear post-event directional evidence, output HOLD with conviction 75-85.
"""

        post_event_instruction = ""
        if is_post_event:
            post_event_instruction = """
This date is AFTER a major event has resolved. The binary uncertainty is now gone.
If the event outcome creates a clear directional bias (e.g., election result favoring markets,
RBI cut being bullish, budget being market-positive), you may support a directional call.
Use your knowledge of what typically follows such events in Indian markets.
"""

        return f"""You are a News and Event Risk Specialist for Indian equity derivatives trading.
Your role: assess whether today's market event risk and VIX regime makes a directional options trade SAFE or RISKY.

MARKET DATA:
- Nifty 50 Spot: {market_data.nifty_spot:.0f}
- India VIX: {vix:.1f} ({vix_regime.upper()} regime)
- Event Risk: {event_risk}
- Market Context: {market_data.context}
{f'- Event Description: {event_desc}' if event_desc else ''}

VIX REGIME GUIDANCE:
{vix_guidance}
{blackout_instruction}
{post_event_instruction}

DECISION FRAMEWORK:
1. Is there a BINARY EVENT today or tomorrow? (election, budget, RBI, macro shock) → HOLD with conviction 80-90
2. Is VIX > 20%? → HOLD with conviction 75-85 (expensive premium, chaotic direction)
3. Is VIX 16-20%? → Only support trades with VERY HIGH conviction from other agents
4. Post major event with clear outcome? → Support directional trade if thesis is clear
5. Normal conditions (VIX < 16, no events)? → Don't block other agents, HOLD only if you see specific event risk

YOUR SPECIFIC RESPONSIBILITY:
- You are the GATEKEEPER. Your HOLD signal (conviction ≥ 70) will BLOCK the trade.
- Do NOT call HOLD out of general uncertainty — only for SPECIFIC, IDENTIFIABLE event risks.
- In normal conditions, output BUY/SELL to align with the market narrative (don't add friction).

Round: {round_num}/3
{other_context}

Respond ONLY with valid JSON (no markdown, no code blocks):
{{
  "direction": "STRONG_BUY" | "BUY" | "HOLD" | "SELL" | "STRONG_SELL",
  "conviction": <0-100>,
  "key_triggers": ["trigger1", "trigger2", "trigger3"],
  "reasoning": "Your event risk assessment in 2-3 sentences. Explain WHY you are blocking or allowing the trade.",
  "vix_regime": "{vix_regime}",
  "event_risk_level": "low|medium|high|extreme"
}}

Your assessment:"""

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM via Anthropic-compatible API."""
        client = get_llm_client()
        return await client.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a binary event risk gatekeeper for Indian equity derivatives. "
                        "You MUST respond with ONLY valid JSON — no markdown, no code fences. "
                        "Your primary job is to block bad trades on event days and high-VIX regimes. "
                        "In normal conditions, do not add friction — support the market narrative."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=1024,
        )

    def _parse_response(self, response_text: str) -> Optional[Dict]:
        """Parse LLM response to structured format."""
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
            # ARCH-H4: Validate direction
            valid_directions = {"STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"}
            if data.get("direction") not in valid_directions:
                data["direction"] = "HOLD"

            data["conviction"] = max(0, min(100, float(data.get("conviction", 50))))
            return data
        except (json.JSONDecodeError, ValueError, AttributeError):
            return None

    def _fallback_response(self, market_data: MarketInput) -> AgentResponse:
        """Fallback: HOLD if we can't parse, be conservative."""
        vix = market_data.india_vix
        event_risk = market_data.event_risk or ""

        # If we know there's an event or high VIX, be conservative on fallback
        if event_risk == "pre_event_blackout" or vix > 20.0:
            direction = "HOLD"
            conviction = 75.0
            reason = f"Fallback: event risk={event_risk}, VIX={vix:.1f} — defaulting to HOLD"
        else:
            direction = "HOLD"
            conviction = 40.0
            reason = "Fallback: parse error, defaulting to neutral HOLD (low conviction)"

        return AgentResponse(
            agent_name=self.name,
            agent_type=self.agent_type,
            direction=direction,
            conviction=conviction,
            reasoning=reason,
            key_triggers=["Parse error", f"VIX={vix:.1f}", f"event_risk={event_risk}"],
            time_horizon=self.time_horizon,
            internal_consistency=0.5,
            reproducible=True,
        )
