"""QuantSignalEngine — pure rules-based quantitative signal scoring engine.

Maps market inputs to a 0-100 directional score with per-factor breakdown.
Zero LLM calls. No I/O. No app.* imports. Only stdlib + dataclasses + typing.

Scoring rules:

BUY side (max 90 pts):
  fii_flow:        fii_net_cr >  +1000 Cr → +25
  dii_absorption:  dii_net_cr > 0 AND fii_net_cr < 0 → +10
  pcr:             pcr > 1.2 (put-heavy = contrarian bullish) → +15
  rsi:             rsi < 30 (oversold) → +20
  vix:             vix < 14 AND vix < vix_5d_avg (calm + falling) → +10
  supertrend:      supertrend == "bullish" → +10

SELL side (max 80 pts):
  fii_flow:        fii_net_cr < -1000 Cr → +25
  pcr:             pcr < 0.7 (call-heavy = contrarian bearish) → +15
  rsi:             rsi > 70 (overbought) → +20
  vix:             vix > 20 AND vix > vix_5d_avg (fear + rising) → +10
  supertrend:      supertrend == "bearish" → +10

Direction: BUY  if buy_points  > sell_points AND buy_points  > 50
           SELL if sell_points > buy_points  AND sell_points > 50
           HOLD otherwise

total_score = max(buy_points, sell_points) clamped [0, 100]

Tier: total_score > 70  → "strong"
      total_score >= 50 → "moderate"
      total_score < 50  → "skip"

Instrument hint:
  BUY  + NIFTY     → "NIFTY_CE"
  BUY  + BANKNIFTY → "BANKNIFTY_CE"
  SELL + NIFTY     → "NIFTY_PE"
  SELL + BANKNIFTY → "BANKNIFTY_PE"
  HOLD             → "NONE"
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


# ---------------------------------------------------------------------------
# Input dataclass
# ---------------------------------------------------------------------------


@dataclass
class QuantInputs:
    """All fields required for quantitative scoring.

    Plan 02 builds this from historical OHLCV + FII/DII flow data.
    """

    fii_net_cr: float       # FII net flow in crores (positive = buying)
    dii_net_cr: float       # DII net flow in crores (positive = buying)
    pcr: float              # Put/Call ratio (>1.2 bearish sentiment = contrarian bullish)
    rsi: float              # RSI-14 value (0-100)
    vix: float              # Current India VIX level
    vix_5d_avg: float       # 5-day average VIX for direction detection
    supertrend: str         # "bullish" or "bearish"

    # Phase 4 additions
    macd_histogram: Optional[float] = None    # MACD(12,26,9) histogram value
    macd_signal_cross: Optional[str] = None   # "bullish_cross" | "bearish_cross" | None
    bb_position: Optional[float] = None       # Price position relative to Bollinger Bands(20,2)
                                               # <0 = below lower band, >1 = above upper band, 0.5 = at middle


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class QuantScoreResult:
    """Result of QuantSignalEngine.compute_quant_score() — pure value object."""

    total_score: int                          # 0-100 clamped
    direction: str                            # "BUY" | "SELL" | "HOLD"
    buy_points: int                           # Raw buy points accumulated
    sell_points: int                          # Raw sell points accumulated
    factors: Dict[str, Dict] = field(default_factory=dict)
    # Per-factor breakdown: {name: {points, threshold_hit, side}}
    tier: str = "skip"                        # "strong" (>70) | "moderate" (>=50) | "skip" (<50)
    instrument_hint: str = "NONE"             # "NIFTY_CE" | "NIFTY_PE" | "BANKNIFTY_CE" | "BANKNIFTY_PE" | "NONE"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class QuantSignalEngine:
    """Deterministic rules engine mapping market inputs to a 0-100 directional score."""

    # Epsilon for float comparisons (avoids floating-point edge cases near zero)
    _EPSILON = 1e-6

    @staticmethod
    def compute_quant_score(
        inputs: QuantInputs,
        instrument: str = "NIFTY",
    ) -> QuantScoreResult:
        """Compute quantitative signal score from market inputs.

        Pure function. No I/O. No side effects.

        Parameters
        ----------
        inputs:
            QuantInputs with all 7 required fields.
        instrument:
            "NIFTY" (default) or "BANKNIFTY". Determines instrument_hint.

        Returns
        -------
        QuantScoreResult with total_score, direction, buy_points, sell_points,
        factors breakdown, tier, and instrument_hint.
        """
        buy_points: int = 0
        sell_points: int = 0
        factors: Dict[str, Dict] = {}

        instrument_upper = (instrument or "NIFTY").upper().strip()

        # ------------------------------------------------------------------
        # FII flow (bidirectional — single "fii_flow" factor key)
        # ------------------------------------------------------------------
        if inputs.fii_net_cr > 1000:
            pts = 25
            buy_points += pts
            factors["fii_flow"] = {"points": pts, "threshold_hit": True, "side": "buy"}
        elif inputs.fii_net_cr < -1000:
            pts = 25
            sell_points += pts
            factors["fii_flow"] = {"points": pts, "threshold_hit": True, "side": "sell"}
        else:
            # Neither threshold triggered
            factors["fii_flow"] = {"points": 0, "threshold_hit": False, "side": "buy"}

        # ------------------------------------------------------------------
        # DII absorption (buy-only rule)
        # ------------------------------------------------------------------
        if inputs.dii_net_cr > 0 and inputs.fii_net_cr < 0:
            pts = 10
            buy_points += pts
            factors["dii_absorption"] = {"points": pts, "threshold_hit": True, "side": "buy"}
        else:
            factors["dii_absorption"] = {"points": 0, "threshold_hit": False, "side": "buy"}

        # ------------------------------------------------------------------
        # PCR (bidirectional — single "pcr" factor key)
        # ------------------------------------------------------------------
        if inputs.pcr > 1.2:
            pts = 15
            buy_points += pts
            factors["pcr"] = {"points": pts, "threshold_hit": True, "side": "buy"}
        elif inputs.pcr < 0.7:
            pts = 15
            sell_points += pts
            factors["pcr"] = {"points": pts, "threshold_hit": True, "side": "sell"}
        else:
            factors["pcr"] = {"points": 0, "threshold_hit": False, "side": "buy"}

        # ------------------------------------------------------------------
        # RSI (bidirectional — single "rsi" factor key)
        # ------------------------------------------------------------------
        if inputs.rsi < 30:
            pts = 20
            buy_points += pts
            factors["rsi"] = {"points": pts, "threshold_hit": True, "side": "buy"}
        elif inputs.rsi > 70:
            pts = 20
            sell_points += pts
            factors["rsi"] = {"points": pts, "threshold_hit": True, "side": "sell"}
        else:
            factors["rsi"] = {"points": 0, "threshold_hit": False, "side": "buy"}

        # ------------------------------------------------------------------
        # VIX (bidirectional — single "vix" factor key)
        # ------------------------------------------------------------------
        if inputs.vix < 14 and inputs.vix < inputs.vix_5d_avg:
            pts = 10
            buy_points += pts
            factors["vix"] = {"points": pts, "threshold_hit": True, "side": "buy"}
        elif inputs.vix > 20 and inputs.vix > inputs.vix_5d_avg:
            pts = 10
            sell_points += pts
            factors["vix"] = {"points": pts, "threshold_hit": True, "side": "sell"}
        else:
            factors["vix"] = {"points": 0, "threshold_hit": False, "side": "buy"}

        # ------------------------------------------------------------------
        # Supertrend (bidirectional — single "supertrend" factor key)
        # ------------------------------------------------------------------
        supertrend_lower = (inputs.supertrend or "").lower().strip()
        if supertrend_lower == "bullish":
            pts = 10
            buy_points += pts
            factors["supertrend"] = {"points": pts, "threshold_hit": True, "side": "buy"}
        elif supertrend_lower == "bearish":
            pts = 10
            sell_points += pts
            factors["supertrend"] = {"points": pts, "threshold_hit": True, "side": "sell"}
        else:
            factors["supertrend"] = {"points": 0, "threshold_hit": False, "side": "buy"}

        # ------------------------------------------------------------------
        # MACD (12, 26, 9) — Phase 4 addition
        # Bullish cross (MACD crosses above signal) → buy +15
        # Bearish cross (MACD crosses below signal) → sell +15
        # Histogram direction as secondary signal → ±5
        # ------------------------------------------------------------------
        if inputs.macd_signal_cross is not None:
            cross = inputs.macd_signal_cross.lower().strip()
            if cross == "bullish_cross":
                pts = 15
                buy_points += pts
                factors["macd"] = {"points": pts, "threshold_hit": True, "side": "buy"}
            elif cross == "bearish_cross":
                pts = 15
                sell_points += pts
                factors["macd"] = {"points": pts, "threshold_hit": True, "side": "sell"}
            else:
                # No cross — use histogram direction for a weaker signal
                if inputs.macd_histogram is not None:
                    if inputs.macd_histogram > QuantSignalEngine._EPSILON:
                        pts = 5
                        buy_points += pts
                        factors["macd"] = {"points": pts, "threshold_hit": True, "side": "buy"}
                    elif inputs.macd_histogram < -QuantSignalEngine._EPSILON:
                        pts = 5
                        sell_points += pts
                        factors["macd"] = {"points": pts, "threshold_hit": True, "side": "sell"}
                    else:
                        factors["macd"] = {"points": 0, "threshold_hit": False, "side": "buy"}
                else:
                    factors["macd"] = {"points": 0, "threshold_hit": False, "side": "buy"}
        elif inputs.macd_histogram is not None:
            if inputs.macd_histogram > QuantSignalEngine._EPSILON:
                pts = 5
                buy_points += pts
                factors["macd"] = {"points": pts, "threshold_hit": True, "side": "buy"}
            elif inputs.macd_histogram < -QuantSignalEngine._EPSILON:
                pts = 5
                sell_points += pts
                factors["macd"] = {"points": pts, "threshold_hit": True, "side": "sell"}
            else:
                factors["macd"] = {"points": 0, "threshold_hit": False, "side": "buy"}
        else:
            factors["macd"] = {"points": 0, "threshold_hit": False, "side": "buy"}

        # ------------------------------------------------------------------
        # Bollinger Bands (20, 2) — Phase 4 addition
        # Price below lower band (bb_position < 0) → oversold, buy +10
        # Price above upper band (bb_position > 1) → overbought, sell +10
        # ------------------------------------------------------------------
        if inputs.bb_position is not None:
            if inputs.bb_position < 0:
                pts = 10
                buy_points += pts
                factors["bollinger"] = {"points": pts, "threshold_hit": True, "side": "buy"}
            elif inputs.bb_position > 1.0:
                pts = 10
                sell_points += pts
                factors["bollinger"] = {"points": pts, "threshold_hit": True, "side": "sell"}
            else:
                factors["bollinger"] = {"points": 0, "threshold_hit": False, "side": "buy"}
        else:
            factors["bollinger"] = {"points": 0, "threshold_hit": False, "side": "buy"}

        # ------------------------------------------------------------------
        # Direction logic
        # ------------------------------------------------------------------
        if buy_points > sell_points and buy_points > 50:
            direction = "BUY"
        elif sell_points > buy_points and sell_points > 50:
            direction = "SELL"
        else:
            direction = "HOLD"

        # ------------------------------------------------------------------
        # Total score: max of buy/sell clamped to [0, 100]
        # ------------------------------------------------------------------
        total_score = max(0, min(100, max(buy_points, sell_points)))

        # ------------------------------------------------------------------
        # Tier
        # ------------------------------------------------------------------
        if total_score > 70:
            tier = "strong"
        elif total_score >= 50:
            tier = "moderate"
        else:
            tier = "skip"

        # ------------------------------------------------------------------
        # Instrument hint
        # ------------------------------------------------------------------
        if direction == "BUY":
            instrument_hint = "BANKNIFTY_CE" if instrument_upper == "BANKNIFTY" else "NIFTY_CE"
        elif direction == "SELL":
            instrument_hint = "BANKNIFTY_PE" if instrument_upper == "BANKNIFTY" else "NIFTY_PE"
        else:
            instrument_hint = "NONE"

        return QuantScoreResult(
            total_score=total_score,
            direction=direction,
            buy_points=buy_points,
            sell_points=sell_points,
            factors=factors,
            tier=tier,
            instrument_hint=instrument_hint,
        )
