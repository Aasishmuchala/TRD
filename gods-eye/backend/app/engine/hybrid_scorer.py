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


# ---------------------------------------------------------------------------
# LLM Validator
# ---------------------------------------------------------------------------


class LLMValidator:
    """Single LLM call that reviews the hybrid signal and returns a ValidatorVerdict."""

    VALIDATOR_PROMPT_TEMPLATE = """\
You are a disciplined options trader reviewing a hybrid market signal before acting on it.

SIGNAL SUMMARY
==============
Instrument   : {instrument}
Date         : {date}
Direction    : {direction}
Hybrid Score : {hybrid_score:.1f} / 100  ({tier})

QUANT ENGINE (60% weight)
-------------------------
Score     : {quant_score}
Direction : {quant_direction}
Factors fired:
{quant_factors_text}

AGENT CONSENSUS (40% weight)
----------------------------
Consensus score : {agent_consensus_score:.1f}
Per-agent calls :
{agent_calls_text}

YOUR TASK
=========
Decide ONE of:
  confirm  — signal is coherent; conviction stands as-is
  adjust   — signal has meaningful contradiction or risk; reduce conviction by 10-30 pts
  skip     — signal has a fatal flaw or extreme contradiction; do NOT trade

Rules you MUST follow:
1. You CANNOT change the direction ({direction}). Only conviction and tradeable status are yours to influence.
2. "adjust" is appropriate when quant and agent consensus disagree on direction OR a key
   risk factor (e.g., VIX spike, PCR extreme not reflected in quant) is visible.
3. "skip" is appropriate ONLY when both quant and majority of agents disagree, or when
   the instrument is at a known event risk (earnings, RBI decision, index expiry) that
   makes directional prediction unreliable.
4. Keep your reasoning to 2 sentences maximum.

RESPONSE FORMAT (JSON only, no other text):
{{
  "verdict": "confirm" | "adjust" | "skip",
  "reasoning": "<2 sentences max>",
  "adjustment_amount": <number 0-30, use 0 for confirm/skip>
}}
"""

    @staticmethod
    def _build_quant_factors_text(quant_breakdown: dict) -> str:
        """Format quant factors for the prompt."""
        lines = []
        for name, data in quant_breakdown.get("factors", {}).items():
            if data.get("threshold_hit"):
                lines.append(f"  - {name}: +{data['points']} pts ({data['side']})")
        return "\n".join(lines) if lines else "  (no factors fired)"

    @staticmethod
    def _build_agent_calls_text(agent_breakdown: dict) -> str:
        """Format per-agent calls for the prompt."""
        lines = []
        for agent_key, data in agent_breakdown.items():
            direction = data["direction"] if isinstance(data, dict) else data.direction
            conviction = data["conviction"] if isinstance(data, dict) else data.conviction
            lines.append(f"  - {agent_key}: {direction} @ {conviction:.0f}")
        return "\n".join(lines) if lines else "  (no agents)"

    @staticmethod
    def _parse_verdict_response(raw: str) -> ValidatorVerdict:
        """Parse JSON verdict from LLM response. Falls back to confirm on parse error."""
        import json, re
        try:
            # Strip markdown fences if present
            text = re.sub(r"```(?:json)?|```", "", raw).strip()
            data = json.loads(text)
            verdict = data.get("verdict", "confirm").lower()
            if verdict not in ("confirm", "adjust", "skip"):
                verdict = "confirm"
            return ValidatorVerdict(
                verdict=verdict,
                reasoning=str(data.get("reasoning", ""))[:500],
                adjustment_amount=float(data.get("adjustment_amount", 0)),
            )
        except Exception:
            # Safe fallback: confirm so we never crash the trade signal
            return ValidatorVerdict(
                verdict="confirm",
                reasoning="Validator response parse error — defaulting to confirm.",
                adjustment_amount=0.0,
            )

    @classmethod
    async def call_validator(
        cls,
        hybrid_result: "HybridResult",
        instrument: str,
        date: str,
    ) -> ValidatorVerdict:
        """Make the single LLM validator call. Returns ValidatorVerdict."""
        from app.auth.llm_client import get_llm_client

        quant_factors_text = cls._build_quant_factors_text(hybrid_result.quant_breakdown)
        agent_calls_text = cls._build_agent_calls_text(hybrid_result.agent_breakdown)

        prompt = cls.VALIDATOR_PROMPT_TEMPLATE.format(
            instrument=instrument.upper(),
            date=date,
            direction=hybrid_result.direction,
            hybrid_score=hybrid_result.hybrid_score,
            tier=hybrid_result.tier,
            quant_score=hybrid_result.quant_breakdown.get("score", 0),
            quant_direction=hybrid_result.quant_breakdown.get("direction", "HOLD"),
            quant_factors_text=quant_factors_text,
            agent_consensus_score=hybrid_result.agent_consensus_score,
            agent_calls_text=agent_calls_text,
        )

        llm = get_llm_client()
        raw = await llm.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )
        return cls._parse_verdict_response(raw)
