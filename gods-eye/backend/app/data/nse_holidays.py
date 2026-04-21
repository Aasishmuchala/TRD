"""NSE trading holidays — fetch with hardcoded fallback.

Primary source: NSE's public ``holiday-master`` endpoint (the same JSON that
powers nseindia.com/resources/exchange-communication-holidays). It is
rate-limited and often blocked from cloud IPs, so we keep a hardcoded
fallback covering the known 2026 + 2027 calendar and auto-fall back on any
failure mode (timeout, 4xx, 5xx, JSON parse error, empty result).

Cache semantics:
    - The fetched set is memoised in-process for ``CACHE_TTL_SECONDS``.
    - A successful fetch replaces the cached set atomically.
    - A failed fetch does NOT clobber a previously-good cache; we only fall
      back to the hardcoded list when there is nothing cached at all.

Public API:
    is_trading_holiday(d) -> bool      # fast, uses in-process cache
    refresh_holidays() -> set[str]     # async, call at startup/midnight
    get_cached_holidays() -> set[str]  # introspection for /status

All date strings are ``YYYY-MM-DD`` in IST.
"""

from __future__ import annotations

import asyncio
import logging
import time as _time
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Set

import httpx

logger = logging.getLogger("gods_eye.nse_holidays")

IST = timezone(timedelta(hours=5, minutes=30))

# ── Hardcoded fallback ──────────────────────────────────────────────────────
# Official NSE trading holidays. Keep this list updated annually when NSE
# publishes the next year's circular. This is a safety net only — the
# fetcher is authoritative when it succeeds.
#
# Source: NSE circular "Trading holidays for the calendar year YYYY"
# https://www.nseindia.com/resources/exchange-communication-holidays
FALLBACK_HOLIDAYS: Set[str] = {
    # 2026 — confirmed from NSE 2026 calendar
    "2026-01-26",  # Republic Day (Mon)
    "2026-03-04",  # Mahashivratri (Wed)
    "2026-03-19",  # Holi (Thu)
    "2026-03-21",  # Bakri Id (Sat — not a trading day anyway)
    "2026-04-03",  # Good Friday (Fri)
    "2026-04-14",  # Dr. Ambedkar Jayanti (Tue)
    "2026-05-01",  # Maharashtra Day (Fri)
    "2026-05-27",  # Buddha Pournima (Wed)
    "2026-08-15",  # Independence Day (Sat — non-trading anyway)
    "2026-08-26",  # Ganesh Chaturthi (Wed)
    "2026-10-02",  # Mahatma Gandhi Jayanti (Fri)
    "2026-10-20",  # Dussehra (Tue)
    "2026-11-09",  # Diwali Laxmi Pujan — special muhurat trading, not a full holiday; keep conservative
    "2026-11-25",  # Guru Nanak Jayanti (Wed)
    "2026-12-25",  # Christmas (Fri)

    # 2027 — rough (update when NSE publishes)
    "2027-01-26",  # Republic Day (Tue)
    "2027-03-26",  # Holi (Fri)
    "2027-08-16",  # Independence Day observed (Mon)
    "2027-10-29",  # Diwali (Fri)
    "2027-12-27",  # Christmas observed (Mon)
}

# NSE public holiday master endpoint. Returns JSON with arrays keyed by
# segment; we want ``CM`` (cash market = equities + F&O). The endpoint
# requires a browser-like User-Agent or it returns 401.
NSE_HOLIDAY_URL = "https://www.nseindia.com/api/holiday-master?type=trading"
NSE_HOME_URL = "https://www.nseindia.com"  # for session cookies
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

# Refresh once per day (roughly) — but the scheduler calls refresh_holidays()
# explicitly at midnight, so this is just a belt-and-suspenders TTL.
CACHE_TTL_SECONDS = 6 * 3600  # 6 hours

# Module-level cache. Not thread-safe but asyncio single-threaded.
_cached_holidays: Optional[Set[str]] = None
_cached_at: float = 0.0
_cache_source: str = "uninit"  # "nse_api" | "fallback" | "uninit"


def _today_ist() -> date:
    return datetime.now(IST).date()


