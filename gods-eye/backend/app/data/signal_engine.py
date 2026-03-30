"""Signal engine for pre-computing market indicators."""

import numpy as np
from typing import Dict, List, Optional
from app.api.schemas import MarketInput


class SignalEngine:
    """Pre-computes technical and flow indicators from raw market data."""

    @staticmethod
    def compute_rsi(prices: List[float], period: int = 14) -> float:
        """Compute RSI(14) from price series."""
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
        return float(np.clip(rsi, 0, 100))

    @staticmethod
    def compute_macd(
        prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Dict[str, float]:
        """Compute MACD line, signal line, and histogram.

        Returns dict with macd_line, signal_line, histogram, and interpretation.
        """
        if len(prices) < slow + signal:
            return {"macd_line": 0.0, "signal_line": 0.0, "histogram": 0.0, "interpretation": "insufficient_data"}

        prices_array = np.array(prices, dtype=float)

        # EMA computation helper
        def ema(data, period):
            multiplier = 2.0 / (period + 1)
            result = np.zeros_like(data)
            result[0] = data[0]
            for i in range(1, len(data)):
                result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
            return result

        fast_ema = ema(prices_array, fast)
        slow_ema = ema(prices_array, slow)
        macd_line = fast_ema - slow_ema
        signal_line = ema(macd_line, signal)
        histogram = macd_line - signal_line

        current_macd = float(macd_line[-1])
        current_signal = float(signal_line[-1])
        current_hist = float(histogram[-1])

        # Interpretation
        if current_macd > current_signal and current_hist > 0:
            if len(histogram) >= 2 and histogram[-2] <= 0:
                interpretation = "bullish_crossover"
            else:
                interpretation = "bullish"
        elif current_macd < current_signal and current_hist < 0:
            if len(histogram) >= 2 and histogram[-2] >= 0:
                interpretation = "bearish_crossover"
            else:
                interpretation = "bearish"
        else:
            interpretation = "neutral"

        return {
            "macd_line": round(current_macd, 4),
            "signal_line": round(current_signal, 4),
            "histogram": round(current_hist, 4),
            "interpretation": interpretation,
        }

    @staticmethod
    def compute_bollinger_bands(
        prices: List[float], period: int = 20
    ) -> Dict[str, float]:
        """Compute Bollinger Band values."""
        if len(prices) < period:
            return {
                "sma": prices[-1] if prices else 100,
                "upper": prices[-1] * 1.02 if prices else 102,
                "lower": prices[-1] * 0.98 if prices else 98,
                "position": 0.5,
            }

        prices_array = np.array(prices[-period:])
        sma = np.mean(prices_array)
        std = np.std(prices_array)

        upper = sma + 2 * std
        lower = sma - 2 * std

        current = prices[-1]
        position = (current - lower) / (upper - lower) if (upper - lower) != 0 else 0.5
        position = np.clip(position, 0, 1)

        return {
            "sma": float(sma),
            "upper": float(upper),
            "lower": float(lower),
            "position": float(position),
        }

    @staticmethod
    def compute_z_score(values: List[float]) -> float:
        """Compute Z-score of latest value."""
        if len(values) < 2:
            return 0.0

        mean = np.mean(values)
        std = np.std(values)
        if std == 0:
            return 0.0

        z_score = (values[-1] - mean) / std
        return float(z_score)

    @staticmethod
    def compute_percentile(values: List[float], lookback: int = 252) -> float:
        """Compute percentile rank of latest value (0-100)."""
        if len(values) < 2:
            return 50.0

        recent = values[-lookback:] if len(values) >= lookback else values
        percentile = (
            np.sum(np.array(recent) <= recent[-1]) / len(recent) * 100
        )
        return float(np.clip(percentile, 0, 100))

    @staticmethod
    def classify_vix_regime(india_vix: float) -> str:
        """Classify VIX into regime."""
        if india_vix < 14:
            return "low_fear"
        elif india_vix < 20:
            return "normal"
        elif india_vix < 30:
            return "elevated"
        else:
            return "high_fear"

    @staticmethod
    def classify_pcr_regime(pcr: float) -> str:
        """Classify Put-Call Ratio into regime."""
        if pcr > 1.5:
            return "extremely_bullish"
        elif pcr > 1.2:
            return "bullish"
        elif pcr > 0.9:
            return "neutral"
        elif pcr > 0.7:
            return "bearish"
        else:
            return "extremely_bearish"

    @staticmethod
    def process_market_input(market_data: MarketInput) -> Dict[str, any]:
        """Pre-process all signals from market input.

        Returns a rich signal dict used by ProfileGenerator to build
        agent-specific context packages.
        """
        signals = {}

        # RSI
        if market_data.historical_prices:
            rsi = SignalEngine.compute_rsi(market_data.historical_prices, 14)
        else:
            rsi = market_data.rsi_14 or 50.0
        signals["rsi"] = rsi
        signals["rsi_interpretation"] = (
            "severely overbought — historically 68% chance of pullback within 5 sessions" if rsi > 75 else
            "overbought — mean reversion likely" if rsi > 70 else
            "mildly overbought" if rsi > 60 else
            "neutral" if rsi > 40 else
            "mildly oversold" if rsi > 30 else
            "oversold — bounce likely" if rsi > 25 else
            "severely oversold — strong bounce probability"
        )

        # MACD
        if market_data.historical_prices and len(market_data.historical_prices) >= 35:
            signals["macd"] = SignalEngine.compute_macd(market_data.historical_prices)
        else:
            signals["macd"] = {"macd_line": market_data.macd_signal or 0.0, "interpretation": "from_input"}

        # Bollinger Bands
        if market_data.historical_prices:
            bb = SignalEngine.compute_bollinger_bands(market_data.historical_prices, 20)
        else:
            bb = {"position": 0.5, "sma": market_data.nifty_spot, "upper": market_data.nifty_spot * 1.02, "lower": market_data.nifty_spot * 0.98}

        bb_pos = bb.get("position", 0.5)
        bb["level"] = (
            "above_upper" if bb_pos > 1.0 else
            "upper_quarter" if bb_pos > 0.75 else
            "middle_upper" if bb_pos > 0.5 else
            "middle_lower" if bb_pos > 0.25 else
            "lower_quarter" if bb_pos > 0.0 else
            "below_lower"
        )
        signals["bollinger_bands"] = bb

        # VIX Regime
        signals["vix_regime"] = SignalEngine.classify_vix_regime(market_data.india_vix)

        # PCR Regime
        signals["pcr_regime"] = SignalEngine.classify_pcr_regime(market_data.pcr_index)

        # Pass-through raw values (used by ProfileGenerator)
        signals["fii_flow_5d"] = market_data.fii_flow_5d
        signals["dii_flow_5d"] = market_data.dii_flow_5d
        signals["usd_inr"] = market_data.usd_inr
        signals["dxy"] = market_data.dxy
        signals["dte"] = market_data.dte
        signals["max_pain"] = market_data.max_pain

        # Max Pain Distance
        if market_data.max_pain and market_data.nifty_spot:
            pain_dist = (market_data.nifty_spot - market_data.max_pain) / market_data.max_pain * 100
            signals["max_pain_distance_pct"] = round(pain_dist, 2)
            signals["max_pain_interpretation"] = (
                "price far above max pain — call writers under pressure, downward pull likely"
                if pain_dist > 1.5 else
                "price above max pain — mild downward gravitational pull"
                if pain_dist > 0.3 else
                "price near max pain — neutral zone, low directional pull"
                if abs(pain_dist) <= 0.3 else
                "price below max pain — mild upward gravitational pull"
                if pain_dist > -1.5 else
                "price far below max pain — put writers under pressure, upward pull likely"
            )

        # FII Flow Momentum
        if market_data.fii_flow_5d:
            fii_daily_avg = market_data.fii_flow_5d / 5
            signals["fii_daily_avg"] = round(fii_daily_avg, 1)
            signals["fii_flow_regime"] = (
                "heavy_buying" if fii_daily_avg > 1000 else
                "moderate_buying" if fii_daily_avg > 300 else
                "light_buying" if fii_daily_avg > 0 else
                "light_selling" if fii_daily_avg > -300 else
                "moderate_selling" if fii_daily_avg > -1000 else
                "heavy_selling"
            )

        # DII Flow Momentum
        if market_data.dii_flow_5d:
            dii_daily_avg = market_data.dii_flow_5d / 5
            signals["dii_daily_avg"] = round(dii_daily_avg, 1)
            signals["dii_flow_regime"] = (
                "heavy_buying" if dii_daily_avg > 800 else
                "moderate_buying" if dii_daily_avg > 200 else
                "light_buying" if dii_daily_avg > 0 else
                "light_selling" if dii_daily_avg > -200 else
                "moderate_selling" if dii_daily_avg > -800 else
                "heavy_selling"
            )

        # DXY Impact on EM
        if market_data.dxy:
            signals["dxy_regime"] = (
                "strong_dollar_headwind" if market_data.dxy > 107 else
                "moderate_dollar" if market_data.dxy > 103 else
                "neutral_dollar" if market_data.dxy > 99 else
                "weak_dollar_tailwind"
            )

        # Expiry Proximity Impact
        if market_data.dte is not None:
            signals["expiry_proximity"] = (
                "expiry_day" if market_data.dte == 0 else
                "expiry_eve" if market_data.dte == 1 else
                "near_expiry" if market_data.dte <= 3 else
                "mid_series" if market_data.dte <= 10 else
                "far_from_expiry"
            )

        return signals
