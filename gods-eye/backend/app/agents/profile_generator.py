"""Agent profile generator — builds enriched context for each agent.

Adapted from MiroFish's oasis_profile_generator.py pattern.
Instead of generating random agent personalities, we build agent-specific
context packages that combine:
  1. Pre-computed quantitative signals (from SignalEngine)
  2. Structural market knowledge (from MarketKnowledgeGraph)
  3. Past performance memory (from AgentMemory)

This is the key integration point — it turns raw MarketInput into
agent-specific intelligence briefs.
"""

from typing import Dict, Optional
from app.api.schemas import MarketInput
from app.data.signal_engine import SignalEngine
from app.knowledge.market_graph import MarketKnowledgeGraph
from app.memory.agent_memory import AgentMemory
from app.learning.skill_store import get_skill_store


class ProfileGenerator:
    """Generates enriched analysis context for each agent archetype.

    Each agent receives a different "briefing" tailored to what matters
    for their decision framework. The FII agent gets flow Z-scores and
    USD analysis; the Retail agent gets expiry mechanics and PCR context.
    """

    def __init__(self, agent_memory: Optional[AgentMemory] = None):
        self.memory = agent_memory
        self.graph = MarketKnowledgeGraph

    def build_context(
        self,
        agent_key: str,
        market_data: MarketInput,
        round_num: int = 1,
    ) -> str:
        """Build enriched context string for an agent.

        Returns a text block to prepend to the agent's analysis prompt,
        containing pre-computed signals, market structure knowledge,
        and past performance feedback.
        """
        sections = []

        # 1. Agent-specific quantitative signals
        signals_section = self._build_signal_context(agent_key, market_data)
        if signals_section:
            sections.append(signals_section)

        # 2. Structural market knowledge
        knowledge_section = self.graph.get_context_for_agent(agent_key, market_data.context)
        if knowledge_section:
            sections.append(knowledge_section)

        # 3. Affected sectors analysis
        affected = self.graph.get_affected_sectors(market_data.context)
        if affected:
            sector_lines = ["SECTORS MOST AFFECTED BY CURRENT SCENARIO:"]
            for s in affected[:5]:
                sector_lines.append(
                    f"  {s['sector']}: {s['direction'].upper()} impact ({s['impact']:+.2f}) — {', '.join(s['reasons'])}"
                )
            sections.append("\n".join(sector_lines))

        # 4. Past performance memory (only if we have data)
        if self.memory:
            memory_section = self.memory.get_agent_history_summary(agent_key)
            if memory_section:
                sections.append(memory_section)

        # 5. Learned skills (auto-learning patterns)
        try:
            skill_store = get_skill_store()
            market_dict = {
                "nifty_spot": market_data.nifty_spot,
                "india_vix": market_data.india_vix,
                "fii_flow_5d": market_data.fii_flow_5d,
                "dii_flow_5d": market_data.dii_flow_5d,
                "usd_inr": market_data.usd_inr,
                "dxy": market_data.dxy,
                "pcr_index": market_data.pcr_index,
                "max_pain": market_data.max_pain,
                "dte": market_data.dte,
            }
            skill_context = skill_store.build_skill_context(agent_key, market_dict)
            if skill_context:
                sections.append(skill_context)
        except Exception:
            pass  # Skills are optional enhancement

        return "\n\n".join(sections)

    def _build_signal_context(self, agent_key: str, market_data: MarketInput) -> str:
        """Build agent-specific pre-computed signal package.

        The plan says: "When the FII agent sees Z-score: -2.3, it knows this
        is a statistically extreme event, not just FII sold a lot."
        """
        # Compute all signals first
        all_signals = SignalEngine.process_market_input(market_data)

        if agent_key == "FII":
            return self._fii_signals(market_data, all_signals)
        elif agent_key == "DII":
            return self._dii_signals(market_data, all_signals)
        elif agent_key == "RETAIL_FNO":
            return self._retail_signals(market_data, all_signals)
        elif agent_key == "ALGO":
            return self._algo_signals(market_data, all_signals)
        elif agent_key == "PROMOTER":
            return self._promoter_signals(market_data, all_signals)
        elif agent_key == "RBI":
            return self._rbi_signals(market_data, all_signals)
        return ""

    def _fii_signals(self, md: MarketInput, signals: Dict) -> str:
        """FII agent: flow Z-scores, USD analysis, EM positioning."""
        lines = ["PRE-COMPUTED QUANTITATIVE SIGNALS (for your analysis):"]

        # FII flow analysis
        fii_flow = md.fii_flow_5d
        fii_intensity = "extreme selling" if fii_flow < -300 else "heavy selling" if fii_flow < -100 else \
                        "mild selling" if fii_flow < 0 else "mild buying" if fii_flow < 100 else \
                        "heavy buying" if fii_flow < 300 else "extreme buying"
        lines.append(f"  FII 5-day flow: ${fii_flow:.0f}M ({fii_intensity})")

        # DXY context
        dxy = md.dxy
        dxy_regime = "very strong USD" if dxy > 108 else "strong USD" if dxy > 105 else \
                     "neutral USD" if dxy > 100 else "weak USD"
        lines.append(f"  DXY: {dxy:.1f} ({dxy_regime})")

        # USD/INR analysis
        usd_inr = md.usd_inr
        inr_pressure = "severe depreciation" if usd_inr > 85 else "moderate depreciation" if usd_inr > 84 else \
                       "mild pressure" if usd_inr > 83 else "stable" if usd_inr > 82 else "INR strength"
        lines.append(f"  USD/INR: {usd_inr:.2f} ({inr_pressure})")

        # Technical signals
        rsi = signals.get("rsi", 50)
        rsi_signal = signals.get("rsi_interpretation", "neutral")
        lines.append(f"  Nifty RSI(14): {rsi:.1f} — {rsi_signal}")

        vix = md.india_vix
        vix_regime = signals.get("vix_regime", "normal")
        lines.append(f"  India VIX: {vix:.1f} ({vix_regime})")

        # Net flow vs DII comparison
        dii_flow = md.dii_flow_5d
        net_institutional = fii_flow + dii_flow
        lines.append(f"  Net institutional flow (FII + DII): ${net_institutional:.0f}M")
        if fii_flow < 0 and dii_flow > 0:
            absorption = min(abs(dii_flow / fii_flow), 1.0) if fii_flow != 0 else 0
            lines.append(f"  DII absorption rate: {absorption:.0%} of FII selling")

        return "\n".join(lines)

    def _dii_signals(self, md: MarketInput, signals: Dict) -> str:
        """DII agent: valuation context, SIP deployment, sector rotation signals."""
        lines = ["PRE-COMPUTED QUANTITATIVE SIGNALS (for your analysis):"]

        # DII flow
        dii_flow = md.dii_flow_5d
        lines.append(f"  DII 5-day flow: ${dii_flow:.0f}M")

        # Valuation context (Nifty level relative to bands)
        bb = signals.get("bollinger_bands", {})
        bb_position = bb.get("position", 0.5)
        val_context = "above upper band (overvalued)" if bb_position > 0.9 else \
                      "upper half (slightly rich)" if bb_position > 0.6 else \
                      "middle band (fair value)" if bb_position > 0.4 else \
                      "lower half (attractive)" if bb_position > 0.1 else \
                      "below lower band (deep value)"
        lines.append(f"  Nifty Bollinger position: {bb_position:.2f} — {val_context}")

        # FII selling creates DII opportunity
        fii_flow = md.fii_flow_5d
        if fii_flow < -100:
            lines.append(f"  FII selling ${abs(fii_flow):.0f}M — potential deployment opportunity")

        # RSI for contrarian signals
        rsi = signals.get("rsi", 50)
        if rsi < 35:
            lines.append(f"  RSI at {rsi:.0f} (oversold) — DII typically accumulates at these levels")
        elif rsi > 70:
            lines.append(f"  RSI at {rsi:.0f} (overbought) — DII typically slows deployment")

        vix = md.india_vix
        vix_regime = signals.get("vix_regime", "normal")
        lines.append(f"  India VIX: {vix:.1f} ({vix_regime})")

        return "\n".join(lines)

    def _retail_signals(self, md: MarketInput, signals: Dict) -> str:
        """Retail F&O agent: expiry mechanics, PCR, max pain analysis."""
        lines = ["PRE-COMPUTED QUANTITATIVE SIGNALS (for your analysis):"]

        # PCR analysis
        pcr = md.pcr_index
        pcr_regime = signals.get("pcr_regime", "neutral")
        lines.append(f"  PCR (Index): {pcr:.2f} ({pcr_regime})")

        # Max pain analysis
        max_pain = md.max_pain
        spot = md.nifty_spot
        distance = spot - max_pain
        distance_pct = (distance / max_pain) * 100 if max_pain else 0
        pain_context = "above max pain" if distance > 0 else "below max pain"
        lines.append(f"  Max Pain: {max_pain:.0f} | Spot: {spot:.0f} | {pain_context} by {abs(distance):.0f} pts ({abs(distance_pct):.1f}%)")

        # DTE context
        dte = md.dte
        expiry_urgency = "EXPIRY DAY — gamma exposure extremely high" if dte == 0 else \
                         "1 day to expiry — theta decay accelerating" if dte == 1 else \
                         f"{dte} days to expiry" if dte <= 3 else \
                         f"{dte} days to expiry (low time decay pressure)"
        lines.append(f"  DTE: {expiry_urgency}")

        # VIX for premium context
        vix = md.india_vix
        premium_context = "very expensive premiums" if vix > 25 else "elevated premiums" if vix > 18 else \
                          "normal premiums" if vix > 12 else "cheap premiums (sellers beware)"
        lines.append(f"  India VIX: {vix:.1f} — {premium_context}")

        # RSI momentum
        rsi = signals.get("rsi", 50)
        lines.append(f"  RSI(14): {rsi:.1f} — {'overbought, puts may be cheap' if rsi > 70 else 'oversold, calls may be cheap' if rsi < 30 else 'neutral'}")

        return "\n".join(lines)

    def _algo_signals(self, md: MarketInput, signals: Dict) -> str:
        """Algo agent gets ALL signals — it's the quant engine."""
        # The algo agent computes its own signals, but we provide
        # pre-computed ones as validation/additional context
        lines = ["PRE-COMPUTED SIGNAL VALIDATION:"]

        rsi = signals.get("rsi", 50)
        lines.append(f"  RSI(14): {rsi:.1f}")

        bb = signals.get("bollinger_bands", {})
        lines.append(f"  BB Position: {bb.get('position', 0.5):.2f}")
        lines.append(f"  BB Level: {bb.get('level', 'middle')}")

        vix_regime = signals.get("vix_regime", "normal")
        lines.append(f"  VIX Regime: {vix_regime}")

        pcr_regime = signals.get("pcr_regime", "neutral")
        lines.append(f"  PCR Regime: {pcr_regime}")

        return "\n".join(lines)

    def _promoter_signals(self, md: MarketInput, signals: Dict) -> str:
        """Promoter agent: price action context for insider perspective."""
        lines = ["PRE-COMPUTED QUANTITATIVE SIGNALS (for your analysis):"]

        spot = md.nifty_spot
        bb = signals.get("bollinger_bands", {})
        bb_position = bb.get("position", 0.5)

        lines.append(f"  Nifty Spot: {spot:.0f}")
        lines.append(f"  Bollinger Band Position: {bb_position:.2f}")

        # Promoter cares about stability
        vix = md.india_vix
        stability = "highly volatile (pledge risk elevated)" if vix > 25 else \
                    "moderately volatile" if vix > 18 else "stable market conditions"
        lines.append(f"  Market Stability: VIX {vix:.1f} — {stability}")

        # FII/DII flows affect promoter sentiment
        fii_flow = md.fii_flow_5d
        if fii_flow < -200:
            lines.append(f"  FII heavy selling (${fii_flow:.0f}M) — stock prices under pressure, pledge ratios may trigger")

        return "\n".join(lines)

    def _rbi_signals(self, md: MarketInput, signals: Dict) -> str:
        """RBI agent: macro indicators for monetary policy perspective."""
        lines = ["PRE-COMPUTED QUANTITATIVE SIGNALS (for your analysis):"]

        # INR pressure
        usd_inr = md.usd_inr
        inr_annual_change = ((usd_inr - 82.0) / 82.0) * 100  # Rough baseline
        lines.append(f"  USD/INR: {usd_inr:.2f} (approx {inr_annual_change:+.1f}% from 82 baseline)")

        # DXY global context
        dxy = md.dxy
        lines.append(f"  DXY: {dxy:.1f}")

        # VIX as financial stability indicator
        vix = md.india_vix
        stability_risk = "SYSTEMIC RISK — may require intervention" if vix > 30 else \
                         "elevated market stress" if vix > 22 else \
                         "moderate stress" if vix > 16 else "financial markets stable"
        lines.append(f"  India VIX: {vix:.1f} — {stability_risk}")

        # Flow balance
        fii_flow = md.fii_flow_5d
        dii_flow = md.dii_flow_5d
        net = fii_flow + dii_flow
        lines.append(f"  Net institutional flow: ${net:.0f}M (FII: ${fii_flow:.0f}M, DII: ${dii_flow:.0f}M)")

        if fii_flow < -300:
            lines.append(f"  ALERT: Severe FII outflow — may warrant RBI forex intervention")

        return "\n".join(lines)
