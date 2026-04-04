"""Data freshness circuit breaker — warns when market data is stale.

Checks all data sources (PCR, FII/DII, VIX, live market) and returns
warnings when any critical data is too old for reliable simulation.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List

from app.data.pcr_store import pcr_store
from app.data.fii_dii_store import fii_dii_store
from app.data.vix_store import vix_store

logger = logging.getLogger("gods_eye.freshness")

# IST timezone offset
IST = timezone(timedelta(hours=5, minutes=30))

# Staleness thresholds (in hours)
STALE_THRESHOLDS = {
    "pcr": 24,        # PCR should be updated daily during market hours
    "fii_dii": 36,    # FII/DII published post-market, allow 1.5 days
    "vix": 24,        # VIX should be current day's data
    "live_market": 1,  # Live data should be within 1 hour during market hours
}


def _hours_since(date_str: str) -> float:
    """Compute hours elapsed since a date string (YYYY-MM-DD or ISO format)."""
    try:
        if "T" in date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=IST)
        now = datetime.now(IST)
        delta = now - dt.astimezone(IST)
        return delta.total_seconds() / 3600
    except Exception:
        return float("inf")


def check_data_freshness(live_timestamp: str = None) -> Dict:
    """Check all data sources for staleness.

    Returns:
        {
            "warnings": ["PCR data >24hr old", ...],
            "sources": {
                "pcr": {"latest_date": "2026-03-31", "hours_old": 12.5, "stale": False},
                "fii_dii": {...},
                "vix": {...},
            },
            "any_stale": True/False,
        }
    """
    warnings: List[str] = []
    sources: Dict[str, Dict] = {}

    # Check PCR freshness
    try:
        latest_pcr = pcr_store.get_latest()
        if latest_pcr:
            hours = _hours_since(latest_pcr["date"])
            stale = hours > STALE_THRESHOLDS["pcr"]
            sources["pcr"] = {
                "latest_date": latest_pcr["date"],
                "hours_old": round(hours, 1),
                "stale": stale,
                "value": latest_pcr.get("pcr"),
            }
            if stale:
                warnings.append(f"PCR data is {hours:.0f}hr old (last: {latest_pcr['date']})")
        else:
            sources["pcr"] = {"latest_date": None, "hours_old": None, "stale": True}
            warnings.append("No PCR data stored — run simulation during market hours to collect")
    except Exception as e:
        sources["pcr"] = {"error": str(e), "stale": True}
        warnings.append(f"PCR store error: {e}")

    # Check FII/DII freshness
    try:
        latest_fii = fii_dii_store.get_latest()
        if latest_fii:
            hours = _hours_since(latest_fii["date"])
            stale = hours > STALE_THRESHOLDS["fii_dii"]
            sources["fii_dii"] = {
                "latest_date": latest_fii["date"],
                "hours_old": round(hours, 1),
                "stale": stale,
                "fii_net": latest_fii.get("fii_net_cr"),
                "dii_net": latest_fii.get("dii_net_cr"),
            }
            if stale:
                warnings.append(f"FII/DII data is {hours:.0f}hr old (last: {latest_fii['date']})")
        else:
            sources["fii_dii"] = {"latest_date": None, "hours_old": None, "stale": True}
            warnings.append("No FII/DII data stored — data will be fetched post-market")
    except Exception as e:
        sources["fii_dii"] = {"error": str(e), "stale": True}
        warnings.append(f"FII/DII store error: {e}")

    # Check VIX freshness
    try:
        latest_vix = vix_store.get_latest()
        if latest_vix:
            hours = _hours_since(latest_vix["date"])
            stale = hours > STALE_THRESHOLDS["vix"]
            sources["vix"] = {
                "latest_date": latest_vix["date"],
                "hours_old": round(hours, 1),
                "stale": stale,
                "close": latest_vix.get("close"),
            }
            if stale:
                warnings.append(f"VIX historical data is {hours:.0f}hr old (last: {latest_vix['date']})")
        else:
            sources["vix"] = {"latest_date": None, "hours_old": None, "stale": True}
            warnings.append("No VIX historical data stored — live VIX will be fetched from Dhan")
    except Exception as e:
        sources["vix"] = {"error": str(e), "stale": True}
        warnings.append(f"VIX store error: {e}")

    # Check live market timestamp
    if live_timestamp:
        hours = _hours_since(live_timestamp)
        stale = hours > STALE_THRESHOLDS["live_market"]
        sources["live_market"] = {
            "latest_timestamp": live_timestamp,
            "hours_old": round(hours, 1),
            "stale": stale,
        }
        if stale:
            warnings.append(f"Live market data is {hours:.1f}hr old — Dhan API may be down")
    else:
        sources["live_market"] = {"latest_timestamp": None, "stale": False}

    return {
        "warnings": warnings,
        "sources": sources,
        "any_stale": any(s.get("stale", False) for s in sources.values()),
    }
