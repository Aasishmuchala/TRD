"""PCR (Put-Call Ratio) historical store — SQLite-backed, Dhan-sourced.

Stores daily PCR snapshots collected from live option chain data.
Supports querying by date range for backtesting and analysis.
"""

import logging
import sqlite3
from datetime import datetime, date
from typing import Dict, List, Optional

from app.config import config

logger = logging.getLogger("gods_eye.pcr_store")


class PCRStore:
    """Manages PCR historical data storage in SQLite.

    Usage:
        store = PCRStore()
        await store.store_pcr(date="2024-01-15", pcr=1.05, ...)
        pcr_val = await store.get_pcr(date="2024-01-15")
        rows = await store.get_range(from_date="2023-01-01", to_date="2024-01-15")
        latest = await store.get_latest()
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        self._init_schema()

    # ------------------------------------------------------------------ #
    # Schema                                                               #
    # ------------------------------------------------------------------ #

    def _init_schema(self) -> None:
        """Create pcr_daily table if it does not exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pcr_daily (
                date TEXT PRIMARY KEY,
                pcr REAL NOT NULL,
                total_call_oi INTEGER NOT NULL DEFAULT 0,
                total_put_oi INTEGER NOT NULL DEFAULT 0,
                max_pain REAL NOT NULL DEFAULT 0,
                nifty_close REAL NOT NULL DEFAULT 0,
                expiry_date TEXT,
                source TEXT NOT NULL DEFAULT 'dhan',
                created_at TEXT NOT NULL
            )
        """)

        # Index for fast date range queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pcr_daily_date
            ON pcr_daily(date)
        """)

        conn.commit()
        conn.close()
        logger.info("PCRStore schema initialised at %s", self.db_path)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def store_pcr(
        self,
        date: str,
        pcr: float,
        total_call_oi: int = 0,
        total_put_oi: int = 0,
        max_pain: float = 0.0,
        nifty_close: float = 0.0,
        expiry_date: Optional[str] = None,
        source: str = "dhan",
    ) -> None:
        """Store or replace a PCR snapshot for a given date.

        Args:
            date: "YYYY-MM-DD" format
            pcr: Put-Call Ratio (e.g., 1.05)
            total_call_oi: Total Call Open Interest
            total_put_oi: Total Put Open Interest
            max_pain: Max Pain strike
            nifty_close: Nifty 50 closing price for the day
            expiry_date: Expiry date used for this snapshot (e.g., "2024-01-25")
            source: Data source (default: "dhan")
        """
        created_at = datetime.utcnow().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """INSERT OR REPLACE INTO pcr_daily
               (date, pcr, total_call_oi, total_put_oi, max_pain, nifty_close, expiry_date, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (date, round(pcr, 3), total_call_oi, total_put_oi, round(max_pain, 2), round(nifty_close, 2), expiry_date, source, created_at),
        )

        conn.commit()
        conn.close()
        logger.info("Stored PCR for %s: pcr=%.3f, call_oi=%d, put_oi=%d, max_pain=%.2f",
                    date, pcr, total_call_oi, total_put_oi, max_pain)

    def get_pcr(self, date: str) -> Optional[float]:
        """Retrieve PCR value for a specific date.

        Args:
            date: "YYYY-MM-DD" format

        Returns:
            PCR value (float) or None if not found.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT pcr FROM pcr_daily WHERE date = ?",
            (date,),
        )
        row = cursor.fetchone()
        conn.close()

        return row[0] if row else None

    def get_range(self, from_date: str, to_date: str) -> List[Dict]:
        """Retrieve PCR data for a date range (inclusive).

        Args:
            from_date: "YYYY-MM-DD" format (inclusive)
            to_date: "YYYY-MM-DD" format (inclusive)

        Returns:
            List of dicts with keys: date, pcr, total_call_oi, total_put_oi, max_pain, nifty_close, expiry_date, source.
            Sorted by date ascending.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """SELECT date, pcr, total_call_oi, total_put_oi, max_pain, nifty_close, expiry_date, source
               FROM pcr_daily
               WHERE date >= ? AND date <= ?
               ORDER BY date ASC""",
            (from_date, to_date),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        return rows

    def get_latest(self) -> Optional[Dict]:
        """Retrieve the most recent PCR snapshot.

        Returns:
            Dict with keys: date, pcr, total_call_oi, total_put_oi, max_pain, nifty_close, expiry_date, source.
            Or None if no data exists.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """SELECT date, pcr, total_call_oi, total_put_oi, max_pain, nifty_close, expiry_date, source
               FROM pcr_daily
               ORDER BY date DESC
               LIMIT 1""",
        )
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def count_rows(self) -> int:
        """Return total number of PCR snapshots stored."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM pcr_daily")
        count = cursor.fetchone()[0]
        conn.close()

        return count


# Global singleton (mirrors historical_store pattern)
pcr_store = PCRStore()
