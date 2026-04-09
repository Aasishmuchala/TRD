"""Algo/Quant agent — pure quantitative computation via QuantSignalEngine.

No LLM calls. Delegates entirely to QuantSignalEngine from Phase 10.
Includes VIX regime filter from Phase 3 profitability plan.
Computes RSI, Supertrend, MACD, and Bollinger Bands from live Dhan OHLCV.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from app.agents.base_agent import BaseAgent
from app.api.schemas import AgentResponse, MarketInput
from app.engine.quant_signal_engine import QuantSignalEngine, QuantInputs
from app.data.technical_signals import TechnicalSignals
from app.data.signal_engine import SignalEngine
from app.data.historical_store import historical_store
from app.data.vix_store import vix_store as _vix_store
from app.config import config

logger = logging.getLogger("gods_eye.algo_agent")


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

        # Build QuantInputs from MarketInput + live OHLCV technicals
        # fii_flow_5d / dii_flow_5d are already in INR crores throughout the system.
        fii_net_cr = market_data.fii_flow_5d or 0.0
        dii_net_cr = market_data.dii_flow_5d or 0.0
        vix = market_data.india_vix

        # ── Compute real technicals from Dhan OHLCV ──────────────────────
        # Fetch historical NIFTY closes for RSI, MACD, Bollinger, Supertrend.
        # Falls back to MarketInput values / safe defaults on any error.
        rsi = market_data.rsi_14 if market_data.rsi_14 is not None else 50.0
        supertrend = "bullish"
        macd_histogram = None
        macd_signal_cross = None
        bb_position = None

        try:
            ohlcv_rows = await historical_store.get_ohlcv("NIFTY")
            if ohlcv_rows and len(ohlcv_rows) >= 30:
                closes = [r["close"] for r in ohlcv_rows]

                # RSI-14 (Wilder smoothed)
                rsi = TechnicalSignals.compute_rsi(closes, period=14)
                logger.info("ALGO: live RSI(14) = %.2f from %d OHLCV rows", rsi, len(closes))

                # Supertrend (ATR-10, multiplier 3.0) — real computation
                supertrend = TechnicalSignals.compute_supertrend(ohlcv_rows, period=10, multiplier=3.0)
                logger.info("ALGO: live Supertrend = %s", supertrend)

                # MACD(12,26,9) — needs 26+9=35 bars minimum
                if len(closes) >= 35:
                    macd_result = SignalEngine.compute_macd(closes, fast=12, slow=26, signal=9)
                    macd_histogram = macd_result.get("histogram")
                    interpretation = macd_result.get("interpretation", "")
                    if "bullish_crossover" in interpretation:
                        macd_signal_cross = "bullish_cross"
                    elif "bearish_crossover" in interpretation:
                        macd_signal_cross = "bearish_cross"
                    logger.info("ALGO: live MACD histogram=%.4f, cross=%s", macd_histogram or 0, macd_signal_cross)

                # Bollinger Bands(20,2) — needs 20 bars
                if len(closes) >= 20:
                    bb_result = SignalEngine.compute_bollinger_bands(closes, period=20)
                    bb_position = bb_result.get("position")
                    logger.info("ALGO: live BB position=%.3f", bb_position or 0)
            else:
                logger.warning("ALGO: insufficient OHLCV rows (%d), using defaults", len(ohlcv_rows) if ohlcv_rows else 0)
        except Exception as e:
            logger.warning("ALGO: failed to compute live technicals: %s — using defaults", e)

        # ── Real 5-day VIX average from vix_store ─────────────────────────
        try:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=12)).strftime("%Y-%m-%d")
            vix_rows = _vix_store.get_range(start_date, end_date)
            vix_closes = [r["close"] for r in vix_rows if r.get("close")][-5:]
            if len(vix_closes) >= 3:
                vix_5d_avg = sum(vix_closes) / len(vix_closes)
            else:
                vix_5d_avg = vix * 0.8 + 17.0 * 0.2
        except Exception:
            vix_5d_avg = vix * 0.8 + 17.0 * 0.2

        inputs = QuantInputs(
            fii_net_cr=fii_net_cr,
            dii_net_cr=dii_net_cr,
            pcr=market_data.pcr_index,
            rsi=rsi,
            vix=vix,
            vix_5d_avg=vix_5d_avg,
            supertrend=supertrend,
            macd_histogram=macd_histogram,
            macd_signal_cross=macd_signal_cross,
            bb_position=bb_position,
        )

        result = QuantSignalEngine.compute_quant_score(inputs, instrument="NIFTY")

        # VIX regime filter (Profitability Roadmap v2 — tightened from soft to hard at VIX>=30)
        # Backtest: High VIX trades lose ₹5K-22K avg per trade → hard HOLD saves capital.
        direction = result.direction
        conviction_multiplier = 1.0

        if config.VIX_FILTER_ENABLED:
            vix_regime = TechnicalSignals.classify_vix_regime(vix)

            if vix_regime == "high":
                # Hard filter: VIX >= 30 → force HOLD, zero conviction.
                # Options become too expensive to buy; adverse gaps are unpredictable.
                direction = "HOLD"
                conviction_multiplier = 0.0
            elif vix_regime == "elevated":
                # Soft filter: VIX 20-29.99 → reduce conviction by 40%
                conviction_multiplier = config.VIX_ELEVATED_CONVICTION_MULTIPLIER  # default 0.6

        # Apply conviction multiplier
        adjusted_conviction = float(result.total_score) * conviction_multiplier

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
            f"VIX={vix:.1f}. "
            f"Base direction: {result.direction}."
        )

        # Add VIX regime filter note to reasoning
        if config.VIX_FILTER_ENABLED:
            vix_regime = TechnicalSignals.classify_vix_regime(vix)
            if vix_regime == "high":
                reasoning += (
                    f" [VIX REGIME FILTER: High VIX ({vix:.1f} >= {config.VIX_HIGH_THRESHOLD}) "
                    f"→ direction overridden to HOLD. Base signal was {result.direction}.]"
                )
            elif vix_regime == "elevated":
                reasoning += (
                    f" [VIX REGIME FILTER: Elevated VIX ({vix:.1f}) "
                    f"→ conviction reduced to {conviction_multiplier:.0%} of base.]"
                )

        # Base signals always present
        amplifies = [
            "FII flow alignment",
            "PCR confirmation",
            "Cross-agent consensus signals",
            "Technical confirmation",
        ]
        dampens = [
            "Low conviction when no threshold fires",
            "Noise and whipsaws",
        ]

        # VIX-driven signals (vix already defined above)
        if vix >= 20:
            amplifies.append("Volatility regime signals")
        elif vix < 14:
            amplifies.append("Momentum strategies")
        else:  # 14 <= vix < 20
            amplifies.append("Range-bound mean-reversion signals")

        # RSI-driven signals
        if rsi > 70:
            amplifies.append("Overbought divergence signals")
        elif rsi < 30:
            amplifies.append("Oversold reversal signals")

        # Tier-driven signals
        if result.tier == "strong":
            amplifies.append("Strong quant signal — high consensus weight")
        elif result.tier == "skip":
            dampens.append("Weak quant signal — reduced consensus weight")

        interaction_effects = {
            "amplifies": amplifies,
            "dampens": dampens,
        }

        return AgentResponse(
            agent_name=self.name,
            agent_type=self.agent_type,
            direction=direction,
            conviction=adjusted_conviction,
            reasoning=reasoning,
            key_triggers=key_triggers[:5],
            time_horizon=self.time_horizon,
            views={
                "intraday": {
                    "direction": direction,
                    "conviction": adjusted_conviction,
                    "score": result.total_score,
                    "tier": result.tier,
                    "instrument_hint": result.instrument_hint,
                }
            },
            interaction_effects=interaction_effects,
            internal_consistency=1.0,
            reproducible=True,
        )
