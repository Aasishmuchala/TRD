"""FII/DII Collection background task — fetches daily flow data from NSE.

Runs post-market (after 18:00 IST) to store daily FII/DII net flows.
Also does a mid-day check during market hours for intraday updates.
Uses the same lifecycle pattern as pcr_collector.
"""

import asyncio
import logging
from datetime import datetime, time, timezone, timedelta
from typing import Optional

from app.data.nse_fii_dii import fetch_fii_dii_activity
from app.data.fii_dii_store import fii_dii_store

logger = logging.getLogger("gods_eye.fii_dii_collector")

# IST timezone offset: UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))

# Post-market window (IST) — NSE publishes provisional FII/DII data ~18:00
POST_MARKET_START = time(17, 30)
POST_MARKET_END = time(20, 0)

# Check interval
COLLECTION_INTERVAL_SECONDS = 1800  # Every 30 minutes


def _get_ist_time() -> datetime:
    """Get current time in IST."""
    return datetime.now(IST)


def _is_collection_window() -> bool:
    """Return True if current time is in the post-market collection window."""
    now = _get_ist_time()
    current_time = now.time()

    # Skip weekends
    if now.weekday() >= 5:
        return False

    return POST_MARKET_START <= current_time <= POST_MARKET_END


class FiiDiiCollector:
    """Manages daily FII/DII flow collection from NSE."""

    def __init__(self):
        self._collection_task: Optional[asyncio.Task] = None
        self._last_stored_date: Optional[str] = None

    async def _collection_loop(self):
        """Background loop that collects FII/DII data post-market.

        - Every 30 minutes during post-market window (17:30-20:00 IST)
        - Stores one snapshot per day (deduped by date)
        """
        while True:
            try:
                if not _is_collection_window():
                    # Not collection window — wait 5 minutes before checking again
                    await asyncio.sleep(300)
                    continue

                today = _get_ist_time().strftime("%Y-%m-%d")

                # Skip if we already stored today's data
                if today == self._last_stored_date:
                    await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)
                    continue

                # Fetch from NSE
                activity = await fetch_fii_dii_activity()

                if activity and not activity.get("error"):
                    fii_net = activity.get("fii_net_value", 0.0)
                    dii_net = activity.get("dii_net_value", 0.0)

                    # Only store if we got real data (not both zero)
                    if fii_net != 0 or dii_net != 0:
                        fii_dii_store.store_daily(
                            date_str=today,
                            fii_net_cr=fii_net,
                            dii_net_cr=dii_net,
                            fii_buy_cr=activity.get("fii_buy_value", 0.0),
                            fii_sell_cr=activity.get("fii_sell_value", 0.0),
                            dii_buy_cr=activity.get("dii_buy_value", 0.0),
                            dii_sell_cr=activity.get("dii_sell_value", 0.0),
                            source="nse_api",
                        )
                        self._last_stored_date = today
                        logger.info(
                            "Stored FII/DII for %s: FII=%+.0f Cr, DII=%+.0f Cr",
                            today, fii_net, dii_net,
                        )
                    else:
                        logger.debug("FII/DII both zero for %s — skipping store", today)
                else:
                    error_msg = activity.get("error", "unknown error") if activity else "no response"
                    logger.warning("FII/DII fetch failed: %s", error_msg)

                # Wait before next collection attempt
                await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)

            except asyncio.CancelledError:
                logger.info("FII/DII collection loop cancelled")
                break
            except Exception as e:
                logger.error("FII/DII collection loop error: %s", e)
                await asyncio.sleep(300)

    def start(self):
        """Start the FII/DII collection background task."""
        if self._collection_task is None or self._collection_task.done():
            self._collection_task = asyncio.create_task(self._collection_loop())
            logger.info("FII/DII collector started (collects post-market: 17:30-20:00 IST)")

    def stop(self):
        """Stop the FII/DII collection background task."""
        if self._collection_task and not self._collection_task.done():
            self._collection_task.cancel()
            logger.info("FII/DII collector stopped")

    async def shutdown(self):
        """Clean up resources."""
        self.stop()

    async def fetch_and_store_now(self) -> bool:
        """Force an immediate fetch and store (for manual triggering).

        Returns True if data was stored, False otherwise.
        """
        today = _get_ist_time().strftime("%Y-%m-%d")
        activity = await fetch_fii_dii_activity()

        if activity and not activity.get("error"):
            fii_net = activity.get("fii_net_value", 0.0)
            dii_net = activity.get("dii_net_value", 0.0)

            if fii_net != 0 or dii_net != 0:
                fii_dii_store.store_daily(
                    date_str=today,
                    fii_net_cr=fii_net,
                    dii_net_cr=dii_net,
                    fii_buy_cr=activity.get("fii_buy_value", 0.0),
                    fii_sell_cr=activity.get("fii_sell_value", 0.0),
                    dii_buy_cr=activity.get("dii_buy_value", 0.0),
                    dii_sell_cr=activity.get("dii_sell_value", 0.0),
                    source="nse_api",
                )
                self._last_stored_date = today
                logger.info("Force-stored FII/DII for %s", today)
                return True

        return False


# Global singleton (mirrors pcr_collector pattern)
fii_dii_collector = FiiDiiCollector()
