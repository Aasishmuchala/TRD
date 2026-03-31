"""Algo/Quant agent — pure quantitative computation via QuantSignalEngine.

No LLM calls. Delegates entirely to QuantSignalEngine from Phase 10.
"""

from typing import Optional, Dict
from app.agents.base_agent import BaseAgent
from app.api.schemas import AgentResponse, MarketInput
from app.engine.quant_signal_engine import QuantSignalEngine, QuantInputs


# USD million to INR crore: 1 USD million ≈ 8.35 Cr at ~83.5 USD/INR
_USD_M_TO_CR = 8.35


class AlgoQuantAgent(BaseAgent):
    """Pure quantitative algorithm agent using QuantSignalEngine rules.

    Produces directional signal from RSI, PCR, VIX, FII flow, and Supertrend.
    Zero LLM calls. Deterministic and reproducible.
    """

    def __init__(self):
        super().__init__(
            name="Algo Trading Engine",
            persona="Pure quantitative algorithm analyzing technical signals",
            decision_framework="QuantSignalEngine rules: FII flow, PCR, RSI, VIX, Supertrend",
            risk_appetite="Moderate",
            time_horizon="Intraday",
            agent_type="QUANT",
        )

    async def analyze(
        self,
        market_data: MarketInput,
        round_num: int = 1,
        other_agents_output: Optional[Dict[str, AgentResponse]] = None,
        enriched_context: Optional[str] = None,
    ) -> AgentResponse:
        """Compute signal via QuantSignalEngine — no LLM, no custom math."""

        # Build QuantInputs from MarketInput
        # fii_flow_5d / dii_flow_5d are in USD millions; convert to INR crores
        fii_net_cr = (market_data.fii_flow_5d or 0.0) * _USD_M_TO_CR
        dii_net_cr = (market_data.dii_flow_5d or 0.0) * _USD_M_TO_CR

        rsi = market_data.rsi_14 if market_data.rsi_14 is not None else 50.0

        # vix_5d_avg not in MarketInput — use spot VIX as conservative fallback
        vix_5d_avg = market_data.india_vix

        # supertrend not in MarketInput — infer from RSI direction
        supertrend = "bearish" if rsi > 50 else "bullish"

        inputs = QuantInputs(
            fii_net_cr=fii_net_cr,
            dii_net_cr=dii_net_cr,
            pcr=market_data.pcr_index,
            rsi=rsi,
            vix=market_data.india_vix,
            vix_5d_avg=vix_5d_avg,
            supertrend=supertrend,
        )

        result = QuantSignalEngine.compute_quant_score(inputs, instrument="NIFTY")

        # Build key triggers from factors that fired
        key_triggers = []
        for factor_name, factor_data in result.factors.items():
            if factor_data.get("threshold_hit"):
                side = factor_data.get("side", "")
                pts = factor_data.get("points", 0)
                key_triggers.append(f"{factor_name} ({side}, +{pts}pts)")
        if not key_triggers:
            key_triggers = ["No threshold triggered — HOLD"]

        reasoning = (
            f"QuantSignalEngine: buy_pts={result.buy_points}, sell_pts={result.sell_points}, "
            f"score={result.total_score}, tier={result.tier}. "
            f"RSI={rsi:.1f}, PCR={market_data.pcr_index:.2f}, "
            f"VIX={market_data.india_vix:.1f}. "
            f"Direction: {result.direction}."
        )

        interaction_effects = {
            "amplifies": ["FII flow alignment", "PCR confirmation"],
            "dampens": ["Low conviction when no threshold fires"],
        }
        if result.tier == "strong":
            interaction_effects["amplifies"].append("Strong quant signal — high consensus weight")
        elif result.tier == "skip":
            interaction_effects["dampens"].append("Weak quant signal — reduced consensus weight")

        return AgentResponse(
            agent_name=self.name,
            agent_type=self.agent_type,
            direction=result.direction,
            conviction=float(result.total_score),
            reasoning=reasoning,
            key_triggers=key_triggers[:5],
            time_horizon=self.time_horizon,
            views={
                "intraday": {
                    "direction": result.direction,
                    "conviction": float(result.total_score),
                    "score": result.total_score,
                    "tier": result.tier,
                    "instrument_hint": result.instrument_hint,
                }
            },
            interaction_effects=interaction_effects,
            internal_consistency=1.0,
            reproducible=True,
        )
