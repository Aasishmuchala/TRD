"""FII/DII activity data fetcher with multi-source fallback.

NSE's public API is often blocked from cloud provider IPs (Railway, AWS, etc.).
This module tries sources in order and returns the first success:
  1. NSE API (primary, multiple endpoint variants)
  2. Moneycontrol mcapi JSON (fallback #1)
  3. BSE India API (fallback #2)

All sources are normalized to the same output shape so downstream callers
(fii_dii_collector, fii_dii_store) do not need to change.
"""

import asyncio
import logging
import random
import re
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("gods_eye.nse_fii_dii")

# ---------------- NSE session (anti-bot cookie handling) ----------------

NSE_BASE = "https://www.nseindia.com"
NSE_API = f"{NSE_BASE}/api"

# Endpoint path changes often — try multiple variants. The first one that
# returns data wins. All return the same "category" schema.
NSE_ENDPOINT_VARIANTS = [
    f"{NSE_API}/fiidiiTradeReact",      # current (observed working 2025+)
    f"{NSE_API}/fiidiiActivity/category",  # legacy (pre-2024)
    f"{NSE_API}/fiidii",                # alternate
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    # Drop `br` — httpx does not decode brotli unless the `brotli` extra is
    # installed, and NSE will return brotli when we advertise it. Ask only
    # for gzip/deflate so httpx handles decoding natively.
    "Accept-Encoding": "gzip, deflate",
    "Referer": f"{NSE_BASE}/",
    "Connection": "keep-alive",
}


