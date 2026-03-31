"""HybridScorer — pure fusion engine combining quantitative score with agent consensus.

Formula (HYB-01):
    hybrid_score = round(quant_score * 0.60 + agent_consensus_score * 0.40, 1)
    hybrid_score clamped to [0, 100]

Agent consensus derivation:
    For each agent in final_outputs:
        direction_weight: BUY/STRONG_BUY → +1.0; SELL/STRONG_SELL → -1.0; HOLD → 0.0
        weighted_sum += direction_weight * conviction
    weighted_avg = weighted_sum / agent_count
    agent_consensus_score = max(0, min(100, abs(weighted_avg)))
    consensus_direction = "BUY" if weighted_avg > 0; "SELL" if < 0; "HOLD" if == 0

Direction-lock invariant (HYB-03):
    quant_result.direction is ALWAYS the final direction.
    The validator CANNOT flip direction. Only conviction and tradeable status are mutable.

Validator verdict semantics:
    "confirm"  → conviction = hybrid_score; tradeable = True
    "adjust"   → conviction = max(0, hybrid_score - adjustment_amount); tradeable = True if conviction > 0
    "skip"     → conviction = 0; tradeable = False; tier overridden to "skip"

Tier after validation:
    hybrid_score > 70 AND verdict != "skip"  → "strong"
    hybrid_score >= 50 AND verdict != "skip" → "moderate"
    hybrid_score < 50 OR verdict == "skip"   → "skip"

Instrument hint (HYB-04):
    Follows quant_result.instrument_hint when quant direction != HOLD.
    Falls back to consensus_direction when quant is HOLD.
    If consensus also HOLD/indeterminate: "NONE".

No I/O. No DB. No network. No app.config imports. Only stdlib + dataclasses + typing.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.engine.quant_signal_engine import QuantScoreResult
from app.api.schemas import AgentResponse


# ---------------------------------------------------------------------------
# Verdict literals
# ---------------------------------------------------------------------------

VERDICT_CONFIRM = "confirm"
VERDICT_ADJUST = "adjust"
VERDICT_SKIP = "skip"

# Direction → numeric weight
_DIRECTION_WEIGHT: Dict[str, float] = {
    "STRONG_BUY": 1.0,
    "BUY": 1.0,
    "HOLD": 0.0,
    "SELL": -1.0,
    "STRONG_SELL": -1.0,
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ValidatorVerdict:
    """Result from the LLM validator (or mock validator in tests/plan 02)."""

    verdict: str                          # "confirm" | "adjust" | "skip"
    reasoning: str                        # plain-language explanation
    adjustment_amount: float = 0.0        # only used for "adjust"; conviction pts to subtract


@dataclass
class AgentBreakdownEntry:
    """Per-agent direction + conviction snapshot used in agent_breakdown."""

    direction: str
    conviction: float


@dataclass
class HybridResult:
    """Fully fused signal ready for API response and downstream consumers."""

    direction: str                                     # Final direction (quant direction, locked)
    hybrid_score: float                                # 0-100 fused score
    conviction: float                                  # Post-validation conviction (may be reduced)
    tradeable: bool                                    # False if skip verdict or score < 50
    tier: str                                          # "strong" | "moderate" | "skip"
    instrument_hint: str                               # From quant or fallback consensus
    quant_breakdown: Dict                              # quant score + factors (from QuantScoreResult)
    agent_breakdown: Dict[str, AgentBreakdownEntry]    # per-agent direction + conviction
    agent_consensus_score: float                       # Derived agent consensus component (pre-fusion)
    validator_verdict: str                             # "confirm" | "adjust" | "skip"
    validator_reasoning: str                           # LLM or mock explanation


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class HybridScorer:
    """Pure fusion engine. All methods are static. No instance state. No I/O."""

    @staticmethod
    def compute_agent_consensus(
        final_outputs: Dict[str, AgentResponse],
    ) -> Tuple[float, str]:
        """Compute agent consensus score and direction from final_outputs.

        Parameters
        ----------
        final_outputs:
            Dict mapping agent_key → AgentResponse.

        Returns
        -------
        (consensus_score, consensus_direction)
            consensus_score: 0-100 representing strength of agreement
            consensus_direction: "BUY" | "SELL" | "HOLD"
        """
        if not final_outputs:
            return 0.0, "HOLD"

        weighted_sum = 0.0
        for agent_response in final_outputs.values():
            weight = _DIRECTION_WEIGHT.get(agent_response.direction.upper(), 0.0)
            weighted_sum += weight * agent_response.conviction

        weighted_avg = weighted_sum / len(final_outputs)

        # Consensus score: absolute strength, clamped to [0, 100]
        consensus_score = max(0.0, min(100.0, abs(weighted_avg)))

        # Consensus direction from sign of weighted average
        if weighted_avg > 0.0:
            consensus_direction = "BUY"
        elif weighted_avg < 0.0:
            consensus_direction = "SELL"
        else:
            consensus_direction = "HOLD"

        return consensus_score, consensus_direction

    @staticmethod
    def _derive_instrument_hint(
        quant_result: QuantScoreResult,
        consensus_direction: str,
    ) -> str:
        """Determine instrument hint following HYB-04 rule.

        Quant instrument_hint takes priority when quant direction != HOLD.
        Falls back to consensus_direction-derived hint when quant is HOLD.
        """
        if quant_result.direction != "HOLD":
            return quant_result.instrument_hint

        # Quant is HOLD — fall back to consensus direction
        if consensus_direction == "BUY":
            # Default to NIFTY_CE as a generic fallback (quant doesn't specify instrument at HOLD)
            return "NIFTY_CE"
        elif consensus_direction == "SELL":
            return "NIFTY_PE"
        else:
            return "NONE"

    @staticmethod
    def fuse(
        quant_result: QuantScoreResult,
        final_outputs: Dict[str, AgentResponse],
        validator: ValidatorVerdict,
    ) -> HybridResult:
        """Fuse quant score with agent consensus and apply validator verdict.

        Pure function. No I/O. No side effects.

        Parameters
        ----------
        quant_result:
            Output from QuantSignalEngine.compute_quant_score().
        final_outputs:
            Dict mapping agent_key → AgentResponse (from Orchestrator.run_simulation()).
        validator:
            ValidatorVerdict — can be LLM-generated or mock.

        Returns
        -------
        HybridResult with all fused signal fields.
        """
        # --- Step 1: Agent consensus ---
        agent_consensus_score, consensus_direction = HybridScorer.compute_agent_consensus(
            final_outputs
        )

        # --- Step 2: Hybrid score (HYB-01) ---
        raw_hybrid = quant_result.total_score * 0.60 + agent_consensus_score * 0.40
        hybrid_score = round(max(0.0, min(100.0, raw_hybrid)), 1)

        # --- Step 3: Direction lock (HYB-03) — quant ALWAYS wins ---
        final_direction = quant_result.direction

        # --- Step 4: Apply validator verdict ---
        verdict = validator.verdict

        if verdict == VERDICT_CONFIRM:
            conviction = hybrid_score
            tradeable = True
        elif verdict == VERDICT_ADJUST:
            conviction = round(max(0.0, hybrid_score - validator.adjustment_amount), 1)
            tradeable = conviction > 0.0
        elif verdict == VERDICT_SKIP:
            conviction = 0.0
            tradeable = False
        else:
            # Unknown verdict — treat as confirm (defensive)
            conviction = hybrid_score
            tradeable = True

        # --- Step 5: Tier (after validation) ---
        if verdict == VERDICT_SKIP:
            tier = "skip"
        elif hybrid_score > 70.0:
            tier = "strong"
        elif hybrid_score >= 50.0:
            tier = "moderate"
        else:
            tier = "skip"

        # --- Step 6: Instrument hint (HYB-04) ---
        instrument_hint = HybridScorer._derive_instrument_hint(quant_result, consensus_direction)

        # --- Step 7: Build breakdown dicts ---
        quant_breakdown: Dict = {
            "score": quant_result.total_score,
            "direction": quant_result.direction,
            "tier": quant_result.tier,
            "factors": quant_result.factors,
        }

        agent_breakdown: Dict[str, AgentBreakdownEntry] = {
            agent_key: AgentBreakdownEntry(
                direction=response.direction,
                conviction=response.conviction,
            )
            for agent_key, response in final_outputs.items()
        }

        return HybridResult(
            direction=final_direction,
            hybrid_score=hybrid_score,
            conviction=conviction,
            tradeable=tradeable,
            tier=tier,
            instrument_hint=instrument_hint,
            quant_breakdown=quant_breakdown,
            agent_breakdown=agent_breakdown,
            agent_consensus_score=agent_consensus_score,
            validator_verdict=verdict,
            validator_reasoning=validator.reasoning,
        )
