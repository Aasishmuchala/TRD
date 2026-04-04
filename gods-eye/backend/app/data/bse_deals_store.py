"""BSE Bulk/Block Deals store — SQLite-backed storage for insider deal activity.

BSE publishes daily bulk/block deals that reveal institutional and promoter
activity. The Promoter agent uses this data to detect insider sentiment.

Table: bse_deals
  date TEXT, security TEXT, client_name TEXT, deal_type TEXT (BULK/BLOCK),
  buy_sell TEXT (BUY/SELL), quantity INTEGER, price REAL, source TEXT, created_at TEXT
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.config import config

logger = logging.getLogger("gods_eye.bse_deals")


class BseDealsStore:
    """SQLite-backed store for BSE bulk/block deal data."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        self._init_table()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_table(self):
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS bse_deals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    security TEXT NOT NULL,
                    client_name TEXT NOT NULL,
                    deal_type TEXT NOT NULL,
                    buy_sell TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    source TEXT DEFAULT 'bse',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_bse_deals_date
                    ON bse_deals(date DESC);
                CREATE INDEX IF NOT EXISTS idx_bse_deals_security
                    ON bse_deals(security, date DESC);
                CREATE INDEX IF NOT EXISTS idx_bse_deals_client
                    ON bse_deals(client_name, date DESC);
            """)
            conn.commit()
        finally:
            conn.close()
        logger.info("BseDealsStore table initialised")

    def store_deal(
        self,
        date: str,
        security: str,
        client_name: str,
        deal_type: str,
        buy_sell: str,
        quantity: int,
        price: float,
        source: str = "bse",
    ) -> bool:
        """Store a single deal. Returns True if inserted, False if duplicate."""
        conn = self._get_conn()
        try:
            # Check for duplicate
            existing = conn.execute(
                """SELECT id FROM bse_deals
                   WHERE date = ? AND security = ? AND client_name = ?
                   AND deal_type = ? AND buy_sell = ? AND quantity = ?""",
                (date, security, client_name, deal_type, buy_sell, quantity),
            ).fetchone()
            if existing:
                return False

            conn.execute(
                """INSERT INTO bse_deals
                   (date, security, client_name, deal_type, buy_sell, quantity, price, source, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (date, security, client_name, deal_type, buy_sell, quantity, price, source,
                 datetime.now().isoformat()),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def store_deals_batch(self, deals: List[Dict]) -> int:
        """Store multiple deals at once. Returns count of new deals inserted."""
        inserted = 0
        for deal in deals:
            if self.store_deal(**deal):
                inserted += 1
        return inserted

    def get_recent_deals(self, days: int = 5, limit: int = 50) -> List[Dict]:
        """Get recent bulk/block deals across all securities."""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT date, security, client_name, deal_type, buy_sell, quantity, price
                   FROM bse_deals
                   WHERE date >= ?
                   ORDER BY date DESC, quantity DESC
                   LIMIT ?""",
                (cutoff, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_deals_for_security(self, security: str, days: int = 30) -> List[Dict]:
        """Get deals for a specific security."""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT date, client_name, deal_type, buy_sell, quantity, price
                   FROM bse_deals
                   WHERE security = ? AND date >= ?
                   ORDER BY date DESC""",
                (security, cutoff),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_large_promoter_deals(self, days: int = 7, min_quantity: int = 100000) -> List[Dict]:
        """Get large deals likely from promoters/insiders (high quantity)."""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT date, security, client_name, deal_type, buy_sell, quantity, price
                   FROM bse_deals
                   WHERE date >= ? AND quantity >= ?
                   ORDER BY quantity DESC
                   LIMIT 20""",
                (cutoff, min_quantity),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_net_sentiment(self, days: int = 5) -> Dict:
        """Compute net buy/sell sentiment from recent deals.

        Returns: {"net_buy_count": int, "net_sell_count": int,
                  "net_buy_value": float, "net_sell_value": float, "sentiment": str}
        """
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT buy_sell, quantity, price FROM bse_deals WHERE date >= ?""",
                (cutoff,),
            ).fetchall()

            buy_count = sum(1 for r in rows if r["buy_sell"] == "BUY")
            sell_count = sum(1 for r in rows if r["buy_sell"] == "SELL")
            buy_value = sum(r["quantity"] * r["price"] for r in rows if r["buy_sell"] == "BUY")
            sell_value = sum(r["quantity"] * r["price"] for r in rows if r["buy_sell"] == "SELL")

            if buy_value > sell_value * 1.3:
                sentiment = "BULLISH"
            elif sell_value > buy_value * 1.3:
                sentiment = "BEARISH"
            else:
                sentiment = "NEUTRAL"

            return {
                "net_buy_count": buy_count,
                "net_sell_count": sell_count,
                "net_buy_value_cr": round(buy_value / 1e7, 2),  # Convert to crores
                "net_sell_value_cr": round(sell_value / 1e7, 2),
                "sentiment": sentiment,
                "total_deals": len(rows),
            }
        finally:
            conn.close()

    def count_rows(self) -> int:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM bse_deals").fetchone()
            return row["cnt"]
        finally:
            conn.close()


# Global singleton
bse_deals_store = BseDealsStore()
