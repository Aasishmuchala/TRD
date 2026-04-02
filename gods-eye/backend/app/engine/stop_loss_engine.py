"""Stop Loss Engine — ATR-based and percentage stop levels for NIFTY options.

For each simulation signal this engine:
  1. Computes ATR(14) from the prior 14+ OHLCV bars (high/low/close)
  2. Computes a stop distance as the TIGHTER of ATR×multiplier or pct×price
  3. Returns a StopLossResult with the exact NIFTY level to place the stop

For the backtest it additionally checks whether next-day's intraday range
(high/low) triggered the stop, and computes the capped P&L if so.

All methods are pure functions (staticmethod) — no state, no DB calls.
Pattern copied from app/engine/quant_signal_engine.py (same dataclass + staticmethod style).
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants — override via Config (GODS_EYE_STOP_LOSS_* env vars)
# ---------------------------------------------------------------------------

ATR_PERIOD: int = 14
DEFAULT_ATR_MULTIPLIER: float = 1.5   # 1.5 × ATR(14) = stop distance in NIFTY points
DEFAULT_PCT_STOP: float = 1.5          # 1.5% adverse move in underlying triggers stop
_OPTION_LEVERAGE: float = 3.0          # Must match backtest_engine._OPTION_LEVERAGE


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class StopLossResult:
    """Stop level computed for one signal day."""

    direction: str              # "BUY" / "SELL" / "HOLD" — the signal direction
    entry_price: float          # NIFTY close on signal day (entry proxy)
    stop_price: float           # NIFTY level that triggers stop exit
    stop_distance_pts: float    # abs(entry_price - stop_price) in index points
    stop_pct: float             # stop_distance_pts / entry_price * 100
    atr_14: float               # ATR(14) value used; 0.0 if insufficient data
    method: str                 # "atr" | "pct" | "none" (HOLD or no data)


# Sentinel for HOLD / no-stop cases
_NO_STOP = StopLossResult(
    direction="HOLD",
    entry_price=0.0,
    stop_price=0.0,
    stop_distance_pts=0.0,
    stop_pct=0.0,
    atr_14=0.0,
    method="none",
)


# ---------------------------------------------------------------------------
# Engine (pure static methods — no instantiation needed)
# ---------------------------------------------------------------------------

class StopLossEngine:
    """Computes stop loss levels and evaluates stop hits for backtest replay.

    All methods are stateless. No DB calls. No side effects.

    Usage (backtest):
        ohlcv_window = all_ohlcv[max(0, i-20):i]     # prior 20 rows, no leakage
        result = StopLossEngine.compute_stop_for_day(
            direction=predicted_direction,
            entry_close=nifty_close,
            ohlcv_window=ohlcv_window,
        )
        if result.method != "none":
            hit = StopLossEngine.check_stop_hit(result.direction, result.stop_price,
                                                next_row["low"], next_row["high"])
            if hit:
                pnl = StopLossEngine.compute_stopped_pnl(result.direction,
                                                          result.entry_price,
                                                          result.stop_price)

    Usage (live simulation):
        result = StopLossEngine.compute_stop_for_day(
            direction=aggregator_direction,
            entry_close=nifty_spot,
            ohlcv_window=recent_ohlcv_rows,  # last 20 rows from historical_store
            atr_multiplier=config.STOP_LOSS_ATR_MULTIPLIER,
            pct_stop=config.STOP_LOSS_PCT,
        )
        # result.stop_price → show in UI "Place stop at 22,847"
    """

    # ------------------------------------------------------------------ #
    # ATR computation                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_atr(ohlcv_rows: List[Dict], period: int = ATR_PERIOD) -> float:
        """Compute ATR(period) from a list of OHLCV dicts.

        Input:  List[Dict] with keys 'high', 'low', 'close' (from historical_store.get_ohlcv)
                Must be sorted ascending by date. Needs at least period+1 rows.
        Returns: float ATR value; 0.0 if insufficient data.

        True Range = max(high-low, |high - prev_close|, |low - prev_close|)
        ATR = simple moving average of last `period` True Range values.
        """
        if len(ohlcv_rows) < period + 1:
            return 0.0

        true_ranges: List[float] = []
        for i in range(1, len(ohlcv_rows)):
            h = float(ohlcv_rows[i]["high"])
            lo = float(ohlcv_rows[i]["low"])
            prev_c = float(ohlcv_rows[i - 1]["close"])
            tr = max(h - lo, abs(h - prev_c), abs(lo - prev_c))
            true_ranges.append(tr)

        if len(true_ranges) < period:
            return 0.0

        return sum(true_ranges[-period:]) / period

    # ------------------------------------------------------------------ #
    # Stop level computation                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_stop(
        direction: str,
        entry_close: float,
        atr_14: float,
        atr_multiplier: float = DEFAULT_ATR_MULTIPLIER,
        pct_stop: float = DEFAULT_PCT_STOP,
    ) -> StopLossResult:
        """Compute stop loss level given pre-computed ATR.

        Takes the TIGHTER of ATR-based and percentage-based stops:
          - ATR-based distance = atr_14 × atr_multiplier (index points)
          - PCT-based distance = entry_close × pct_stop / 100

        Tighter = smaller distance from entry = less room to move against us.

        For BUY: stop is BELOW entry (NIFTY must fall to trigger).
        For SELL: stop is ABOVE entry (NIFTY must rise to trigger).
        For HOLD: returns _NO_STOP sentinel (no stop applicable).
        """
        if direction not in ("BUY", "STRONG_BUY", "SELL", "STRONG_SELL"):
            return _NO_STOP

        if entry_close <= 0:
            return _NO_STOP

        pct_distance = entry_close * (pct_stop / 100.0)

        if atr_14 > 0:
            atr_distance = atr_14 * atr_multiplier
            # Take the tighter (smaller) distance
            distance = min(atr_distance, pct_distance)
            method = "atr" if atr_distance <= pct_distance else "pct"
        else:
            # No ATR data — fall back to percentage only
            distance = pct_distance
            method = "pct"

        if direction in ("BUY", "STRONG_BUY"):
            stop_price = entry_close - distance
        else:  # SELL / STRONG_SELL
            stop_price = entry_close + distance

        return StopLossResult(
            direction=direction,
            entry_price=round(entry_close, 2),
            stop_price=round(stop_price, 2),
            stop_distance_pts=round(distance, 2),
            stop_pct=round((distance / entry_close) * 100, 3),
            atr_14=round(atr_14, 2),
            method=method,
        )

    @staticmethod
    def compute_stop_for_day(
        direction: str,
        entry_close: float,
        ohlcv_window: List[Dict],
        atr_multiplier: float = DEFAULT_ATR_MULTIPLIER,
        pct_stop: float = DEFAULT_PCT_STOP,
    ) -> StopLossResult:
        """Convenience wrapper: compute ATR then stop level.

        ohlcv_window: last N rows BEFORE the signal day (no current-day leakage).
                      Needs at least ATR_PERIOD+1 (15) rows for ATR; fewer falls
                      back to pct-only stop.
        """
        atr = StopLossEngine.compute_atr(ohlcv_window, period=ATR_PERIOD)
        return StopLossEngine.compute_stop(
            direction=direction,
            entry_close=entry_close,
            atr_14=atr,
            atr_multiplier=atr_multiplier,
            pct_stop=pct_stop,
        )

    # ------------------------------------------------------------------ #
    # Stop hit check (backtest use only)                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def check_stop_hit(
        direction: str,
        stop_price: float,
        day_low: float,
        day_high: float,
    ) -> bool:
        """Check whether the stop was triggered during the next day's intraday range.

        For BUY:  stop hit if day_low  <= stop_price (NIFTY fell through stop)
        For SELL: stop hit if day_high >= stop_price (NIFTY rose through stop)
        HOLD: never hit (stop_price is 0).
        """
        if direction in ("BUY", "STRONG_BUY"):
            return day_low <= stop_price
        if direction in ("SELL", "STRONG_SELL"):
            return day_high >= stop_price
        return False

    # ------------------------------------------------------------------ #
    # Capped P&L when stop is hit                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_stopped_pnl(
        direction: str,
        entry_price: float,
        stop_price: float,
        option_leverage: float = _OPTION_LEVERAGE,
    ) -> float:
        """P&L when the stop is triggered.

        Uses the same leverage model as backtest_engine._compute_pnl().
        For a BUY trade that stops out:
            move_pct = (stop_price - entry_price) / entry_price * 100  (negative)
            pnl = move_pct * leverage * (entry_price / 100)
        For a SELL trade that stops out:
            move_pct is inverted (rising price hurts short)

        Always returns a negative number (a loss) when stop is hit.
        Returns 0.0 for HOLD.
        """
        if direction not in ("BUY", "STRONG_BUY", "SELL", "STRONG_SELL"):
            return 0.0
        if entry_price <= 0:
            return 0.0

        raw_move_pct = (stop_price - entry_price) / entry_price * 100

        if direction in ("BUY", "STRONG_BUY"):
            # Negative: stop is below entry
            move_pct = raw_move_pct
        else:
            # SELL: rising price (positive raw_move_pct) is a loss
            move_pct = -raw_move_pct

        return move_pct * option_leverage * (entry_price / 100)
