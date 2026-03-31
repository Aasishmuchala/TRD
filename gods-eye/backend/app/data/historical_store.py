"""Historical OHLCV and VIX data store — SQLite-backed, Dhan-sourced.

Cache-first: reads from SQLite if today's data exists; fetches from Dhan otherwise.
Dhan failure raises DhanFetchError — no silent fallback to mock data.
"""

import asyncio
import logging
import sqlite3
import time
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional

from app.config import config
from app.data.dhan_client import dhan_client, DhanFetchError

logger = logging.getLogger("gods_eye.historical")

# Instruments supported by this store
INSTRUMENTS = {
    "NIFTY": "13",
    "BANKNIFTY": "25",
    "VIX": "26",
}

# How far back to backfill (trading days ≈ 1.4 * calendar days)
BACKFILL_YEARS = 2   # fetch 2 years to guarantee 252+ trading days


class HistoricalStore:
    """Manages historical price storage in SQLite.

    Usage:
        store = HistoricalStore()
        rows = await store.get_ohlcv("NIFTY")    # 252+ OHLCV dicts
        vix  = await store.get_vix_closes()       # 252+ VIX close dicts
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        self._init_schema()

    # ------------------------------------------------------------------ #
    # Schema                                                               #
    # ------------------------------------------------------------------ #

    def _init_schema(self) -> None:
        """Create tables if they do not exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_prices (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument TEXT    NOT NULL,
                date       TEXT    NOT NULL,
                open       REAL    NOT NULL,
                high       REAL    NOT NULL,
                low        REAL    NOT NULL,
                close      REAL    NOT NULL,
                volume     INTEGER NOT NULL DEFAULT 0,
                fetched_at TEXT    NOT NULL,
                UNIQUE(instrument, date)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_vix (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                date       TEXT    NOT NULL UNIQUE,
                close      REAL    NOT NULL,
                fetched_at TEXT    NOT NULL
            )
        """)

        # Indexes for fast date-range queries used by Phase 6+
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_hp_instrument_date
            ON historical_prices(instrument, date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_hvix_date
            ON historical_vix(date)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS oi_snapshots (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument    TEXT    NOT NULL,
                date          TEXT    NOT NULL,
                call_oi       INTEGER NOT NULL DEFAULT 0,
                put_oi        INTEGER NOT NULL DEFAULT 0,
                pcr           REAL    NOT NULL DEFAULT 0.0,
                net_sentiment TEXT    NOT NULL DEFAULT 'neutral',
                fetched_at    TEXT    NOT NULL,
                UNIQUE(instrument, date)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_oi_instrument_date
            ON oi_snapshots(instrument, date)
        """)

        conn.commit()
        conn.close()
        logger.info("HistoricalStore schema initialised at %s", self.db_path)

    # ------------------------------------------------------------------ #
    # Cache-check helpers                                                  #
    # ------------------------------------------------------------------ #

    def _is_cache_fresh(self, instrument: str) -> bool:
        """Return True if data for today already exists in SQLite.

        'Fresh' means we have at least one row fetched today.
        This prevents re-fetching from Dhan within the same trading day.
        """
        today = date.today().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        if instrument == "VIX":
            cursor.execute(
                "SELECT 1 FROM historical_vix WHERE fetched_at >= ? LIMIT 1",
                (today,)
            )
        else:
            cursor.execute(
                "SELECT 1 FROM historical_prices WHERE instrument = ? AND fetched_at >= ? LIMIT 1",
                (instrument, today)
            )
        row = cursor.fetchone()
        conn.close()
        return row is not None

    def _count_rows(self, instrument: str) -> int:
        """Return number of stored rows for this instrument."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        if instrument == "VIX":
            cursor.execute("SELECT COUNT(*) FROM historical_vix")
        else:
            cursor.execute(
                "SELECT COUNT(*) FROM historical_prices WHERE instrument = ?",
                (instrument,)
            )
        count = cursor.fetchone()[0]
        conn.close()
        return count

    # ------------------------------------------------------------------ #
    # Dhan fetch + upsert                                                  #
    # ------------------------------------------------------------------ #

    async def _fetch_and_store(self, instrument: str) -> None:
        """Fetch full history from Dhan and upsert into SQLite.

        Args:
            instrument: "NIFTY", "BANKNIFTY", or "VIX"

        Raises:
            DhanFetchError: propagated from dhan_client.fetch_historical_candles
            ValueError: if instrument is unknown
        """
        security_id = INSTRUMENTS.get(instrument)
        if not security_id:
            raise ValueError(f"Unknown instrument: {instrument!r}. Valid: {list(INSTRUMENTS)}")

        to_date = date.today().isoformat()
        from_date = (date.today() - timedelta(days=BACKFILL_YEARS * 365)).isoformat()

        logger.info(
            "Fetching historical data for %s (secId=%s) from %s to %s",
            instrument, security_id, from_date, to_date
        )

        # Rate-limit: 1 req/sec between instrument fetches (caller spaces them)
        candles = await dhan_client.fetch_historical_candles(security_id, from_date, to_date)

        if not candles:
            raise DhanFetchError(
                f"Dhan returned zero candles for {instrument} ({from_date} -> {to_date})"
            )

        fetched_at = datetime.utcnow().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if instrument == "VIX":
            cursor.executemany(
                """INSERT OR REPLACE INTO historical_vix (date, close, fetched_at)
                   VALUES (:date, :close, :fetched_at)""",
                [{"date": c["date"], "close": c["close"], "fetched_at": fetched_at}
                 for c in candles]
            )
        else:
            cursor.executemany(
                """INSERT OR REPLACE INTO historical_prices
                   (instrument, date, open, high, low, close, volume, fetched_at)
                   VALUES (:instrument, :date, :open, :high, :low, :close, :volume, :fetched_at)""",
                [{**c, "instrument": instrument, "fetched_at": fetched_at} for c in candles]
            )

        conn.commit()
        conn.close()
        logger.info("Stored %d candles for %s", len(candles), instrument)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def get_ohlcv(
        self,
        instrument: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> List[Dict]:
        """Return daily OHLCV rows for instrument, fetching from Dhan if needed.

        Args:
            instrument: "NIFTY" or "BANKNIFTY"
            from_date: optional "YYYY-MM-DD" filter (inclusive)
            to_date: optional "YYYY-MM-DD" filter (inclusive)

        Returns:
            List of {"date", "open", "high", "low", "close", "volume"} sorted by date asc.

        Raises:
            DhanFetchError: if Dhan API fails and cache is empty
        """
        if instrument not in ("NIFTY", "BANKNIFTY"):
            raise ValueError(f"get_ohlcv only supports NIFTY/BANKNIFTY, got {instrument!r}")

        # Fetch from Dhan if cache is stale or empty
        if not self._is_cache_fresh(instrument):
            await self._fetch_and_store(instrument)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT date, open, high, low, close, volume FROM historical_prices WHERE instrument = ?"
        params: list = [instrument]
        if from_date:
            query += " AND date >= ?"
            params.append(from_date)
        if to_date:
            query += " AND date <= ?"
            params.append(to_date)
        query += " ORDER BY date ASC"

        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    async def get_vix_closes(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> List[Dict]:
        """Return daily VIX close values, fetching from Dhan if needed.

        Returns:
            List of {"date", "close"} sorted by date asc.

        Raises:
            DhanFetchError: if Dhan API fails and cache is empty
        """
        if not self._is_cache_fresh("VIX"):
            try:
                await self._fetch_and_store("VIX")
            except DhanFetchError:
                logger.warning("VIX historical not available on Dhan — returning cached/empty data")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT date, close FROM historical_vix"
        params: list = []
        if from_date:
            query += " WHERE date >= ?"
            params.append(from_date)
        if to_date:
            op = "AND" if from_date else "WHERE"
            query += f" {op} date <= ?"
            params.append(to_date)
        query += " ORDER BY date ASC"

        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    async def backfill_all(self) -> Dict[str, int]:
        """Trigger a full backfill for all instruments sequentially.

        Rate-limits to 1 request/second between instruments.
        VIX is non-fatal — Dhan doesn't support historical VIX charts.
        Returns dict of {instrument: row_count_stored}.

        Raises:
            DhanFetchError: if NIFTY or BANKNIFTY fails.
        """
        results = {}
        for instrument in ["NIFTY", "BANKNIFTY"]:
            await self._fetch_and_store(instrument)
            results[instrument] = self._count_rows(instrument)
            await asyncio.sleep(1.0)

        # VIX historical not available on Dhan — skip gracefully
        try:
            await self._fetch_and_store("VIX")
            results["VIX"] = self._count_rows("VIX")
        except DhanFetchError:
            logger.warning("VIX historical data not available on Dhan — skipping (backtest will use default VIX regime)")
            results["VIX"] = self._count_rows("VIX")

        return results

    def store_oi_snapshot(
        self,
        instrument: str,
        date_str: str,
        call_oi: int,
        put_oi: int,
        pcr: float,
    ) -> None:
        """Store or replace an OI snapshot for instrument + date.

        net_sentiment derived from PCR:
          pcr > 1.2  -> "bullish"  (put-heavy = bearish hedging = contrarian bullish signal)
          pcr < 0.8  -> "bearish"  (call-heavy = speculative buying = contrarian bearish signal)
          otherwise  -> "neutral"
        """
        if pcr > 1.2:
            net_sentiment = "bullish"
        elif pcr < 0.8:
            net_sentiment = "bearish"
        else:
            net_sentiment = "neutral"

        fetched_at = datetime.utcnow().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO oi_snapshots
               (instrument, date, call_oi, put_oi, pcr, net_sentiment, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (instrument, date_str, call_oi, put_oi, round(pcr, 3), net_sentiment, fetched_at),
        )
        conn.commit()
        conn.close()
        logger.info("Stored OI snapshot for %s on %s (PCR=%.3f)", instrument, date_str, pcr)

    def get_oi_snapshot(self, instrument: str, date_str: str) -> Optional[Dict]:
        """Return OI snapshot for instrument + date, or None if not stored.

        Returns: {"instrument", "date", "call_oi", "put_oi", "pcr", "net_sentiment"} or None.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """SELECT instrument, date, call_oi, put_oi, pcr, net_sentiment
               FROM oi_snapshots WHERE instrument = ? AND date = ?""",
            (instrument, date_str),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None


# Global singleton (mirrors dhan_client pattern)
historical_store = HistoricalStore()
