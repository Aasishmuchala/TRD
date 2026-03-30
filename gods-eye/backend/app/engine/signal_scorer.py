"""Signal scorer — combined 0-100 signal score from agent sentiment + technical indicators.

Pure, stateless module. No DB, no network, no app.config imports.

Formula:
    sentiment_component (60% weight):
        direction_multiplier: STRONG_BUY/STRONG_SELL → 1.0, BUY/SELL → 0.85, HOLD → 0.0
        sentiment_raw = conviction * direction_multiplier
        sentiment_score = sentiment_raw * 0.60

    technical_component (40% weight):
        RSI: rsi < 30 supports BUY; rsi > 70 supports SELL
        Supertrend: "bullish" supports BUY; "bearish" supports SELL
        VIX regime: "low" supports BUY; "high" supports SELL; others neutral
        OI sentiment: "bullish" supports BUY; "bearish" supports SELL; absent → neutral
        aligned_count = number of signals aligned with direction (0-4)
        tech_raw = aligned_count * 25
        technical_score = tech_raw * 0.40

    final_score = round(sentiment_score + technical_score, 1) clamped to [0, 100]

Tier mapping:
    score > 70   → "strong"
    score >= 50  → "moderate"
    score < 50   → "skip"

Instrument mapping (BUY family = BUY/STRONG_BUY; SELL family = SELL/STRONG_SELL):
    BUY  family + NIFTY     → "NIFTY_CE"
    BUY  family + BANKNIFTY → "BANKNIFTY_CE"
    SELL family + NIFTY     → "NIFTY_PE"
    SELL family + BANKNIFTY → "BANKNIFTY_PE"
    HOLD (any)              → "NONE"
    Unknown direction       → treated as HOLD
"""

from dataclasses import dataclass, field
from typing import Dict, List

# ---------------------------------------------------------------------------
# Direction constants
# ---------------------------------------------------------------------------

_BUY_FAMILY = {"BUY", "STRONG_BUY"}
_SELL_FAMILY = {"SELL", "STRONG_SELL"}

_DIRECTION_MULTIPLIER: Dict[str, float] = {
    "STRONG_BUY": 1.0,
    "STRONG_SELL": 1.0,
    "BUY": 0.85,
    "SELL": 0.85,
    "HOLD": 0.0,
}

