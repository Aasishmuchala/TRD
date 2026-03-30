"""Pure quantitative algorithm agent - no LLM calls."""

import numpy as np
from typing import Dict, Optional, List
from app.agents.base_agent import BaseAgent
from app.api.schemas import AgentResponse, MarketInput


class AlgoQuantAgent(BaseAgent):
    """Quantitative algorithm agent using technical analysis."""

    def __init__(self):
        super().__init__(
            name="Algo Trading Engine",
            persona="Pure quantitative algorithm analyzing technical signals",
            decision_framework="Multi-signal consensus with weightings",
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
        """Analyze using pure technical indicators."""

        signals = {}

        # RSI calculation
        if market_data.rsi_14 is not None:
            signals["rsi_14"] = market_data.rsi_14
        elif market_data.historical_prices:
            signals["rsi_14"] = self._compute_rsi(
                market_data.historical_prices, period=14
            )
        else:
            signals["rsi_14"] = 50.0

        # VIX regime
        if market_data.india_vix < 14:
            signals["vix_regime"] = "low_fear"
            vix_signal = 0.2
        elif market_data.india_vix < 20:
            signals["vix_regime"] = "elevated"
            vix_signal = 0.0
        else:
            signals["vix_regime"] = "high_fear"
            vix_signal = -0.3

        # PCR analysis
        pcr_strength = self._analyze_pcr(market_data.pcr_index)
        signals["pcr"] = market_data.pcr_index
        signals["pcr_interpretation"] = pcr_strength["interpretation"]

        # MACD equivalent
        if market_data.macd_signal is not None:
            signals["macd_signal"] = market_data.macd_signal
        else:
            signals["macd_signal"] = 0.0

        # Bollinger Band position
        bb_position = self._compute_bb_position(market_data)
        signals["bb_position"] = bb_position

        # Compute composite score (0-100)
        rsi_score = self._rsi_to_signal(signals["rsi_14"])
        pcr_score = pcr_strength["signal_strength"]
        bb_score = bb_position["signal"]

        # Weighted combination
        composite = (rsi_score * 0.35) + (pcr_score * 0.35) + (bb_score * 0.30)
        composite = composite + vix_signal

        # Clamp between -1 and 1
        composite = np.clip(composite, -1, 1)

        # Convert to direction
        direction, conviction = self._composite_to_direction(composite)

        # Build key triggers
        key_triggers = []
        if signals["rsi_14"] > 70:
            key_triggers.append(f"RSI({signals['rsi_14']:.1f}) overbought")
        elif signals["rsi_14"] < 30:
            key_triggers.append(f"RSI({signals['rsi_14']:.1f}) oversold")

        key_triggers.append(f"PCR {signals['pcr_interpretation']}")
        key_triggers.append(f"VIX regime: {signals['vix_regime']}")
        key_triggers.append(f"Bollinger Band: {bb_position['level']}")

        reasoning = self._build_reasoning(signals, composite, direction)

        return AgentResponse(
            agent_name=self.name,
            agent_type=self.agent_type,
            direction=direction,
            conviction=conviction,
            reasoning=reasoning,
            key_triggers=key_triggers,
            time_horizon=self.time_horizon,
            views={
                "intraday": {
                    "direction": direction,
                    "conviction": conviction,
                    "rsi": signals["rsi_14"],
                    "vix_regime": signals["vix_regime"],
                }
            },
            interaction_effects={"amplifies": [], "dampens": []},
            internal_consistency=1.0,
            reproducible=True,
        )

    def _compute_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate Relative Strength Index."""
        if len(prices) < period + 1:
            return 50.0

        deltas = np.diff(prices[-period - 1 :])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)

    def _rsi_to_signal(self, rsi: float) -> float:
        """Convert RSI to signal strength (-1 to 1)."""
        if rsi > 70:
            return -0.7  # Overbought
        elif rsi > 60:
            return -0.3
        elif rsi > 50:
            return 0.0
        elif rsi > 40:
            return 0.0
        elif rsi < 30:
            return 0.7  # Oversold
        elif rsi < 40:
            return 0.3
        else:
            return 0.0

    def _analyze_pcr(self, pcr: float) -> Dict[str, any]:
        """Analyze Put-Call Ratio."""
        if pcr > 1.5:
            return {
                "interpretation": "Extremely bullish (excessive puts)",
                "signal_strength": 0.6,
            }
        elif pcr > 1.2:
            return {
                "interpretation": "Bullish (elevated puts)",
                "signal_strength": 0.3,
            }
        elif pcr > 0.9:
            return {
                "interpretation": "Neutral (balanced)",
                "signal_strength": 0.0,
            }
        elif pcr > 0.7:
            return {
                "interpretation": "Bearish (elevated calls)",
                "signal_strength": -0.3,
            }
        else:
            return {
                "interpretation": "Extremely bearish (excessive calls)",
                "signal_strength": -0.6,
            }

    def _compute_bb_position(self, market_data: MarketInput) -> Dict[str, any]:
        """Compute Bollinger Band position."""
        if not market_data.historical_prices or len(market_data.historical_prices) < 20:
            return {"position": 0.5, "level": "middle", "signal": 0.0}

        prices = market_data.historical_prices[-20:]
        sma = np.mean(prices)
        std = np.std(prices)

        current = market_data.nifty_spot
        upper = sma + 2 * std
        lower = sma - 2 * std

        if current > upper:
            position = 1.0
            level = "above_upper"
            signal = -0.4
        elif current > sma + std:
            position = 0.75
            level = "upper_half"
            signal = -0.2
        elif current > sma:
            position = 0.5
            level = "middle_upper"
            signal = 0.1
        elif current > sma - std:
            position = 0.25
            level = "middle_lower"
            signal = -0.1
        elif current > lower:
            position = 0.0
            level = "lower_half"
            signal = 0.2
        else:
            position = -1.0
            level = "below_lower"
            signal = 0.4

        return {"position": position, "level": level, "signal": signal}

    def _composite_to_direction(self, composite: float) -> tuple:
        """Convert composite score to direction and conviction."""
        if composite > 0.6:
            return "STRONG_BUY", min(85, 50 + abs(composite) * 50)
        elif composite > 0.3:
            return "BUY", min(65, 40 + abs(composite) * 50)
        elif composite > -0.3:
            return "HOLD", max(20, 30 - abs(composite) * 50)
        elif composite > -0.6:
            return "SELL", min(65, 40 + abs(composite) * 50)
        else:
            return "STRONG_SELL", min(85, 50 + abs(composite) * 50)

    def _build_reasoning(
        self, signals: Dict, composite: float, direction: str
    ) -> str:
        """Build reasoning for the decision."""
        parts = []

        rsi = signals["rsi_14"]
        if rsi > 70:
            parts.append(f"RSI at {rsi:.1f} indicates overbought conditions.")
        elif rsi < 30:
            parts.append(f"RSI at {rsi:.1f} indicates oversold conditions.")
        else:
            parts.append(f"RSI at {rsi:.1f} is neutral.")

        pcr = signals["pcr"]
        parts.append(f"PCR at {pcr:.2f} suggests {signals['pcr_interpretation']}.")

        vix = signals["vix_regime"]
        parts.append(f"VIX regime is {vix}.")

        bb = signals["bb_position"]
        parts.append(f"Price is {bb['level']} Bollinger Bands.")

        parts.append(
            f"Composite technical signal: {composite:.2f}. Direction: {direction}."
        )

        return " ".join(parts)