async def _fetch_from_nse() -> Optional[Set[str]]:
    """Try to fetch the holiday list from NSE's public API.

    Returns None on any failure. Never raises.
    """
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(8.0, connect=4.0),
            headers=NSE_HEADERS,
            follow_redirects=True,
        ) as client:
            # NSE requires a session cookie before the API will respond —
            # hit the home page first to establish it.
            try:
                await client.get(NSE_HOME_URL)
            except httpx.HTTPError as e:
                logger.debug("NSE cookie priming failed: %s", e)

            resp = await client.get(NSE_HOLIDAY_URL)
            if resp.status_code != 200:
                logger.warning(
                    "NSE holiday fetch: HTTP %s (body=%s)",
                    resp.status_code,
                    resp.text[:200],
                )
                return None

            try:
                data = resp.json()
            except ValueError as e:
                logger.warning("NSE holiday fetch: JSON decode failed: %s", e)
                return None
    except httpx.HTTPError as e:
        logger.warning("NSE holiday fetch: %s", e)
        return None

    # Response shape: {"CM": [{"tradingDate": "28-Jan-2026", "weekDay": "Wednesday", ...}, ...], ...}
    cm = data.get("CM") if isinstance(data, dict) else None
    if not cm or not isinstance(cm, list):
        logger.warning("NSE holiday fetch: unexpected shape, keys=%s", list(data.keys()) if isinstance(data, dict) else type(data))
        return None

    holidays: Set[str] = set()
    for entry in cm:
        raw = entry.get("tradingDate") if isinstance(entry, dict) else None
        if not raw:
            continue
        # NSE format: "28-Jan-2026"
        for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d"):
            try:
                d = datetime.strptime(raw, fmt).date()
                holidays.add(d.isoformat())
                break
            except ValueError:
                continue

    if not holidays:
        logger.warning("NSE holiday fetch: parsed 0 dates from %d entries", len(cm))
        return None

    return holidays


async def refresh_holidays() -> Set[str]:
    """Refresh the in-process holiday cache.

    Tries NSE API; on failure, keeps any existing cache, else uses fallback.
    Safe to call repeatedly — idempotent.
    """
    global _cached_holidays, _cached_at, _cache_source

    fetched = await _fetch_from_nse()
    if fetched is not None:
        _cached_holidays = fetched
        _cached_at = _time.time()
        _cache_source = "nse_api"
        logger.info("NSE holidays refreshed from API: %d entries", len(fetched))
        return fetched

    # Fetch failed. Keep prior cache if any.
    if _cached_holidays is not None:
        logger.info("NSE holiday fetch failed — keeping prior cache (%d entries, source=%s)", len(_cached_holidays), _cache_source)
        return _cached_holidays

    # Cold start + fetch failed → fallback.
    _cached_holidays = set(FALLBACK_HOLIDAYS)
    _cached_at = _time.time()
    _cache_source = "fallback"
    logger.info("NSE holiday fetch failed on cold start — using hardcoded fallback (%d entries)", len(_cached_holidays))
    return _cached_holidays


def get_cached_holidays() -> Set[str]:
    """Return the current cached holiday set. Returns fallback if never initialised."""
    if _cached_holidays is None:
        return set(FALLBACK_HOLIDAYS)
    return _cached_holidays


def get_cache_info() -> dict:
    """Introspection for status endpoints."""
    return {
        "source": _cache_source,
        "entries": len(_cached_holidays) if _cached_holidays else len(FALLBACK_HOLIDAYS),
        "last_refreshed": (
            datetime.fromtimestamp(_cached_at, IST).isoformat()
            if _cached_at
            else None
        ),
    }


def is_trading_holiday(d: Optional[date] = None) -> bool:
    """Return True if `d` (default: today IST) is an NSE trading holiday.

    Does NOT consider weekends — callers should combine with a weekday check.
    """
    if d is None:
        d = _today_ist()
    holidays = _cached_holidays if _cached_holidays is not None else FALLBACK_HOLIDAYS
    return d.isoformat() in holidays


def next_holiday(after: Optional[date] = None) -> Optional[str]:
    """Return the next upcoming NSE holiday as ISO date string, or None."""
    if after is None:
        after = _today_ist()
    holidays = _cached_holidays if _cached_holidays is not None else FALLBACK_HOLIDAYS
    future = sorted(h for h in holidays if h > after.isoformat())
    return future[0] if future else None


def is_trading_day(d: Optional[date] = None) -> bool:
    """Convenience: True iff `d` is Mon-Fri AND not an NSE holiday.

    Matches what the simulation scheduler should gate on.
    """
    if d is None:
        d = _today_ist()
    if d.weekday() >= 5:  # Sat/Sun
        return False
    return not is_trading_holiday(d)
