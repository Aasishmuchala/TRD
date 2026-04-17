"""Prediction tracking and accuracy evaluation."""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from app.api.schemas import PredictionLog, SimulationResult
from app.config import config


class PredictionTracker:
    """Tracks predictions and evaluates accuracy."""

    def __init__(self, db_path: str = config.DATABASE_PATH):
        """Initialize tracker with SQLite database."""
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id TEXT PRIMARY KEY,
                simulation_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                market_input TEXT NOT NULL,
                predicted_direction TEXT NOT NULL,
                predicted_conviction REAL NOT NULL,
                agents_output TEXT NOT NULL,
                actual_direction TEXT,
                check_timestamp TEXT,
                accuracy INTEGER,
                notes TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS simulations (
                simulation_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                market_input TEXT NOT NULL,
                agents_output TEXT NOT NULL,
                final_direction TEXT NOT NULL,
                final_conviction REAL NOT NULL,
                execution_time_ms REAL NOT NULL,
                model_used TEXT NOT NULL
            )
        """
        )

        conn.commit()
        conn.close()

    def log_simulation(self, result: SimulationResult) -> str:
        """Log a simulation result."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        cursor = conn.cursor()

        # Serialize complex objects
        market_input_json = result.market_input.model_dump_json()
        agents_output_json = json.dumps(
            {k: v.model_dump() for k, v in result.agents_output.items()}
        )

        cursor.execute(
            """
            INSERT INTO simulations
            (simulation_id, timestamp, market_input, agents_output,
             final_direction, final_conviction, execution_time_ms, model_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                result.simulation_id,
                result.timestamp.isoformat(),
                market_input_json,
                agents_output_json,
                result.aggregator_result.final_direction,
                result.aggregator_result.final_conviction,
                result.execution_time_ms,
                result.model_used,
            ),
        )

        conn.commit()
        conn.close()

        return result.simulation_id

    def log_prediction(self, simulation_result: SimulationResult) -> str:
        """Log a prediction for tracking accuracy."""
        prediction_id = f"pred_{simulation_result.simulation_id}"
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        cursor = conn.cursor()

        market_input_json = simulation_result.market_input.model_dump_json()
        agents_output_json = json.dumps(
            {k: v.model_dump() for k, v in simulation_result.agents_output.items()}
        )

        cursor.execute(
            """
            INSERT INTO predictions
            (prediction_id, simulation_id, timestamp, market_input,
             predicted_direction, predicted_conviction, agents_output)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                prediction_id,
                simulation_result.simulation_id,
                simulation_result.timestamp.isoformat(),
                market_input_json,
                simulation_result.aggregator_result.final_direction,
                simulation_result.aggregator_result.final_conviction,
                agents_output_json,
            ),
        )

        conn.commit()
        conn.close()

        return prediction_id

    def record_outcome(
        self,
        prediction_id: str,
        actual_direction: str,
        notes: Optional[str] = None,
    ) -> bool:
        """Record actual market outcome and compute accuracy.

        TRD-L2: Outcomes are recorded manually — there is no automated T+1
        comparison job that fetches next-day NIFTY close and scores predictions.
        Without automation, predictions go unscored, which means FeedbackEngine
        weight tuning has no data to work with. Future: add a scheduled task
        (cron or APScheduler) that runs daily at 15:35 IST to fetch T+1 close
        and call record_outcome for all pending predictions.
        """
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        cursor = conn.cursor()

        # Get prediction
        cursor.execute("SELECT predicted_direction FROM predictions WHERE prediction_id = ?",
                       (prediction_id,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            return False

        predicted_direction = result[0]

        # ARCH-H5: Map directions to families before comparing.
        # Exact match was too strict (STRONG_BUY vs BUY counted as wrong).
        _DIRECTION_FAMILY = {
            "STRONG_BUY": "UP", "BUY": "UP",
            "HOLD": "NEUTRAL",
            "SELL": "DOWN", "STRONG_SELL": "DOWN",
        }
        predicted_family = _DIRECTION_FAMILY.get(predicted_direction, predicted_direction)
        actual_family = _DIRECTION_FAMILY.get(actual_direction, actual_direction)
        # TRD-M3: Binary accuracy — a +0.01% BUY counts the same as a +3% BUY.
        # Future improvement: magnitude-weighted accuracy (e.g. score = move_pct
        # when correct, -move_pct when wrong) would better reward high-conviction
        # correct calls and penalize large misses.
        accuracy = 1 if predicted_family == actual_family else 0

        # Update record
        cursor.execute(
            """
            UPDATE predictions
            SET actual_direction = ?, check_timestamp = ?, accuracy = ?, notes = ?
            WHERE prediction_id = ?
        """,
            (
                actual_direction,
                datetime.now().isoformat(),
                accuracy,
                notes,
                prediction_id,
            ),
        )

        conn.commit()
        conn.close()

        return True

    def get_accuracy_metrics(self, lookback_days: int = 30) -> Dict:
        """Get accuracy metrics for recent predictions."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        cursor = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=lookback_days)).isoformat()

        cursor.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN accuracy = 1 THEN 1 ELSE 0 END) as correct,
                AVG(predicted_conviction) as avg_conviction,
                predicted_direction
            FROM predictions
            WHERE check_timestamp IS NOT NULL AND timestamp > ?
            GROUP BY predicted_direction
        """,
            (cutoff_date,),
        )

        results = cursor.fetchall()
        conn.close()

        metrics = {}
        for row in results:
            total, correct, avg_conviction, direction = row
            if total > 0:
                accuracy_pct = (correct / total) * 100
                metrics[direction] = {
                    "total_predictions": total,
                    "correct": correct,
                    "accuracy_percent": accuracy_pct,
                    "avg_conviction": avg_conviction or 0,
                }

        return metrics

    def get_prediction_history(
        self, limit: int = 100, offset: int = 0
    ) -> List[Dict]:
        """Get paginated prediction history."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                prediction_id, simulation_id, timestamp, predicted_direction,
                predicted_conviction, actual_direction, accuracy
            FROM predictions
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """,
            (limit, offset),
        )

        rows = cursor.fetchall()
        conn.close()

        history = []
        for row in rows:
            history.append(
                {
                    "prediction_id": row[0],
                    "simulation_id": row[1],
                    "timestamp": row[2],
                    "predicted_direction": row[3],
                    "predicted_conviction": row[4],
                    "actual_direction": row[5],
                    "accuracy": row[6],
                }
            )

        return history

    def get_simulation_history(
        self, limit: int = 100, offset: int = 0
    ) -> List[Dict]:
        """Get paginated simulation history with full data."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                simulation_id, timestamp, market_input, agents_output,
                final_direction, final_conviction, execution_time_ms, model_used
            FROM simulations
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """,
            (limit, offset),
        )

        rows = cursor.fetchall()
        conn.close()

        history = []
        for row in rows:
            market_input = None
            agents_output = None
            try:
                market_input = json.loads(row[2]) if row[2] else None
            except (json.JSONDecodeError, TypeError):
                pass
            try:
                agents_output = json.loads(row[3]) if row[3] else None
            except (json.JSONDecodeError, TypeError):
                pass

            history.append(
                {
                    "simulation_id": row[0],
                    "timestamp": row[1],
                    "market_input": market_input,
                    "agents_output": agents_output,
                    "aggregator_result": {
                        "final_direction": row[4],
                        "final_conviction": row[5],
                    },
                    "execution_time_ms": row[6],
                    "model_used": row[7],
                    "feedback_active": False,
                }
            )

        return history
