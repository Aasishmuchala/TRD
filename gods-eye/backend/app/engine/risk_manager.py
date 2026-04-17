"""RiskManager — deterministic position sizing and stop/target computation.

Pure module: no I/O, no DB, no network, no app.* imports.
Only stdlib + dataclasses.

Formulas
--------
  stop_distance   = VIX * STOP_MULTIPLIER       (default 5.0)
  target_distance = stop_distance * RISK_REWARD_RATIO  (default 1.5)

Lot sizing
----------
  tier == "strong"   (score > 70)  → lots = 2
  tier == "moderate" (score 50-70) → lots = 1
  tier == "skip"     (score < 50)  → lots = 0  (all distances and levels = entry_close)

Directional levels
------------------
  BUY:  stop_level  = entry_close - stop_distance
        target_level = entry_close + target_distance
  SELL: stop_level  = entry_close + stop_distance
        target_level = entry_close - target_distance
  HOLD: stop_level  = entry_close (no directional offset)
        target_level = entry_close (no directional offset)
"""

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Module-level constants (overridable by callers via optional params in future)
# ---------------------------------------------------------------------------

STOP_MULTIPLIER: float = 5.0
RISK_REWARD_RATIO: float = 1.5


# ---------------------------------------------------------------------------
# RiskParams dataclass
# ---------------------------------------------------------------------------

@dataclass
class RiskParams:
    """Output of RiskManager.compute().

    All fields are computed deterministically from (tier, direction, entry_close, vix).
    """

    lots: int            # 0, 1, or 2 based on tier
    stop_distance: float  # points away from entry (0 when tier==skip)
    target_distance: float  # points away from entry — always 1.5 * stop_distance (0 when skip)
    stop_level: float    # absolute index level (entry_close ± stop_distance)
    target_level: float  # absolute index level (entry_close ± target_distance)
    vix_used: float      # VIX value used in computation (for response transparency)
    risk_reward: float   # always 1.5 (constant, shown for UI clarity)


# ---------------------------------------------------------------------------
# RiskManager
# ---------------------------------------------------------------------------

class RiskManager:
    """Pure static methods for position sizing and stop/target computation.

    No instance state. No side effects. Safe to call from any context.

    TRD-L6: This module is used by hybrid_backtest.py (line 239) and imported
    (but not called) in paper_trader.py. The main backtest_engine.py and
    orchestrator.py do NOT use this module — they use StopLossEngine instead.
    Consider either integrating RiskManager into the main pipeline or removing
    the unused import from paper_trader.py.
    """

    @staticmethod
    def compute(
        tier: str,
        direction: str,
        entry_close: float,
        vix: float,
    ) -> RiskParams:
        """Compute position sizing and stop/target levels from signal parameters.

        Parameters
        ----------
        tier : str
            Signal strength tier — "strong", "moderate", or "skip".
            Any other value is treated as "skip".
        direction : str
            Trade direction — "BUY", "SELL", or "HOLD".
            "HOLD" produces distances but no directional offset on levels.
        entry_close : float
            Index closing price at entry (must be > 0).
        vix : float
            Current India VIX value (must be > 0).

        Returns
        -------
        RiskParams
            Fully-computed risk parameters. See RiskParams dataclass.

        Raises
        ------
        ValueError
            If vix <= 0 or entry_close <= 0.
        """
        # Input validation
        if vix <= 0:
            raise ValueError("VIX must be positive")
        if entry_close <= 0:
            raise ValueError("entry_close must be positive")

        # Normalise tier — unknown values become "skip"
        normalised_tier = tier if tier in ("strong", "moderate", "skip") else "skip"

        # Lot sizing
        if normalised_tier == "strong":
            lots = 2
        elif normalised_tier == "moderate":
            lots = 1
        else:  # skip or unknown
            lots = 0

        # Skip path: zero distances, levels stay at entry
        if lots == 0:
            return RiskParams(
                lots=0,
                stop_distance=0.0,
                target_distance=0.0,
                stop_level=entry_close,
                target_level=entry_close,
                vix_used=vix,
                risk_reward=RISK_REWARD_RATIO,
            )

        # Stop and target distances
        stop_distance = round(vix * STOP_MULTIPLIER, 1)
        target_distance = round(stop_distance * RISK_REWARD_RATIO, 1)

        # Directional levels
        direction_upper = direction.upper()
        if direction_upper == "BUY":
            stop_level = entry_close - stop_distance
            target_level = entry_close + target_distance
        elif direction_upper == "SELL":
            stop_level = entry_close + stop_distance
            target_level = entry_close - target_distance
        else:
            # HOLD or unrecognised — no directional offset
            stop_level = entry_close
            target_level = entry_close

        return RiskParams(
            lots=lots,
            stop_distance=stop_distance,
            target_distance=target_distance,
            stop_level=stop_level,
            target_level=target_level,
            vix_used=vix,
            risk_reward=RISK_REWARD_RATIO,
        )
