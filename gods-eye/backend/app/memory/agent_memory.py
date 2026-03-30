"""Per-agent memory system — tracks predictions, accuracy, and failure patterns.

Adapted from MiroFish's Zep-based agent memory pattern (zep_tools.py).
Uses SQLite instead of Zep Cloud for Phase 1.

The key insight: an FII agent that "remembers" it was wrong about DXY > 105 last time
can adjust its conviction. This builds compounding intelligence over time.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class AgentAccuracyStats:
    """Accuracy statistics for a single agent."""
    agent_key: str
    total_predictions: int
    correct_predictions: int
    accuracy_pct: float
    avg_conviction_correct: float  # Average conviction when agent was right
    avg_conviction_wrong: float  # Average conviction when agent was wrong
    calibration_score: float  # How well conviction matches actual accuracy
    direction_breakdown: Dict[str, Dict]  # Per-direction accuracy
    recent_streak: int  # Positive = wins, negative = losses
    strongest_context: str  # Context where agent is most accurate
    weakest_context: str  # Context where agent is least accurate


@dataclass
class FailurePattern:
    """Detected pattern in agent failures."""
    agent_key: str
    pattern_type: str  # "overconfident_buy", "misses_reversals", "context_blind", etc.
    description: str
    frequency: float  # 0-1, how often this pattern appears
    sample_count: int
    example_contexts: List[str]


class AgentMemory:
    """Per-agent memory with accuracy tracking and failure pattern detection.

    Schema extends PredictionTracker with agent-level granularity.
    PredictionTracker logs aggregate predictions; AgentMemory tracks
    each agent's individual calls within those predictions.
    """

    def __init__(self, db_path: str = "gods_eye.db"):
        self.db_path = db_path
        self._init_tables()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        """Create agent memory tables if they don't exist."""
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS agent_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    simulation_id TEXT NOT NULL,
                    agent_key TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    context TEXT DEFAULT 'normal',
                    direction TEXT NOT NULL,
                    conviction REAL NOT NULL,
                    reasoning TEXT,
                    key_triggers TEXT,
                    round_num INTEGER DEFAULT 3,
                    actual_direction TEXT,
                    was_correct INTEGER,
                    market_snapshot TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_agent_pred_key
                    ON agent_predictions(agent_key);
                CREATE INDEX IF NOT EXISTS idx_agent_pred_context
                    ON agent_predictions(agent_key, context);
                CREATE INDEX IF NOT EXISTS idx_agent_pred_time
                    ON agent_predictions(timestamp DESC);

                CREATE TABLE IF NOT EXISTS agent_weight_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    agent_key TEXT NOT NULL,
                    old_weight REAL NOT NULL,
                    new_weight REAL NOT NULL,
                    reason TEXT
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def log_agent_prediction(
        self,
        simulation_id: str,
        agent_key: str,
        direction: str,
        conviction: float,
        reasoning: str = "",
        key_triggers: List[str] = None,
        context: str = "normal",
        round_num: int = 3,
        market_snapshot: Dict = None,
    ):
        """Log a single agent's prediction for accuracy tracking."""
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO agent_predictions
                   (simulation_id, agent_key, timestamp, context, direction,
                    conviction, reasoning, key_triggers, round_num, market_snapshot)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    simulation_id,
                    agent_key,
                    datetime.now().isoformat(),
                    context,
                    direction,
                    conviction,
                    reasoning,
                    json.dumps(key_triggers or []),
                    round_num,
                    json.dumps(market_snapshot or {}),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def record_agent_outcome(
        self, simulation_id: str, actual_direction: str
    ) -> int:
        """Record actual outcome for all agents in a simulation.

        Returns number of agent records updated.
        """
        # Map actual_direction to simplified form for comparison
        actual_simplified = self._simplify_direction(actual_direction)

        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT id, direction FROM agent_predictions WHERE simulation_id = ?",
                (simulation_id,),
            ).fetchall()

            updated = 0
            for row in rows:
                predicted_simplified = self._simplify_direction(row["direction"])
                was_correct = 1 if predicted_simplified == actual_simplified else 0
                conn.execute(
                    "UPDATE agent_predictions SET actual_direction = ?, was_correct = ? WHERE id = ?",
                    (actual_direction, was_correct, row["id"]),
                )
                updated += 1

            conn.commit()
            return updated
        finally:
            conn.close()

    def get_agent_accuracy(
        self, agent_key: str, lookback_days: int = 90
    ) -> AgentAccuracyStats:
        """Compute comprehensive accuracy stats for an agent."""
        cutoff = (datetime.now() - timedelta(days=lookback_days)).isoformat()
        conn = self._get_conn()
        try:
            # Get all predictions with outcomes
            rows = conn.execute(
                """SELECT direction, conviction, context, was_correct
                   FROM agent_predictions
                   WHERE agent_key = ? AND timestamp > ? AND was_correct IS NOT NULL""",
                (agent_key, cutoff),
            ).fetchall()

            if not rows:
                return AgentAccuracyStats(
                    agent_key=agent_key,
                    total_predictions=0,
                    correct_predictions=0,
                    accuracy_pct=0.0,
                    avg_conviction_correct=0.0,
                    avg_conviction_wrong=0.0,
                    calibration_score=0.0,
                    direction_breakdown={},
                    recent_streak=0,
                    strongest_context="unknown",
                    weakest_context="unknown",
                )

            total = len(rows)
            correct = sum(1 for r in rows if r["was_correct"])
            accuracy = correct / total if total > 0 else 0.0

            # Conviction breakdown
            correct_convictions = [r["conviction"] for r in rows if r["was_correct"]]
            wrong_convictions = [r["conviction"] for r in rows if not r["was_correct"]]
            avg_conv_correct = sum(correct_convictions) / len(correct_convictions) if correct_convictions else 0.0
            avg_conv_wrong = sum(wrong_convictions) / len(wrong_convictions) if wrong_convictions else 0.0

            # Calibration: how well conviction predicts accuracy
            # Group by conviction buckets and compare predicted vs actual
            calibration = self._compute_calibration(rows)

            # Per-direction breakdown
            direction_breakdown = {}
            for direction in ["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]:
                dir_rows = [r for r in rows if r["direction"] == direction]
                if dir_rows:
                    dir_correct = sum(1 for r in dir_rows if r["was_correct"])
                    direction_breakdown[direction] = {
                        "total": len(dir_rows),
                        "correct": dir_correct,
                        "accuracy": dir_correct / len(dir_rows),
                    }

            # Recent streak
            recent = conn.execute(
                """SELECT was_correct FROM agent_predictions
                   WHERE agent_key = ? AND was_correct IS NOT NULL
                   ORDER BY timestamp DESC LIMIT 20""",
                (agent_key,),
            ).fetchall()
            streak = self._compute_streak(recent)

            # Context analysis
            strongest, weakest = self._analyze_context_performance(rows)

            return AgentAccuracyStats(
                agent_key=agent_key,
                total_predictions=total,
                correct_predictions=correct,
                accuracy_pct=round(accuracy * 100, 1),
                avg_conviction_correct=round(avg_conv_correct, 1),
                avg_conviction_wrong=round(avg_conv_wrong, 1),
                calibration_score=round(calibration, 2),
                direction_breakdown=direction_breakdown,
                recent_streak=streak,
                strongest_context=strongest,
                weakest_context=weakest,
            )
        finally:
            conn.close()

    def detect_failure_patterns(
        self, agent_key: str, min_samples: int = 10
    ) -> List[FailurePattern]:
        """Detect systematic failure patterns for an agent.

        This is the "prompt evolution" input — knowing *how* an agent fails
        allows the system to add corrective context to future prompts.
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT direction, conviction, context, was_correct, reasoning
                   FROM agent_predictions
                   WHERE agent_key = ? AND was_correct IS NOT NULL""",
                (agent_key,),
            ).fetchall()

            if len(rows) < min_samples:
                return []

            patterns = []
            wrong_rows = [r for r in rows if not r["was_correct"]]
            total_wrong = len(wrong_rows)

            if total_wrong < 3:
                return []

            # Pattern 1: Overconfident on buys
            high_conv_buy_wrong = [
                r for r in wrong_rows
                if r["direction"] in ("BUY", "STRONG_BUY") and r["conviction"] > 70
            ]
            if len(high_conv_buy_wrong) >= 3:
                freq = len(high_conv_buy_wrong) / total_wrong
                contexts = list(set(r["context"] for r in high_conv_buy_wrong))[:3]
                patterns.append(FailurePattern(
                    agent_key=agent_key,
                    pattern_type="overconfident_buy",
                    description=f"Agent is wrong {len(high_conv_buy_wrong)} times when calling BUY/STRONG_BUY with >70% conviction",
                    frequency=round(freq, 2),
                    sample_count=len(high_conv_buy_wrong),
                    example_contexts=contexts,
                ))

            # Pattern 2: Overconfident on sells
            high_conv_sell_wrong = [
                r for r in wrong_rows
                if r["direction"] in ("SELL", "STRONG_SELL") and r["conviction"] > 70
            ]
            if len(high_conv_sell_wrong) >= 3:
                freq = len(high_conv_sell_wrong) / total_wrong
                contexts = list(set(r["context"] for r in high_conv_sell_wrong))[:3]
                patterns.append(FailurePattern(
                    agent_key=agent_key,
                    pattern_type="overconfident_sell",
                    description=f"Agent is wrong {len(high_conv_sell_wrong)} times when calling SELL/STRONG_SELL with >70% conviction",
                    frequency=round(freq, 2),
                    sample_count=len(high_conv_sell_wrong),
                    example_contexts=contexts,
                ))

            # Pattern 3: Context-specific weakness
            context_accuracy = {}
            for r in rows:
                ctx = r["context"]
                if ctx not in context_accuracy:
                    context_accuracy[ctx] = {"correct": 0, "total": 0}
                context_accuracy[ctx]["total"] += 1
                if r["was_correct"]:
                    context_accuracy[ctx]["correct"] += 1

            for ctx, stats in context_accuracy.items():
                if stats["total"] >= 5:
                    acc = stats["correct"] / stats["total"]
                    if acc < 0.35:  # Below 35% in a specific context
                        patterns.append(FailurePattern(
                            agent_key=agent_key,
                            pattern_type="context_weakness",
                            description=f"Agent accuracy drops to {acc:.0%} in '{ctx}' context ({stats['correct']}/{stats['total']})",
                            frequency=round(1 - acc, 2),
                            sample_count=stats["total"],
                            example_contexts=[ctx],
                        ))

            # Pattern 4: Always disagrees with consensus (contrarian bias)
            # This would need consensus data which we don't have per-row yet
            # Future enhancement

            return patterns
        finally:
            conn.close()

    def get_agent_history_summary(
        self, agent_key: str, limit: int = 5
    ) -> str:
        """Build a natural language summary of agent's recent performance.

        This text is injected into the agent's prompt so it can self-correct.
        """
        stats = self.get_agent_accuracy(agent_key, lookback_days=30)
        patterns = self.detect_failure_patterns(agent_key)

        if stats.total_predictions == 0:
            return ""

        lines = [
            f"YOUR RECENT PERFORMANCE ({stats.total_predictions} predictions, last 30 days):",
            f"  Overall accuracy: {stats.accuracy_pct:.0f}%",
        ]

        if stats.avg_conviction_correct > 0:
            lines.append(
                f"  Avg conviction when correct: {stats.avg_conviction_correct:.0f}% | "
                f"when wrong: {stats.avg_conviction_wrong:.0f}%"
            )

        if stats.calibration_score > 0:
            lines.append(f"  Calibration score: {stats.calibration_score:.2f} (1.0 = perfectly calibrated)")

        # Direction breakdown
        for direction, data in stats.direction_breakdown.items():
            if data["total"] >= 3:
                lines.append(f"  {direction}: {data['accuracy']:.0%} accurate ({data['correct']}/{data['total']})")

        if stats.recent_streak != 0:
            if stats.recent_streak > 0:
                lines.append(f"  Current streak: {stats.recent_streak} correct in a row")
            else:
                lines.append(f"  Current streak: {abs(stats.recent_streak)} wrong in a row — consider lowering conviction")

        if stats.strongest_context != "unknown":
            lines.append(f"  Strongest context: {stats.strongest_context}")
        if stats.weakest_context != "unknown":
            lines.append(f"  Weakest context: {stats.weakest_context} — be cautious here")

        # Failure pattern warnings
        for pattern in patterns[:2]:  # Max 2 warnings
            lines.append(f"  WARNING: {pattern.description}")

        return "\n".join(lines)

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    @staticmethod
    def _simplify_direction(direction: str) -> str:
        """Simplify direction for accuracy comparison.
        STRONG_BUY/BUY → UP, STRONG_SELL/SELL → DOWN, HOLD → FLAT
        """
        d = direction.upper()
        if d in ("STRONG_BUY", "BUY"):
            return "UP"
        elif d in ("STRONG_SELL", "SELL"):
            return "DOWN"
        return "FLAT"

    @staticmethod
    def _compute_calibration(rows) -> float:
        """Compute calibration score: how well conviction predicts accuracy.

        Buckets predictions by conviction (0-40, 40-60, 60-80, 80-100),
        compares expected accuracy in each bucket vs actual.
        """
        buckets = {
            "low": {"predictions": [], "range": (0, 40)},
            "medium": {"predictions": [], "range": (40, 60)},
            "high": {"predictions": [], "range": (60, 80)},
            "very_high": {"predictions": [], "range": (80, 100)},
        }

        for r in rows:
            conv = r["conviction"]
            correct = r["was_correct"]
            for bucket in buckets.values():
                if bucket["range"][0] <= conv < bucket["range"][1]:
                    bucket["predictions"].append(correct)
                    break
            else:
                # conviction >= 100
                buckets["very_high"]["predictions"].append(correct)

        total_error = 0.0
        buckets_used = 0
        for name, bucket in buckets.items():
            preds = bucket["predictions"]
            if len(preds) >= 3:
                actual_accuracy = sum(preds) / len(preds)
                expected_accuracy = (bucket["range"][0] + bucket["range"][1]) / 200  # midpoint / 100
                total_error += abs(actual_accuracy - expected_accuracy)
                buckets_used += 1

        if buckets_used == 0:
            return 0.0

        avg_error = total_error / buckets_used
        return max(0.0, 1.0 - avg_error)  # 1.0 = perfect calibration

    @staticmethod
    def _compute_streak(recent_rows) -> int:
        """Compute current win/loss streak from most recent predictions."""
        if not recent_rows:
            return 0

        first = recent_rows[0]["was_correct"]
        streak = 0
        for r in recent_rows:
            if r["was_correct"] == first:
                streak += 1
            else:
                break

        return streak if first else -streak

    @staticmethod
    def _analyze_context_performance(rows) -> Tuple[str, str]:
        """Find strongest and weakest context for an agent."""
        context_stats = {}
        for r in rows:
            ctx = r["context"]
            if ctx not in context_stats:
                context_stats[ctx] = {"correct": 0, "total": 0}
            context_stats[ctx]["total"] += 1
            if r["was_correct"]:
                context_stats[ctx]["correct"] += 1

        # Filter to contexts with >= 3 predictions
        valid = {
            k: v["correct"] / v["total"]
            for k, v in context_stats.items()
            if v["total"] >= 3
        }

        if not valid:
            return "unknown", "unknown"

        strongest = max(valid, key=valid.get)
        weakest = min(valid, key=valid.get)
        return strongest, weakest
