"""PCR Collection background task — collects live option chain data during market hours.

Runs during IST market hours (9:15-15:30) and stores daily PCR snapshots.
Uses the same pattern as dhan_token_manager for lifecycle management.
"""

import asyncio
import logging
from datetime import datetime, time, timezone, timedelta
from typing import Optional

from app.data.dhan_client import dhan_client
from app.data.pcr_store import pcr_store

logger = logging.getLogger("gods_eye.pcr_collector")

# IST timezone offset: UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))

# Market hours (IST)
MARKET_OPEN = time(9, 15)   # 9:15 AM IST
MARKET_CLOSE = time(15, 30)  # 3:30 PM IST
EOD_SNAPSHOT_TIME = time(15, 25)  # 3:25 PM IST (5 min before close)

# Collection frequency during market hours
COLLECTION_INTERVAL_SECONDS = 300  # Every 5 minutes


def _get_ist_time() -> datetime:
    """Get current time in IST."""
    return datetime.now(IST)


def _is_market_hours() -> bool:
    """Return True if current time is within market hours (IST)."""
    now = _get_ist_time()
    current_time = now.time()

    # Market is closed on weekends (5 = Saturday, 6 = Sunday)
    if now.weekday() >= 5:
        return False

    # Check if within market hours
    return MARKET_OPEN <= current_time <= MARKET_CLOSE


def _should_collect_eod_snapshot() -> bool:
    """Return True if it's time for end-of-day snapshot (3:25 PM IST)."""
    now = _get_ist_time()
    current_time = now.time()

    # Check if we're within 5 minutes of EOD snapshot time
    # (in case collection runs at slightly different times)
    if now.weekday() >= 5:
        return False

    # Snapshot if within [15:20, 15:30]
    return time(15, 20) <= current_time <= time(15, 30)


class PCRCollector:
    """Manages live PCR collection from Dhan option chain during market hours."""

    def __init__(self):
        self._collection_task: Optional[asyncio.Task] = None
        self._last_eod_snapshot_date: Optional[str] = None

    async def _collection_loop(self):
        """Background loop that collects PCR during market hours.

        - Every 5 minutes during market hours: fetch options summary and log it
        - At 3:25 PM IST: store end-of-day snapshot in pcr_store
        """
        while True:
            try:
                if not _is_market_hours():
                    # Not market hours — wait 60 seconds before checking again
                    await asyncio.sleep(60)
                    continue

                # Fetch live option chain summary
                summary = await dhan_client.fetch_options_summary()

                if summary:
                    pcr = summary.get("pcr", 1.0)
                    call_oi = summary.get("total_call_oi", 0)
                    put_oi = summary.get("total_put_oi", 0)
                    max_pain = summary.get("max_pain", 0.0)

                    logger.info(
                        "PCR live: %.3f (call_oi=%d, put_oi=%d, max_pain=%.0f)",
                        pcr, call_oi, put_oi, max_pain
                    )

                    # Check if it's time for end-of-day snapshot
                    if _should_collect_eod_snapshot():
                        today = _get_ist_time().strftime("%Y-%m-%d")

                        # Avoid storing multiple snapshots for the same day
                        if today != self._last_eod_snapshot_date:
                            # Fetch Nifty close via dhan_client (for context)
                            nifty_data = await dhan_client.fetch_nifty50()
                            nifty_close = nifty_data.get("last", 0.0) if nifty_data else 0.0

                            # Store end-of-day snapshot
                            pcr_store.store_pcr(
                                date=today,
                                pcr=pcr,
                                total_call_oi=call_oi,
                                total_put_oi=put_oi,
                                max_pain=max_pain,
                                nifty_close=nifty_close,
                                expiry_date=None,  # Could extract from chain if needed
                                source="dhan",
                            )
                            self._last_eod_snapshot_date = today
                else:
                    logger.warning("Failed to fetch options summary from Dhan")

                # Wait before next collection
                await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)

            except asyncio.CancelledError:
                logger.info("PCR collection loop cancelled")
                break
            except Exception as e:
                logger.error("PCR collection loop error: %s", e)
                # Wait 5 minutes before retrying on error
                await asyncio.sleep(300)

    def start(self):
        """Start the PCR collection background task."""
        if self._collection_task is None or self._collection_task.done():
            self._collection_task = asyncio.create_task(self._collection_loop())
            logger.info("PCR collector started (collects during market hours: 9:15-15:30 IST)")

    def stop(self):
        """Stop the PCR collection background task."""
        if self._collection_task and not self._collection_task.done():
            self._collection_task.cancel()
            logger.info("PCR collector stopped")

    async def shutdown(self):
        """Clean up resources."""
        self.stop()


# Global singleton (mirrors dhan_token_manager pattern)
pcr_collector = PCRCollector()