# Weights
_SENTIMENT_WEIGHT = 0.60
_TECHNICAL_WEIGHT = 0.40
_TECH_POINTS_PER_SIGNAL = 25  # 4 signals × 25 = 100 max


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ScoreResult:
    """Result of SignalScorer.score() — pure value object, no behaviour."""

    score: float
    tier: str                       # "strong" | "moderate" | "skip"
    direction: str
    contributing_factors: List[str] = field(default_factory=list)
    suggested_instrument: str = "NONE"  # "NIFTY_CE" | "NIFTY_PE" | "BANKNIFTY_CE" | "BANKNIFTY_PE" | "NONE"


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class SignalScorer:
    """Combine agent consensus output with technical signals into a 0-100 score."""

    @staticmethod
    def score(
        direction: str,
        conviction: float,
        signals: Dict,
        instrument: str = "NIFTY",
    ) -> ScoreResult:
        """Compute combined signal score.

        Parameters
        ----------
        direction:
            Agent consensus direction. One of: BUY, SELL, HOLD, STRONG_BUY, STRONG_SELL.
            Unknown values are treated as HOLD (safe default).
        conviction:
            Weighted consensus conviction, 0-100.
        signals:
            Technical signals dict (keys: rsi, supertrend, vix_regime, oi_sentiment).
            Missing keys are treated as neutral (no contribution).
        instrument:
            "NIFTY" or "BANKNIFTY" (case-insensitive). Determines option type in output.

        Returns
        -------
        ScoreResult
        """
        # Normalise inputs
        direction = direction.upper().strip() if direction else "HOLD"
        instrument_upper = instrument.upper().strip() if instrument else "NIFTY"

        # Unknown direction → HOLD safe default
        if direction not in _DIRECTION_MULTIPLIER:
            direction = "HOLD"

        # ------------------------------------------------------------------
        # Sentiment component (60%)
        # ------------------------------------------------------------------
        direction_mult = _DIRECTION_MULTIPLIER[direction]
        sentiment_raw = conviction * direction_mult          # 0–100
        sentiment_score = sentiment_raw * _SENTIMENT_WEIGHT  # 0–60

        # ------------------------------------------------------------------
        # Technical component (40%)
        # Technical alignment is relative to direction family
        # ------------------------------------------------------------------
        is_buy_dir = direction in _BUY_FAMILY
        is_sell_dir = direction in _SELL_FAMILY
        # HOLD: technicals can still score (up to 40) but sentiment = 0 → max 40

        aligned_count = 0
        factors: List[str] = []

        # RSI
        rsi_val = signals.get("rsi")
        if rsi_val is not None:
            if is_buy_dir and rsi_val < 30:
                aligned_count += 1
                factors.append(f"RSI oversold ({rsi_val:.1f}) supports BUY")
            elif is_sell_dir and rsi_val > 70:
                aligned_count += 1
                factors.append(f"RSI overbought ({rsi_val:.1f}) supports SELL")

        # Supertrend
        supertrend = signals.get("supertrend", "").lower() if signals.get("supertrend") else ""
        if is_buy_dir and supertrend == "bullish":
            aligned_count += 1
            factors.append("Supertrend bullish")
        elif is_sell_dir and supertrend == "bearish":
            aligned_count += 1
            factors.append("Supertrend bearish")

        # VIX regime
        vix_regime = signals.get("vix_regime", "").lower() if signals.get("vix_regime") else ""
        if is_buy_dir and vix_regime == "low":
            aligned_count += 1
            factors.append("VIX low regime supports BUY")
        elif is_sell_dir and vix_regime == "high":
            aligned_count += 1
            factors.append("VIX high regime supports SELL")

        # OI sentiment (optional — absent = neutral)
        oi = signals.get("oi_sentiment", "").lower() if signals.get("oi_sentiment") else ""
        if is_buy_dir and oi == "bullish":
            aligned_count += 1
            factors.append("OI sentiment bullish supports BUY")
        elif is_sell_dir and oi == "bearish":
            aligned_count += 1
            factors.append("OI sentiment bearish supports SELL")

        tech_raw = aligned_count * _TECH_POINTS_PER_SIGNAL     # 0–100
        technical_score = tech_raw * _TECHNICAL_WEIGHT         # 0–40

        # ------------------------------------------------------------------
        # Final score
        # ------------------------------------------------------------------
        raw = sentiment_score + technical_score
        final_score = round(max(0.0, min(100.0, raw)), 1)

        # ------------------------------------------------------------------
        # Tier
        # ------------------------------------------------------------------
        if final_score > 70:
            tier = "strong"
        elif final_score >= 50:
            tier = "moderate"
        else:
            tier = "skip"

        # ------------------------------------------------------------------
        # Contributing factors — always include agent conviction entry
        # ------------------------------------------------------------------
        factors.append(f"Agent conviction: {conviction:.1f} ({direction})")

        # ------------------------------------------------------------------
        # Suggested instrument
        # ------------------------------------------------------------------
        if direction in _BUY_FAMILY:
            if instrument_upper == "BANKNIFTY":
                suggested = "BANKNIFTY_CE"
            else:
                suggested = "NIFTY_CE"
        elif direction in _SELL_FAMILY:
            if instrument_upper == "BANKNIFTY":
                suggested = "BANKNIFTY_PE"
            else:
                suggested = "NIFTY_PE"
        else:
            suggested = "NONE"

        return ScoreResult(
            score=final_score,
            tier=tier,
            direction=direction,
            contributing_factors=factors,
            suggested_instrument=suggested,
        )
