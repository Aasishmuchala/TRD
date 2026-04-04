"""Feedback engine — accuracy-driven weight tuning and prompt hints.

This is the self-learning loop from Part 4 of the plan:
  accuracy → weight adjustment → prompt evolution → better predictions

The engine reads agent accuracy from AgentMemory and produces:
  1. Dynamic agent weights (overriding config defaults)
  2. Prompt hints injected into agent context (via ProfileGenerator)
"""

from typing import Dict, List, Optional, Tuple
from app.memory.agent_memory import AgentMemory, AgentAccuracyStats
from app.config import config


class FeedbackEngine:
    """Auto-tunes agent weights and generates prompt corrections from accuracy data.

    Weight tuning formula (from plan):
      new_weight = base_weight × (accuracy_score / avg_accuracy_all_agents)
      Capped at ±20% of base weight to prevent oscillation

    Requires minimum 30 predictions with outcomes before activating.
    Below threshold, returns default weights.
    """

    MIN_PREDICTIONS_FOR_TUNING = 15  # Lowered from 30 — activate weight tuning earlier
    MAX_WEIGHT_ADJUSTMENT = 0.20  # ±20% cap

    def __init__(self, agent_memory: AgentMemory):
        self.memory = agent_memory

    def get_tuned_weights(
        self, lookback_days: int = 90, vix_regime: Optional[str] = None
    ) -> Dict[str, float]:
        """Compute accuracy-tuned agent weights, optionally stratified by VIX regime.

        Args:
            lookback_days: How far back to look for predictions.
            vix_regime: Optional VIX regime ("low_vix", "normal_vix",
                       "elevated_vix", "high_vix"). If provided, uses
                       regime-specific accuracy for tuning so different
                       agents get higher weight in different regimes.

        Returns default weights if insufficient data.
        Returns tuned weights if >= MIN_PREDICTIONS_FOR_TUNING predictions exist.
        """
        base_weights = dict(config.AGENT_WEIGHTS)
        agent_keys = list(base_weights.keys())

        # Get accuracy stats for all agents (regime-specific if requested)
        stats: Dict[str, AgentAccuracyStats] = {}
        for key in agent_keys:
            if vix_regime:
                s = self.memory.get_agent_accuracy_by_regime(key, vix_regime, lookback_days)
            else:
                s = self.memory.get_agent_accuracy(key, lookback_days)
            if s.total_predictions > 0:
                stats[key] = s

        # Check if we have enough data
        total_predictions = sum(s.total_predictions for s in stats.values())
        if total_predictions < self.MIN_PREDICTIONS_FOR_TUNING:
            return base_weights

        # Compute average accuracy across all agents with data
        accuracies = {k: s.accuracy_pct / 100.0 for k, s in stats.items() if s.total_predictions >= 5}
        if not accuracies:
            return base_weights

        avg_accuracy = sum(accuracies.values()) / len(accuracies)

        # Avoid division by zero
        if avg_accuracy == 0:
            return base_weights

        # Tune weights
        tuned = {}
        for key in agent_keys:
            base = base_weights[key]

            if key in accuracies:
                # Accuracy ratio: >1 means better than average, <1 means worse
                ratio = accuracies[key] / avg_accuracy

                # Apply with cap
                adjustment = ratio - 1.0  # e.g., 0.15 means 15% better than avg
                capped_adjustment = max(-self.MAX_WEIGHT_ADJUSTMENT, min(self.MAX_WEIGHT_ADJUSTMENT, adjustment))
                tuned[key] = base * (1.0 + capped_adjustment)
            else:
                tuned[key] = base

        # Normalize weights to sum to 1.0
        total = sum(tuned.values())
        if total > 0:
            tuned = {k: v / total for k, v in tuned.items()}

        return tuned

    def get_weight_changes(self, lookback_days: int = 90) -> Dict[str, Dict]:
        """Get detailed weight change info for each agent (for UI/debugging)."""
        base_weights = dict(config.AGENT_WEIGHTS)
        tuned_weights = self.get_tuned_weights(lookback_days)

        changes = {}
        for key in base_weights:
            base = base_weights[key]
            tuned = tuned_weights[key]
            change_pct = ((tuned - base) / base * 100) if base > 0 else 0

            stats = self.memory.get_agent_accuracy(key, lookback_days)
            changes[key] = {
                "base_weight": round(base, 4),
                "tuned_weight": round(tuned, 4),
                "change_pct": round(change_pct, 1),
                "accuracy_pct": stats.accuracy_pct,
                "total_predictions": stats.total_predictions,
                "reason": self._explain_change(key, change_pct, stats),
            }

        return changes

    def get_prompt_hints(self, agent_key: str) -> str:
        """Generate corrective prompt hints based on failure patterns.

        These hints are prepended to the agent's prompt to help it
        avoid repeated mistakes. This is "prompt evolution" from the plan.
        """
        patterns = self.memory.detect_failure_patterns(agent_key)
        if not patterns:
            return ""

        hints = ["CALIBRATION NOTES (based on your past performance):"]
        for pattern in patterns[:3]:  # Max 3 hints
            if pattern.pattern_type == "overconfident_buy":
                hints.append(
                    f"  - You tend to be overconfident on BUY calls (wrong {pattern.sample_count} times at >70% conviction). "
                    f"Consider lowering conviction on BUY unless evidence is overwhelming."
                )
            elif pattern.pattern_type == "overconfident_sell":
                hints.append(
                    f"  - You tend to be overconfident on SELL calls (wrong {pattern.sample_count} times at >70% conviction). "
                    f"Consider lowering conviction on SELL unless evidence is overwhelming."
                )
            elif pattern.pattern_type == "context_weakness":
                hints.append(
                    f"  - Your accuracy drops significantly in '{pattern.example_contexts[0]}' scenarios. "
                    f"Be extra cautious and consider defaulting to HOLD with moderate conviction."
                )

        return "\n".join(hints)

    def should_activate(self) -> bool:
        """Check if feedback engine has enough data to be useful."""
        total = 0
        for key in config.AGENT_WEIGHTS:
            stats = self.memory.get_agent_accuracy(key, lookback_days=90)
            total += stats.total_predictions
        return total >= self.MIN_PREDICTIONS_FOR_TUNING

    @staticmethod
    def _explain_change(agent_key: str, change_pct: float, stats: AgentAccuracyStats) -> str:
        """Human-readable explanation of weight change."""
        if stats.total_predictions < 5:
            return "Insufficient data — using default weight"
        if abs(change_pct) < 1:
            return f"Performing near average ({stats.accuracy_pct:.0f}% accuracy)"
        elif change_pct > 0:
            return f"Weight increased: {stats.accuracy_pct:.0f}% accuracy (above average)"
        else:
            return f"Weight decreased: {stats.accuracy_pct:.0f}% accuracy (below average)"
