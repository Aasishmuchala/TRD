"""Historical OHLCV and VIX data store — SQLite-backed, dual-sourced.

Data sourcing strategy:
  - NSE indices (NIFTY, BANKNIFTY, VIX): yfinance via ^NSEI / ^NSEBANK / ^INDIAVIX
    Reason: Dhan's /v2/charts/historical does NOT support IDX_I segment for
    historical candles. Passing security_id=13 with NSE_EQ returns a random
    equity at ~₹6,400 — not NIFTY50. This is a confirmed Dhan API limitation.
  - Equities / F&O: Dhan (existing behaviour, unchanged)

Cache-first: reads from SQLite if today's data exists; fetches from source otherwise.
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

# Instruments sourced from yfinance (Dhan does not support index historical candles)
YFINANCE_TICKERS = {
    "NIFTY":     "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "VIX":       "^INDIAVIX",
}

# How far back to backfill (trading days ≈ 1.4 * calendar days)
BACKFILL_YEARS = 3   # fetch 3 years — ensures RSI/indicator warm-up data for FY24-25 backtests


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
        """Fetch full history and upsert into SQLite.

        Routing:
          - Indices (NIFTY, BANKNIFTY, VIX) → yfinance  (Dhan doesn't support IDX_I)
          - Equities                          → Dhan

        Raises:
            DhanFetchError / RuntimeError: if fetch fails and cache is empty
            ValueError: if instrument is unknown
        """
        if instrument not in INSTRUMENTS and instrument not in YFINANCE_TICKERS:
            raise ValueError(f"Unknown instrument: {instrument!r}. Valid: {list(INSTRUMENTS)}")

        to_date = date.today().isoformat()
        from_date = (date.today() - timedelta(days=BACKFILL_YEARS * 365)).isoformat()

        if instrument in YFINANCE_TICKERS:
            candles = await self._fetch_from_yfinance(instrument, from_date, to_date)
        else:
            security_id = INSTRUMENTS[instrument]
            logger.info(
                "Fetching historical data for %s (secId=%s) from %s to %s via Dhan",
                instrument, security_id, from_date, to_date
            )
            candles = await dhan_client.fetch_historical_candles(security_id, from_date, to_date)

        if not candles:
            raise DhanFetchError(
                f"No candles returned for {instrument} ({from_date} -> {to_date})"
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

    async def _fetch_from_yfinance(self, instrument: str, from_date: str, to_date: str) -> list:
        """Fetch OHLCV from yfinance for index instruments (NIFTY, BANKNIFTY, VIX).

        Dhan's /v2/charts/historical does not support NSE cash index history.
        yfinance provides accurate NSE index data via ^NSEI / ^NSEBANK / ^INDIAVIX.

        Returns:
            List of {"date", "open", "high", "low", "close", "volume"} dicts.
        """
        ticker_sym = YFINANCE_TICKERS[instrument]
        logger.info(
            "Fetching historical data for %s (%s) from %s to %s via yfinance",
            instrument, ticker_sym, from_date, to_date
        )
        try:
            import yfinance as yf
        except ImportError:
            raise RuntimeError(
                "yfinance is required for index historical data. "
                "Add 'yfinance' to requirements.txt."
            )

        # yfinance end date is exclusive — add 1 day to include to_date
        end = (datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        ticker = yf.Ticker(ticker_sym)
        hist = ticker.history(start=from_date, end=end, auto_adjust=True)

        if hist.empty:
            raise DhanFetchError(
                f"yfinance returned no data for {ticker_sym} ({from_date} → {to_date}). "
                "Possible rate-limit — try again in a few minutes."
            )

        candles = []
        for ts, row in hist.iterrows():
            candles.append({
                "date": ts.date().isoformat(),
                "open":   round(float(row["Open"]),  2),
                "high":   round(float(row["High"]),  2),
                "low":    round(float(row["Low"]),   2),
                "close":  round(float(row["Close"]), 2),
                "volume": int(row.get("Volume", 0)),
            })
        return candles

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
            except Exception:
                logger.warning("VIX historical fetch failed — returning cached/empty data")

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
