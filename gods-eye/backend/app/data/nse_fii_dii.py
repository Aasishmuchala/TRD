"""NSE FII/DII activity data fetcher with anti-bot handling.

Fetches real FII/DII net flow data from NSE API endpoint.
Uses session management (similar to market_data.py) to handle anti-bot cookies.
"""

import asyncio
import logging
import random
from typing import Dict, Optional, Any

import httpx

logger = logging.getLogger("gods_eye.nse_fii_dii")

# NSE API Constants
NSE_BASE = "https://www.nseindia.com"
NSE_API = f"{NSE_BASE}/api"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": f"{NSE_BASE}/",
    "Connection": "keep-alive",
}


class NSEFiiDiiSession:
    """Maintains a persistent httpx session with NSE cookies for FII/DII data."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._cookie_ts: float = 0

    async def _ensure_session(self) -> httpx.AsyncClient:
        """Create client and fetch cookies if needed."""
        import time

        now = time.time()
        # Refresh cookies every 4 minutes (they expire ~5 min)
        if self._client is None or (now - self._cookie_ts) > 240:
            if self._client:
                await self._client.aclose()
            self._client = httpx.AsyncClient(
                headers=HEADERS,
                timeout=httpx.Timeout(15.0, connect=10.0),
                follow_redirects=True,
                verify=True,
            )
            # Hit homepage to get session cookies
            try:
                resp = await self._client.get(NSE_BASE)
                resp.raise_for_status()
                self._cookie_ts = now
                logger.info("NSE session cookies refreshed for FII/DII fetch")
            except Exception as e:
                logger.warning(f"Failed to refresh NSE cookies for FII/DII: {e}")
                self._cookie_ts = now - 200  # Retry sooner
        return self._client

    async def get(self, url: str) -> Optional[Dict]:
        """Make authenticated GET to NSE API. Returns parsed JSON or None."""
        client = await self._ensure_session()
        try:
            # Small random delay to avoid rate limiting
            await asyncio.sleep(random.uniform(0.1, 0.5))
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"NSE HTTP {e.response.status_code} for {url}")
            if e.response.status_code == 403:
                # Force cookie refresh on next call
                self._cookie_ts = 0
            return None
        except Exception as e:
            logger.warning(f"NSE request failed for {url}: {e}")
            return None

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


# Global session instance
_nse_fii_dii_session = NSEFiiDiiSession()


async def fetch_fii_dii_activity() -> Dict[str, Any]:
    """Fetch live FII/DII activity data from NSE API.

    Returns dict with:
        - fii_category: "FII/FPI"
        - fii_net_value: net FII flow in crores (float)
        - dii_category: "DII"
        - dii_net_value: net DII flow in crores (float)
        - timestamp: when data was fetched
        - source: "nse_api"
        - error: error message if fetch failed

    Example response structure from NSE API:
    [
        {
            "category": "FII/FPI",
            "netValue": "1234.56",
            "buyValue": "2000.00",
            "sellValue": "765.44",
            ...
        },
        {
            "category": "DII",
            "netValue": "-5678.90",
            ...
        }
    ]
    """
    from datetime import datetime

    endpoint = f"{NSE_API}/fiidiiActivity/category"
    data = await _nse_fii_dii_session.get(endpoint)

    result = {
        "timestamp": datetime.utcnow().isoformat(),
        "source": "nse_api",
        "fii_net_value": 0.0,
        "dii_net_value": 0.0,
        "fii_buy_value": 0.0,
        "fii_sell_value": 0.0,
        "dii_buy_value": 0.0,
        "dii_sell_value": 0.0,
        "error": None,
    }

    if not data:
        result["error"] = "NSE API returned no data — endpoint may be blocked or market may be closed"
        logger.warning(result["error"])
        return result

    if not isinstance(data, list):
        result["error"] = f"NSE API returned unexpected format: {type(data)}"
        logger.warning(result["error"])
        return result

    try:
        for entry in data:
            category = entry.get("category", "").upper()
            net_value = entry.get("netValue", 0)
            buy_value = entry.get("buyValue", 0)
            sell_value = entry.get("sellValue", 0)

            # Parse string values with commas (e.g., "1,234.56")
            if isinstance(net_value, str):
                net_value = float(net_value.replace(",", ""))
            if isinstance(buy_value, str):
                buy_value = float(buy_value.replace(",", ""))
            if isinstance(sell_value, str):
                sell_value = float(sell_value.replace(",", ""))

            if "FII" in category or "FPI" in category:
                result["fii_net_value"] = net_value
                result["fii_buy_value"] = buy_value
                result["fii_sell_value"] = sell_value
                logger.debug(f"FII data: net={net_value}, buy={buy_value}, sell={sell_value}")

            elif "DII" in category:
                result["dii_net_value"] = net_value
                result["dii_buy_value"] = buy_value
                result["dii_sell_value"] = sell_value
                logger.debug(f"DII data: net={net_value}, buy={buy_value}, sell={sell_value}")

        return result

    except Exception as e:
        result["error"] = f"Failed to parse FII/DII data: {str(e)}"
        logger.warning(result["error"])
        return result


async def close_session():
    """Clean up NSE session."""
    await _nse_fii_dii_session.close()