class NSEFiiDiiSession:
    """Maintains a persistent httpx session with NSE cookies for FII/DII data."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._cookie_ts: float = 0

    async def _ensure_session(self) -> httpx.AsyncClient:
        import time

        now = time.time()
        if self._client is None or (now - self._cookie_ts) > 240:
            if self._client:
                await self._client.aclose()
            self._client = httpx.AsyncClient(
                headers=HEADERS,
                timeout=httpx.Timeout(15.0, connect=10.0),
                follow_redirects=True,
                verify=True,
            )
            try:
                resp = await self._client.get(NSE_BASE)
                resp.raise_for_status()
                self._cookie_ts = now
                logger.debug("NSE session cookies refreshed")
            except Exception as e:
                logger.warning("Failed to refresh NSE cookies: %s", e)
                self._cookie_ts = now - 200

        return self._client

    async def get(self, url: str) -> Optional[Any]:
        client = await self._ensure_session()
        try:
            await asyncio.sleep(random.uniform(0.1, 0.5))
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.debug("NSE HTTP %s for %s", e.response.status_code, url)
            if e.response.status_code == 403:
                self._cookie_ts = 0
            return None
        except Exception as e:
            logger.debug("NSE request failed for %s: %s", url, e)
            return None

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


_nse_session = NSEFiiDiiSession()


# ---------------- Result scaffold ----------------


def _empty_result() -> Dict[str, Any]:
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "source": None,
        "fii_net_value": 0.0,
        "dii_net_value": 0.0,
        "fii_buy_value": 0.0,
        "fii_sell_value": 0.0,
        "dii_buy_value": 0.0,
        "dii_sell_value": 0.0,
        "error": None,
    }


def _to_float(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        v = v.replace(",", "").strip()
        if not v or v == "-":
            return 0.0
        try:
            return float(v)
        except ValueError:
            return 0.0
    return 0.0


# ---------------- Source 1: NSE ----------------


async def _fetch_from_nse() -> Optional[Dict[str, Any]]:
    """Try NSE API endpoint variants. Return result dict or None on failure."""
    for url in NSE_ENDPOINT_VARIANTS:
        data = await _nse_session.get(url)
        if not data or not isinstance(data, list):
            continue

        result = _empty_result()
        result["source"] = "nse_api"
        try:
            for entry in data:
                category = str(entry.get("category", "")).upper()
                net_value = _to_float(entry.get("netValue", 0))
                buy_value = _to_float(entry.get("buyValue", 0))
                sell_value = _to_float(entry.get("sellValue", 0))

                if "FII" in category or "FPI" in category:
                    result["fii_net_value"] = net_value
                    result["fii_buy_value"] = buy_value
                    result["fii_sell_value"] = sell_value
                elif "DII" in category:
                    result["dii_net_value"] = net_value
                    result["dii_buy_value"] = buy_value
                    result["dii_sell_value"] = sell_value

            if result["fii_net_value"] != 0 or result["dii_net_value"] != 0:
                logger.info("FII/DII: got data from NSE %s", url)
                return result
        except Exception as e:
            logger.debug("NSE parse failed for %s: %s", url, e)
            continue

    return None


# ---------------- Source 2: Moneycontrol ----------------

MC_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.moneycontrol.com/",
}


async def _fetch_from_moneycontrol() -> Optional[Dict[str, Any]]:
    """Fetch latest day FII/DII from Moneycontrol.

    The public page embeds a Next.js __NEXT_DATA__ JSON blob under
    props.pageProps.FiiDiiData.fiiDiiData (most-recent day first).
    Fields: fiiCM (FII cash-market net), diiCM (DII cash-market net), date, ...
    Only net cash-market is exposed; buy/sell breakdown is not public here.
    """
    import json

    urls = [
        "https://www.moneycontrol.com/markets/fii-dii-data/",
        "https://www.moneycontrol.com/stocks/marketstats/fii_dii_activity/index.php",
    ]

    html = None
    for url in urls:
        try:
            async with httpx.AsyncClient(
                headers=MC_HEADERS,
                timeout=httpx.Timeout(15.0, connect=10.0),
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
                break
        except Exception as e:
            logger.debug("Moneycontrol fetch failed for %s: %s", url, e)
            continue

    if not html:
        return None

    # Extract __NEXT_DATA__ JSON
    nd_re = re.compile(
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )
    m = nd_re.search(html)
    if not m:
        logger.debug("Moneycontrol: __NEXT_DATA__ not found")
        return None

    try:
        nd = json.loads(m.group(1))
    except Exception as e:
        logger.debug("Moneycontrol: __NEXT_DATA__ JSON parse failed: %s", e)
        return None

    try:
        rows = (
            nd.get("props", {})
              .get("pageProps", {})
              .get("FiiDiiData", {})
              .get("fiiDiiData", [])
        )
    except Exception:
        rows = []

    if not rows:
        logger.debug("Moneycontrol: fiiDiiData empty")
        return None

    # Row 0 is most recent day. Skip rows that are all zero.
    for row in rows:
        fii_net = _to_float(row.get("fiiCM"))
        dii_net = _to_float(row.get("diiCM"))
        if fii_net == 0 and dii_net == 0:
            continue

        date_str = row.get("date") or row.get("fDate") or "?"
        result = _empty_result()
        result["source"] = "moneycontrol"
        result["fii_net_value"] = fii_net
        result["dii_net_value"] = dii_net
        # MC does not expose buy/sell breakdown in this payload — leave zeros
        logger.info(
            "FII/DII: got data from Moneycontrol for %s (FII=%+.2f, DII=%+.2f)",
            date_str, fii_net, dii_net,
        )
        return result

    logger.debug("Moneycontrol: no non-zero row found")
    return None


# ---------------- Public entry point ----------------


async def fetch_fii_dii_activity() -> Dict[str, Any]:
    """Fetch live FII/DII activity data, trying multiple sources.

    Order:
        1. NSE `/api/fiidiiTradeReact` (fastest, buy/sell breakdown).
        2. Moneycontrol `/markets/fii-dii-data/` (public, net only).
    Returns the first success; otherwise an empty result with error populated.
    """
    # Source 1: NSE (may be blocked from cloud IPs)
    try:
        nse_result = await _fetch_from_nse()
        if nse_result is not None:
            return nse_result
    except Exception as e:
        logger.debug("NSE source raised: %s", e)

    # Source 2: Moneycontrol (usually works from cloud IPs)
    try:
        mc_result = await _fetch_from_moneycontrol()
        if mc_result is not None:
            return mc_result
    except Exception as e:
        logger.debug("Moneycontrol source raised: %s", e)

    # All sources failed
    result = _empty_result()
    result["source"] = "none"
    result["error"] = (
        "All FII/DII sources failed (NSE, Moneycontrol) — "
        "endpoints may be blocked or data not yet published for today"
    )
    logger.warning(result["error"])
    return result


async def close_session():
    """Clean up NSE session."""
    await _nse_session.close()
