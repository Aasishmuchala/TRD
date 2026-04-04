"""Historical FII/DII daily flow data store — SQLite-backed.

Stores real FII/DII net flows by date, replacing the circular proxy
(momentum * 500) with actual NSE data.
"""

import logging
import sqlite3
from datetime import datetime, date
from typing import List, Dict, Optional

from app.config import config

logger = logging.getLogger("gods_eye.fii_dii_store")


class FiiDiiStore:
    """Manages historical FII/DII storage in SQLite.

    Usage:
        store = FiiDiiStore()
        await store.store_daily(date(2024, 4, 1), fii_net_cr=1234.56, dii_net_cr=-500.00)
        data = await store.get_range("2024-04-01", "2024-04-30")  # List of daily dicts
        latest = await store.get_latest()  # Most recent day's data
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        self._init_schema()

    # ---- Schema ----

    def _init_schema(self) -> None:
        """Create fii_dii_daily table if it does not exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fii_dii_daily (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                date          TEXT    NOT NULL UNIQUE,
                fii_net_cr    REAL    NOT NULL DEFAULT 0,
                dii_net_cr    REAL    NOT NULL DEFAULT 0,
                fii_buy_cr    REAL    NOT NULL DEFAULT 0,
                fii_sell_cr   REAL    NOT NULL DEFAULT 0,
                dii_buy_cr    REAL    NOT NULL DEFAULT 0,
                dii_sell_cr   REAL    NOT NULL DEFAULT 0,
                source        TEXT    NOT NULL DEFAULT 'unknown',
                created_at    TEXT    NOT NULL
            )
        """)

        # Index for fast date-range queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fii_dii_date
            ON fii_dii_daily(date)
        """)

        conn.commit()
        conn.close()
        logger.info("FiiDiiStore schema initialised at %s", self.db_path)

    # ---- Public API ----

    def store_daily(
        self,
        date_str: str,
        fii_net_cr: float,
        dii_net_cr: float,
        fii_buy_cr: float = 0.0,
        fii_sell_cr: float = 0.0,
        dii_buy_cr: float = 0.0,
        dii_sell_cr: float = 0.0,
        source: str = "nse_api",
    ) -> None:
        """Store or replace daily FII/DII flow data.

        Args:
            date_str: "YYYY-MM-DD" format
            fii_net_cr: net FII flow in crores (positive = inflow)
            dii_net_cr: net DII flow in crores (positive = inflow)
            fii_buy_cr: FII buy value in crores (optional)
            fii_sell_cr: FII sell value in crores (optional)
            dii_buy_cr: DII buy value in crores (optional)
            dii_sell_cr: DII sell value in crores (optional)
            source: data source identifier (default: "nse_api")
        """
        created_at = datetime.utcnow().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """INSERT OR REPLACE INTO fii_dii_daily
               (date, fii_net_cr, dii_net_cr, fii_buy_cr, fii_sell_cr, dii_buy_cr, dii_sell_cr, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (date_str, fii_net_cr, dii_net_cr, fii_buy_cr, fii_sell_cr, dii_buy_cr, dii_sell_cr, source, created_at),
        )

        conn.commit()
        conn.close()
        logger.debug(
            "Stored FII/DII for %s: FII=%+.2f Cr, DII=%+.2f Cr (source=%s)",
            date_str, fii_net_cr, dii_net_cr, source,
        )

    def get_range(
        self,
        from_date: str,
        to_date: str,
    ) -> List[Dict]:
        """Get FII/DII data for date range.

        Args:
            from_date: "YYYY-MM-DD" (inclusive)
            to_date: "YYYY-MM-DD" (inclusive)

        Returns:
            List of {"date", "fii_net_cr", "dii_net_cr", "fii_buy_cr", ...} sorted by date asc.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """SELECT date, fii_net_cr, dii_net_cr, fii_buy_cr, fii_sell_cr, dii_buy_cr, dii_sell_cr, source
               FROM fii_dii_daily
               WHERE date >= ? AND date <= ?
               ORDER BY date ASC""",
            (from_date, to_date),
        )

        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        logger.debug("Retrieved %d FII/DII records from %s to %s", len(rows), from_date, to_date)
        return rows

    def get_5d_sum(self, date_str: str) -> Dict:
        """Get sum of FII/DII flows for 5-day window ending on given date.

        Args:
            date_str: "YYYY-MM-DD" (center of window)

        Returns:
            {"fii_5d_net": float, "dii_5d_net": float, "days_found": int}
            If less than 5 days of data: returns sum of available days.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get 5 rows ending on or before date_str (most recent 5 trading days)
        cursor.execute(
            """SELECT fii_net_cr, dii_net_cr
               FROM fii_dii_daily
               WHERE date <= ?
               ORDER BY date DESC
               LIMIT 5""",
            (date_str,),
        )

        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        fii_5d = sum(r["fii_net_cr"] for r in rows)
        dii_5d = sum(r["dii_net_cr"] for r in rows)

        result = {
            "fii_5d_net": fii_5d,
            "dii_5d_net": dii_5d,
            "days_found": len(rows),
        }
        logger.debug("5-day sum for %s: FII=%+.2f, DII=%+.2f (days=%d)", date_str, fii_5d, dii_5d, len(rows))
        return result

    def get_latest(self) -> Optional[Dict]:
        """Get the most recent FII/DII data.

        Returns:
            {"date", "fii_net_cr", "dii_net_cr", ...} or None if no data stored.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """SELECT date, fii_net_cr, dii_net_cr, fii_buy_cr, fii_sell_cr, dii_buy_cr, dii_sell_cr, source
               FROM fii_dii_daily
               ORDER BY date DESC
               LIMIT 1"""
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            result = dict(row)
            logger.debug("Latest FII/DII: %s -> FII=%+.2f, DII=%+.2f", result["date"], result["fii_net_cr"], result["dii_net_cr"])
            return result
        return None

    def get_by_date(self, date_str: str) -> Optional[Dict]:
        """Get FII/DII data for a specific date.

        Args:
            date_str: "YYYY-MM-DD"

        Returns:
            {"date", "fii_net_cr", "dii_net_cr", ...} or None if not found.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """SELECT date, fii_net_cr, dii_net_cr, fii_buy_cr, fii_sell_cr, dii_buy_cr, dii_sell_cr, source
               FROM fii_dii_daily
               WHERE date = ?""",
            (date_str,),
        )

        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def count_rows(self) -> int:
        """Return total number of stored FII/DII records."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM fii_dii_daily")
        count = cursor.fetchone()[0]
        conn.close()
        return count


# ---- Helper for QuantSignalEngine ----

def get_fii_dii_for_quant(store: FiiDiiStore, date_str: str) -> Dict:
    """Get FII/DII data ready for QuantInputs.

    Returns dict with fii_net_cr and dii_net_cr from store for given date,
    or zeros if not found.

    Args:
        store: FiiDiiStore instance
        date_str: "YYYY-MM-DD"

    Returns:
        {"fii_net_cr": float, "dii_net_cr": float}
        Falls back to 0.0 if date not in store.
    """
    data = store.get_by_date(date_str)
    if data:
        return {
            "fii_net_cr": data.get("fii_net_cr", 0.0),
            "dii_net_cr": data.get("dii_net_cr", 0.0),
        }
    # No data for this date
    logger.debug("No FII/DII data for %s — using zeros", date_str)
    return {
        "fii_net_cr": 0.0,
        "dii_net_cr": 0.0,
    }


# Global singleton (mirrors historical_store pattern)
fii_dii_store = FiiDiiStore()
