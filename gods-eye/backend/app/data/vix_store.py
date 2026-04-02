"""India VIX historical store — SQLite-backed, Dhan-sourced.

Stores daily VIX OHLC snapshots from Dhan API.
Supports querying by date range for backtesting and analysis.
"""

import logging
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from app.config import config
from app.data.dhan_client import dhan_client

logger = logging.getLogger("gods_eye.vix_store")


class VIXStore:
    """Manages India VIX historical data storage in SQLite.

    Usage:
        store = VIXStore()
        await store.backfill_from_dhan(from_date="2024-01-01", to_date="2024-12-31")
        vix_close = await store.get_close(date="2024-01-15")
        vix_data = await store.get_vix(date="2024-01-15")
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
        """Create vix_daily table if it does not exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vix_daily (
                date TEXT PRIMARY KEY,
                open REAL NOT NULL DEFAULT 0,
                high REAL NOT NULL DEFAULT 0,
                low REAL NOT NULL DEFAULT 0,
                close REAL NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT 'dhan',
                created_at TEXT NOT NULL
            )
        """)

        # Index for fast date range queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_vix_daily_date
            ON vix_daily(date)
        """)

        conn.commit()
        conn.close()
        logger.info("VIXStore schema initialised at %s", self.db_path)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def store_vix(
        self,
        date: str,
        open: float,
        high: float,
        low: float,
        close: float,
        source: str = "dhan",
    ) -> None:
        """Store or replace a VIX snapshot for a given date.

        Args:
            date: "YYYY-MM-DD" format
            open: Opening price
            high: High price
            low: Low price
            close: Closing price
            source: Data source (default: "dhan")
        """
        created_at = datetime.utcnow().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """INSERT OR REPLACE INTO vix_daily
               (date, open, high, low, close, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (date, round(open, 2), round(high, 2), round(low, 2), round(close, 2), source, created_at),
        )

        conn.commit()
        conn.close()
        logger.info("Stored VIX for %s: open=%.2f, high=%.2f, low=%.2f, close=%.2f",
                    date, open, high, low, close)

    def get_vix(self, date: str) -> Optional[Dict]:
        """Retrieve VIX data for a specific date.

        Args:
            date: "YYYY-MM-DD" format

        Returns:
            Dict with keys: date, open, high, low, close, source.
            Or None if not found.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT date, open, high, low, close, source FROM vix_daily WHERE date = ?",
            (date,),
        )
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_close(self, date: str) -> Optional[float]:
        """Retrieve VIX closing price for a specific date.

        Args:
            date: "YYYY-MM-DD" format

        Returns:
            Closing price (float) or None if not found.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT close FROM vix_daily WHERE date = ?",
            (date,),
        )
        row = cursor.fetchone()
        conn.close()

        return row[0] if row else None

    def get_range(self, from_date: str, to_date: str) -> List[Dict]:
        """Retrieve VIX data for a date range (inclusive).

        Args:
            from_date: "YYYY-MM-DD" format (inclusive)
            to_date: "YYYY-MM-DD" format (inclusive)

        Returns:
            List of dicts with keys: date, open, high, low, close, source.
            Sorted by date ascending.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """SELECT date, open, high, low, close, source
               FROM vix_daily
               WHERE date >= ? AND date <= ?
               ORDER BY date ASC""",
            (from_date, to_date),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        return rows

    def get_latest(self) -> Optional[Dict]:
        """Retrieve the most recent VIX snapshot.

        Returns:
            Dict with keys: date, open, high, low, close, source.
            Or None if no data exists.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """SELECT date, open, high, low, close, source
               FROM vix_daily
               ORDER BY date DESC
               LIMIT 1""",
        )
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def count_rows(self) -> int:
        """Return total number of VIX snapshots stored."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM vix_daily")
        count = cursor.fetchone()[0]
        conn.close()

        return count

    # ------------------------------------------------------------------ #
    # Dhan Integration                                                     #
    # ------------------------------------------------------------------ #

    async def backfill_from_dhan(self, from_date: str, to_date: str) -> int:
        """Fetch VIX historical OHLC from Dhan and store it.

        Args:
            from_date: "YYYY-MM-DD" format
            to_date: "YYYY-MM-DD" format

        Returns:
            Count of rows stored.

        Note:
            Dhan's /charts/historical endpoint officially does NOT support
            IDX_I (index) segment for India VIX. This method attempts to fetch
            with security_id="26" (India VIX), exchange_segment="IDX_I",
            but may fail with DhanFetchError if Dhan blocks the request.
            In that case, consider using Yahoo Finance as a fallback source.
        """
        try:
            from app.data.dhan_client import DhanFetchError

            candles = await dhan_client.fetch_historical_candles(
                security_id="26",
                from_date=from_date,
                to_date=to_date,
                exchange_segment="IDX_I",
                instrument="INDEX",
            )
        except Exception as e:
            logger.error("Failed to fetch VIX historical data from Dhan: %s", e)
            return 0

        stored_count = 0
        for candle in candles:
            try:
                self.store_vix(
                    date=candle["date"],
                    open=candle.get("open", 0.0),
                    high=candle.get("high", 0.0),
                    low=candle.get("low", 0.0),
                    close=candle.get("close", 0.0),
                    source="dhan",
                )
                stored_count += 1
            except Exception as e:
                logger.warning("Failed to store candle for date %s: %s", candle.get("date"), e)
                continue

        logger.info("Backfilled %d VIX candles from Dhan (%s to %s)", stored_count, from_date, to_date)
        return stored_count


# Global singleton (mirrors pcr_store pattern)
vix_store = VIXStore()
