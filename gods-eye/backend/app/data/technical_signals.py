"""Technical signal computations for historical OHLCV data.

All methods accept List[Dict] rows from HistoricalStore.get_ohlcv() -- dicts
with keys: date, open, high, low, close, volume (sorted date ASC).

No async, no I/O. Pure numpy arithmetic for use by backtest engine (Phase 7)
and the signals API endpoint (Plan 02).
"""

import numpy as np
from typing import Dict, List, Optional


class TechnicalSignals:

    # RSI-14 (Wilder Smoothed EMA)
    #
    # Formula:
    #   deltas = diff(closes)
    #   seed_avg_gain = mean(gains[:14])     <- simple average seed
    #   seed_avg_loss = mean(losses[:14])
    #   For i > 14:
    #     avg_gain = (prev_avg_gain * 13 + gain_i) / 14   <- Wilder smoothing
    #     avg_loss = (prev_avg_loss * 13 + loss_i) / 14
    #   RS = avg_gain / avg_loss
    #   RSI = 100 - 100 / (1 + RS)

    @staticmethod
    def compute_rsi(closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0

        arr = np.array(closes, dtype=float)
        deltas = np.diff(arr)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = float(np.mean(gains[:period]))
        avg_loss = float(np.mean(losses[:period]))

        for g, l in zip(gains[period:], losses[period:]):
            avg_gain = (avg_gain * (period - 1) + g) / period
            avg_loss = (avg_loss * (period - 1) + l) / period

        if avg_loss == 0.0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return float(np.clip(rsi, 0.0, 100.0))

    # VWAP Deviation (percentage from rolling VWAP)
    #
    # VWAP = sum(close_i * volume_i) / sum(volume_i)
    # Deviation = (close_last - VWAP) / VWAP * 100
    # Uses all supplied rows as the rolling window.

    @staticmethod
    def compute_vwap_deviation(rows: List[Dict]) -> float:
        if not rows:
            return 0.0

        closes = np.array([r["close"] for r in rows], dtype=float)
        volumes = np.array([r["volume"] for r in rows], dtype=float)

        total_vol = float(np.sum(volumes))
        if total_vol == 0.0:
            vwap = float(np.mean(closes))
        else:
            vwap = float(np.sum(closes * volumes) / total_vol)

        if vwap == 0.0:
            return 0.0

        last_close = float(rows[-1]["close"])
        return round((last_close - vwap) / vwap * 100, 4)

    # Supertrend (ATR-10, multiplier 3.0)
    #
    # Algorithm:
    #   1. TR = max(high-low, |high-prev_close|, |low-prev_close|)
    #   2. ATR(10) via Wilder EMA: atr[i] = (atr[i-1] * 9 + tr[i]) / 10
    #   3. basic_upper = (high+low)/2 + 3.0 * ATR
    #      basic_lower = (high+low)/2 - 3.0 * ATR
    #   4. final_upper[i] = min(basic_upper[i], final_upper[i-1])  unless prev close broke above
    #      final_lower[i] = max(basic_lower[i], final_lower[i-1])  unless prev close broke below
    #   5. direction starts "bullish"; flips "bearish" when close <= final_upper;
    #      flips back "bullish" when close > final_lower

    @staticmethod
    def compute_supertrend(rows: List[Dict], period: int = 10, multiplier: float = 3.0) -> str:
        if len(rows) < period + 1:
            return "bullish"

        highs = np.array([r["high"] for r in rows], dtype=float)
        lows = np.array([r["low"] for r in rows], dtype=float)
        closes = np.array([r["close"] for r in rows], dtype=float)
        n = len(rows)

        tr = np.zeros(n)
        tr[0] = highs[0] - lows[0]
        for i in range(1, n):
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )

        atr = np.zeros(n)
        atr[period - 1] = float(np.mean(tr[:period]))
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

        hl2 = (highs + lows) / 2.0
        basic_upper = hl2 + multiplier * atr
        basic_lower = hl2 - multiplier * atr

        final_upper = np.zeros(n)
        final_lower = np.zeros(n)
        final_upper[period - 1] = basic_upper[period - 1]
        final_lower[period - 1] = basic_lower[period - 1]
        direction = "bullish"

        for i in range(period, n):
            if closes[i - 1] > final_upper[i - 1]:
                final_upper[i] = basic_upper[i]
            else:
                final_upper[i] = min(basic_upper[i], final_upper[i - 1])

            if closes[i - 1] < final_lower[i - 1]:
                final_lower[i] = basic_lower[i]
            else:
                final_lower[i] = max(basic_lower[i], final_lower[i - 1])

            if direction == "bullish" and closes[i] <= final_upper[i]:
                direction = "bearish"
            elif direction == "bearish" and closes[i] > final_lower[i]:
                direction = "bullish"

        return direction

    # VIX Regime Classification
    #
    # Thresholds per ROADMAP Phase 6 TECH-05:
    #   below 14      -> "low"
    #   14 to 19.99   -> "normal"
    #   20 to 29.99   -> "elevated"
    #   30+           -> "high"
    #
    # NOTE: signal_engine.py uses "low_fear"/"high_fear" labels for live simulation.
    # These labels ("low"/"normal"/"elevated"/"high") are for historical/backtest use only.
    # Do not merge these two classification schemes.

    @staticmethod
    def classify_vix_regime(india_vix: float) -> str:
        if india_vix < 0:
            raise ValueError(f"VIX cannot be negative: {india_vix}")
        if india_vix < 14:
            return "low"
        elif india_vix < 20:
            return "normal"
        elif india_vix < 30:
            return "elevated"
        else:
            return "high"

    # Convenience: compute all OHLCV-based signals for a specific target date.
    # Slices rows to up-to and including date_str to prevent future data leakage.

    @staticmethod
    def compute_signals_for_date(rows: List[Dict], date_str: str) -> Dict:
        window = [r for r in rows if r["date"] <= date_str]
        if not window:
            return {"error": f"No rows at or before {date_str}"}

        closes = [r["close"] for r in window]
        # VWAP uses a 20-day rolling window only — using the full multi-year history
        # produces a permanently-inflated deviation (NIFTY trending up means current
        # price is always ~10-12% above the long-run average, making the signal useless).
        vwap_window = window[-20:] if len(window) >= 20 else window
        return {
            "rsi": TechnicalSignals.compute_rsi(closes),
            "vwap_deviation_pct": TechnicalSignals.compute_vwap_deviation(vwap_window),
            "supertrend": TechnicalSignals.compute_supertrend(window),
        }


# Global singleton -- mirrors dhan_client / historical_store pattern
technical_signals = TechnicalSignals()
