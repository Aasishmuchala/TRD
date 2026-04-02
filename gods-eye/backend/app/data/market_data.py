"""Live Indian market data service — Dhan API primary, NSE fallback.

Data source priority:
    1. Dhan API (reliable, authenticated, requires DHAN_ACCESS_TOKEN)
    2. NSE India scraping (free but flaky, gets blocked under load)
    3. Fallback mock data (deterministic, always available)

NSE anti-bot handling (fallback only):
    - First hit to nseindia.com sets session cookies
    - All subsequent requests use that session
    - User-Agent must look like a real browser
"""

import asyncio
import logging
import random
from datetime import datetime, time as dt_time
from typing import Any, Dict, List, Optional

import httpx

from app.data.cache import cache, MarketCache
from app.data.dhan_client import dhan_client
from app.data.pcr_store import pcr_store
from app.data.fii_dii_store import fii_dii_store

logger = logging.getLogger("gods_eye.market_data")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
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

# Sector index symbols tracked
SECTOR_INDICES = [
    "NIFTY BANK",
    "NIFTY IT",
    "NIFTY PHARMA",
    "NIFTY AUTO",
    "NIFTY METAL",
    "NIFTY REALTY",
    "NIFTY FMCG",
    "NIFTY ENERGY",
    "NIFTY FINANCIAL SERVICES",
]


# ---------------------------------------------------------------------------
# NSE Session Manager
# ---------------------------------------------------------------------------
class NSESession:
    """Maintains a persistent httpx session with NSE cookies."""

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
                logger.info("NSE session cookies refreshed")
            except Exception as e:
                logger.warning(f"Failed to refresh NSE cookies: {e}")
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


# ---------------------------------------------------------------------------
# Market Data Service
# ---------------------------------------------------------------------------
class MarketDataService:
    """Fetches live Indian market data — Dhan primary, NSE fallback."""

    def __init__(self):
        self._nse = NSESession()
        self._dhan = dhan_client
        if self._dhan.is_configured:
            logger.info("Dhan API configured — using as primary data source")
        else:
            logger.info("Dhan API not configured — using NSE scraping (set DHAN_ACCESS_TOKEN + DHAN_CLIENT_ID for reliable data)")

    # ---- High-level methods (used by API routes) ----

    async def get_live_snapshot(self) -> Dict[str, Any]:
        """Full market snapshot: Nifty, VIX, FII/DII, breadth.

        Returns a dict matching the shape expected by MarketInput + extras.
        """
        cached = cache.get("live_snapshot")
        if cached:
            return cached

        # Fetch indices in a SINGLE Dhan call (avoids 429 rate limits),
        # plus FII/DII and breadth in parallel
        indices_task = self._fetch_all_indices()
        fii_dii_task = self._fetch_fii_dii()
        breadth_task = self._fetch_market_breadth()

        indices, fii_dii, breadth = await asyncio.gather(
            indices_task, fii_dii_task, breadth_task
        )

        nifty = indices.get("nifty") or {}
        bank_nifty = indices.get("bank_nifty") or {}
        vix = indices.get("vix") or {}

        def _num(val, default=0):
            """Safely coerce API response values to float."""
            if val is None:
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        nifty_spot = _num(nifty.get("last"))

        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "market_open": self._is_market_open(),

            # Nifty 50
            "nifty_spot": nifty_spot,
            "nifty_open": _num(nifty.get("open")),
            "nifty_high": _num(nifty.get("high")),
            "nifty_low": _num(nifty.get("low")),
            "nifty_close": _num(nifty.get("prev_close")),
            "nifty_change": _num(nifty.get("change")),
            "nifty_change_pct": _num(nifty.get("change_pct")),

            # Bank Nifty
            "bank_nifty_spot": _num(bank_nifty.get("last")),
            "bank_nifty_change": _num(bank_nifty.get("change")),
            "bank_nifty_change_pct": _num(bank_nifty.get("change_pct")),

            # VIX
            "india_vix": _num(vix.get("current"), 15.0),
            "vix_change": _num(vix.get("change")),
            "vix_change_pct": _num(vix.get("change_pct")),

            # FII / DII
            "fii_net_today": _num(fii_dii.get("fii_net_today")),
            "dii_net_today": _num(fii_dii.get("dii_net_today")),
            "fii_flow_5d": _num(fii_dii.get("fii_net_5d")),
            "dii_flow_5d": _num(fii_dii.get("dii_net_5d")),

            # Breadth
            "advance_decline_ratio": _num(breadth.get("adr"), 1.0),
            "advances": _num(breadth.get("advances")),
            "declines": _num(breadth.get("declines")),
            "unchanged": _num(breadth.get("unchanged")),

            # Source + error reporting
            "data_source": "dhan_live" if nifty_spot > 0 else "fallback",
            "data_error": nifty.get("_error") or (None if nifty_spot > 0 else "No live market data available — using fallback data"),
        }

        cache.set("live_snapshot", snapshot, ttl=MarketCache.DEFAULT_TTLS["spot"])
        return snapshot

    async def get_options_chain(self, symbol: str = "NIFTY") -> Dict[str, Any]:
        """Nifty options chain summary: PCR, max pain, top OI strikes."""
        cache_key = f"options_{symbol}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        data = await self._fetch_options_chain(symbol)
        cache.set(cache_key, data, ttl=MarketCache.DEFAULT_TTLS["options"])
        return data

    async def get_sector_indices(self) -> List[Dict[str, Any]]:
        """All tracked sector indices with current value and % change."""
        cached = cache.get("sectors")
        if cached:
            return cached

        data = await self._fetch_sector_indices()
        cache.set("sectors", data, ttl=MarketCache.DEFAULT_TTLS["sectors"])
        return data

    async def build_market_input(self) -> Dict[str, Any]:
        """Build a complete MarketInput-compatible dict from live data.

        This is the key method used by /api/simulate?source=live.
        """
        snapshot = await self.get_live_snapshot()
        options = await self.get_options_chain()

        nifty_spot = snapshot.get("nifty_spot", 0)
        if nifty_spot <= 0:
            nifty_spot = 23500  # Fallback

        # Fetch forex data in parallel
        usd_inr_task = self._fetch_usd_inr()
        dxy_task = self._fetch_dxy()
        usd_inr, dxy = await asyncio.gather(usd_inr_task, dxy_task)

        # PCR: prefer live options chain, fallback to stored PCR from pcr_collector
        pcr_value = options.get("pcr", 0)
        if not pcr_value or pcr_value == 1.0:
            try:
                latest_pcr = pcr_store.get_latest()
                if latest_pcr and latest_pcr.get("pcr"):
                    pcr_value = latest_pcr["pcr"]
                    logger.debug("PCR from store: %.3f (date=%s)", pcr_value, latest_pcr.get("date"))
            except Exception as e:
                logger.warning("PCR store fallback failed: %s", e)
        if not pcr_value:
            pcr_value = 1.0

        return {
            "nifty_spot": nifty_spot,
            "nifty_open": snapshot.get("nifty_open"),
            "nifty_high": snapshot.get("nifty_high"),
            "nifty_low": snapshot.get("nifty_low"),
            "nifty_close": snapshot.get("nifty_close"),
            "india_vix": snapshot.get("india_vix", 15.0),
            "fii_flow_5d": snapshot.get("fii_flow_5d", 0),
            "dii_flow_5d": snapshot.get("dii_flow_5d", 0),
            "usd_inr": usd_inr,
            "dxy": dxy,
            "pcr_index": pcr_value,
            "max_pain": options.get("max_pain", nifty_spot),
            "dte": options.get("dte", 5),
            "context": self._detect_context(),
            # Extras not in standard MarketInput but useful for agents
            "_live": True,
            "_timestamp": snapshot.get("timestamp"),
            "_fii_net_today": snapshot.get("fii_net_today", 0),
            "_dii_net_today": snapshot.get("dii_net_today", 0),
            "_advance_decline_ratio": snapshot.get("advance_decline_ratio", 1.0),
            "_nifty_change_pct": snapshot.get("nifty_change_pct", 0),
            "_vix_change_pct": snapshot.get("vix_change_pct", 0),
        }

    # ---- NSE Fetchers ----

    async def _fetch_all_indices(self) -> Dict[str, Any]:
        """Fetch Nifty, Bank Nifty, VIX in a single Dhan API call.

        Returns dict with keys: nifty, bank_nifty, vix — each a data dict or empty dict.
        """
        if self._dhan.is_configured:
            try:
                result = await self._dhan.fetch_all_indices()
                nifty = result.get("nifty")
                if nifty and nifty.get("last", 0) > 0:
                    logger.debug("All indices from Dhan API (batched)")
                    return {
                        "nifty": nifty,
                        "bank_nifty": result.get("bank_nifty") or {},
                        "vix": result.get("vix") or {"current": 15.0, "change": 0, "change_pct": 0},
                    }
                logger.warning("Dhan batched call returned no Nifty data — market may be closed")
            except Exception as e:
                logger.warning("Dhan batched index fetch failed: %s", e)
        else:
            logger.error("Dhan API not configured — set DHAN_ACCESS_TOKEN + DHAN_CLIENT_ID")

        # Fallback — all empty
        return {
            "nifty": self._error_nifty("Dhan API returned no data"),
            "bank_nifty": {},
            "vix": {"current": 15.0, "change": 0, "change_pct": 0},
        }

    async def _fetch_nifty50(self) -> Dict[str, Any]:
        """Fetch Nifty 50 — Dhan only. Error if Dhan fails."""
        if self._dhan.is_configured:
            result = await self._dhan.fetch_nifty50()
            if result and result.get("last", 0) > 0:
                logger.debug("Nifty 50 from Dhan API")
                return result
            logger.warning("Dhan returned no Nifty data — market may be closed")
            return self._error_nifty("Dhan API returned no data — market may be closed")
        logger.error("Dhan API not configured — set DHAN_ACCESS_TOKEN + DHAN_CLIENT_ID")
        return self._error_nifty("Dhan API not configured")
        # NSE fallback disabled — Dhan is the only source
        data = await self._nse.get(
            f"{NSE_API}/equity-stockIndices?index=NIFTY%2050"
        )
        if data and "data" in data:
            for item in data["data"]:
                if item.get("symbol") == "NIFTY 50":
                    return {
                        "last": item.get("lastPrice", 0),
                        "open": item.get("open", 0),
                        "high": item.get("dayHigh", 0),
                        "low": item.get("dayLow", 0),
                        "prev_close": item.get("previousClose", 0),
                        "change": item.get("change", 0),
                        "change_pct": item.get("pChange", 0),
                    }
        # Fallback
        return self._fallback_nifty()

    async def _fetch_bank_nifty(self) -> Dict[str, Any]:
        """Fetch Bank Nifty — Dhan only. Error if Dhan fails."""
        if self._dhan.is_configured:
            result = await self._dhan.fetch_bank_nifty()
            if result and result.get("last", 0) > 0:
                logger.debug("Bank Nifty from Dhan API")
                return result
            return {"last": 0, "open": 0, "high": 0, "low": 0, "prev_close": 0, "change": 0, "change_pct": 0, "_error": "Dhan returned no Bank Nifty data"}
        return {"last": 0, "open": 0, "high": 0, "low": 0, "prev_close": 0, "change": 0, "change_pct": 0, "_error": "Dhan not configured"}
        # NSE fallback disabled
        cached = cache.get("bank_nifty")
        if cached:
            return cached

        data = await self._nse.get(
            f"{NSE_API}/equity-stockIndices?index=NIFTY%20BANK"
        )
        if data and "data" in data:
            for item in data["data"]:
                symbol = item.get("symbol", item.get("indexSymbol", ""))
                if "BANK" in symbol.upper() and "NIFTY" in symbol.upper():
                    last = float(item.get("lastPrice", 0) or 0)
                    prev = float(item.get("previousClose", 0) or 0)
                    change = float(item.get("change", last - prev) or 0)
                    change_pct = float(item.get("pChange", 0) or 0)
                    if change_pct == 0 and prev > 0:
                        change_pct = (change / prev) * 100
                    result = {
                        "last": last,
                        "open": float(item.get("open", 0) or 0),
                        "high": float(item.get("dayHigh", 0) or 0),
                        "low": float(item.get("dayLow", 0) or 0),
                        "prev_close": prev,
                        "change": change,
                        "change_pct": change_pct,
                    }
                    cache.set("bank_nifty", result, ttl=MarketCache.DEFAULT_TTLS.get("spot", 60))
                    return result

        # Graceful fallback — return zeroed values
        return {"last": 0, "open": 0, "high": 0, "low": 0, "prev_close": 0, "change": 0, "change_pct": 0}

    async def _fetch_india_vix(self) -> Dict[str, Any]:
        """Fetch India VIX — Dhan only. Error if Dhan fails."""
        if self._dhan.is_configured:
            result = await self._dhan.fetch_india_vix()
            if result and result.get("current", 0) > 0:
                logger.debug("India VIX from Dhan API")
                return result
            return {"current": 0, "change": 0, "change_pct": 0, "_error": "Dhan returned no VIX data"}
        return {"current": 0, "change": 0, "change_pct": 0, "_error": "Dhan not configured"}
        # NSE fallback disabled
        data = await self._nse.get(f"{NSE_API}/allIndices")
        if data and "data" in data:
            for item in data["data"]:
                if "VIX" in item.get("index", "").upper():
                    return {
                        "current": item.get("last", 15.0),
                        "change": item.get("variation", 0),
                        "change_pct": item.get("percentChange", 0),
                    }
        return {"current": 15.0, "change": 0, "change_pct": 0}

    async def _fetch_fii_dii(self) -> Dict[str, Any]:
        """Fetch FII/DII daily activity data — stored 5-day sum from real data.

        Primary source: fii_dii_store (SQLite, populated by NSE scraper).
        Fallback: live NSE API with estimation for 5-day sum.
        """
        result = {
            "fii_net_today": 0,
            "dii_net_today": 0,
            "fii_net_5d": 0,
            "dii_net_5d": 0,
        }

        # Try stored data first (real 5-day rolling sum)
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            five_day = fii_dii_store.get_5d_sum(today_str)
            if five_day and five_day.get("days_found", 0) > 0:
                result["fii_net_5d"] = five_day["fii_5d_net"]
                result["dii_net_5d"] = five_day["dii_5d_net"]
                logger.debug(
                    "FII/DII 5d from store: FII=%+.0f Cr (%d days), DII=%+.0f Cr",
                    result["fii_net_5d"], five_day["days_found"], result["dii_net_5d"],
                )

            # Get today's net from store
            today_data = fii_dii_store.get_by_date(today_str)
            if today_data:
                result["fii_net_today"] = today_data.get("fii_net_cr", 0)
                result["dii_net_today"] = today_data.get("dii_net_cr", 0)
                return result
        except Exception as e:
            logger.warning("FII/DII store read failed: %s", e)

        # Fallback: live NSE API for today's data
        try:
            data = await self._nse.get(f"{NSE_API}/fiidiiActivity/category")
            if data and isinstance(data, list):
                for entry in data:
                    category = entry.get("category", "").upper()
                    net_value = entry.get("netValue", 0)
                    if isinstance(net_value, str):
                        net_value = float(net_value.replace(",", ""))

                    if "FII" in category or "FPI" in category:
                        result["fii_net_today"] = net_value
                    elif "DII" in category:
                        result["dii_net_today"] = net_value

                # If we got live data but no stored 5d, estimate
                if result["fii_net_5d"] == 0 and result["fii_net_today"] != 0:
                    result["fii_net_5d"] = result["fii_net_today"] * 2.5
                    result["dii_net_5d"] = result["dii_net_today"] * 2.5
                    logger.debug("FII/DII 5d estimated from today's live data (×2.5)")
        except Exception as e:
            logger.warning("Live NSE FII/DII fetch also failed: %s", e)

        return result

    async def _fetch_options_chain(self, symbol: str = "NIFTY") -> Dict[str, Any]:
        """Fetch options chain and compute PCR, max pain, top OI."""
        data = await self._nse.get(
            f"{NSE_API}/option-chain-indices?symbol={symbol}"
        )
        if not data or "records" not in data:
            return self._fallback_options()

        records = data["records"]
        expiry_dates = records.get("expiryDates", [])
        current_expiry = expiry_dates[0] if expiry_dates else None

        all_data = records.get("data", [])
        # Filter to current expiry
        chain = [
            row for row in all_data
            if row.get("expiryDate") == current_expiry
        ]

        if not chain:
            return self._fallback_options()

        # Compute PCR
        total_put_oi = 0
        total_call_oi = 0
        strike_pain = {}  # strike -> pain value

        for row in chain:
            strike = row.get("strikePrice", 0)
            ce = row.get("CE", {})
            pe = row.get("PE", {})
            ce_oi = ce.get("openInterest", 0) or 0
            pe_oi = pe.get("openInterest", 0) or 0

            total_call_oi += ce_oi
            total_put_oi += pe_oi

            # Max pain calculation: for each strike, sum of
            # (calls ITM loss + puts ITM loss) for all other strikes
            strike_pain[strike] = {"ce_oi": ce_oi, "pe_oi": pe_oi}

        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0

        # Max pain: strike where total loss to option writers is minimum
        max_pain = self._compute_max_pain(strike_pain)

        # Top OI strikes
        top_call_strikes = sorted(
            [(s, d["ce_oi"]) for s, d in strike_pain.items()],
            key=lambda x: x[1], reverse=True
        )[:5]
        top_put_strikes = sorted(
            [(s, d["pe_oi"]) for s, d in strike_pain.items()],
            key=lambda x: x[1], reverse=True
        )[:5]

        # Days to expiry
        dte = 5
        if current_expiry:
            try:
                exp_date = datetime.strptime(current_expiry, "%d-%b-%Y")
                dte = max(0, (exp_date - datetime.now()).days)
            except ValueError:
                pass

        # Underlying
        underlying = records.get("underlyingValue", 0)

        return {
            "symbol": symbol,
            "expiry": current_expiry,
            "dte": dte,
            "underlying": underlying,
            "pcr": round(pcr, 3),
            "max_pain": max_pain,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "top_call_oi_strikes": [
                {"strike": s, "oi": oi} for s, oi in top_call_strikes
            ],
            "top_put_oi_strikes": [
                {"strike": s, "oi": oi} for s, oi in top_put_strikes
            ],
        }

    async def _fetch_sector_indices(self) -> List[Dict[str, Any]]:
        """Fetch all sector index values."""
        data = await self._nse.get(f"{NSE_API}/allIndices")
        sectors = []
        if data and "data" in data:
            for item in data["data"]:
                name = item.get("index", "")
                if name in SECTOR_INDICES:
                    sectors.append({
                        "name": name,
                        "value": item.get("last", 0),
                        "change": item.get("variation", 0),
                        "change_pct": item.get("percentChange", 0),
                        "open": item.get("open", 0),
                        "high": item.get("high", 0),
                        "low": item.get("low", 0),
                        "prev_close": item.get("previousClose", 0),
                    })

        if not sectors:
            sectors = self._fallback_sectors()

        return sectors

    async def _fetch_market_breadth(self) -> Dict[str, Any]:
        """Fetch advance/decline data."""
        try:
            data = await self._nse.get(f"{NSE_API}/equity-stockIndices?index=NIFTY%2050")
            if data and "advance" in data:
                adv_data = data["advance"]
                advances = int(adv_data.get("advances", 25))
                declines = int(adv_data.get("declines", 25))
                unchanged = int(adv_data.get("unchanged", 0))
                adr = advances / declines if declines > 0 else 1.0
                return {
                    "advances": advances,
                    "declines": declines,
                    "unchanged": unchanged,
                    "adr": round(adr, 2),
                }
        except Exception as e:
            logger.warning("Market breadth fetch failed: %s", e)
        return {"advances": 25, "declines": 25, "unchanged": 0, "adr": 1.0}

    # ---- Forex Fetchers ----

    async def _fetch_usd_inr(self) -> float:
        """Fetch USD/INR rate from free forex API with fallback.

        Uses exchangerate-api.com (free, no API key needed).
        Falls back to 83.5 if API is unavailable.
        """
        cache_key = "forex_usd_inr"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            client = await self._nse._ensure_session()
            resp = await client.get(
                "https://api.exchangerate-api.com/v4/latest/USD",
                timeout=httpx.Timeout(10.0),
            )
            resp.raise_for_status()
            data = resp.json()
            rates = data.get("rates", {})
            usd_inr = rates.get("INR", 83.5)
            # Cache for 5 minutes
            cache.set(cache_key, usd_inr, ttl=300)
            logger.info(f"USD/INR fetched: {usd_inr}")
            return usd_inr
        except Exception as e:
            logger.warning(f"Failed to fetch USD/INR: {e}. Using fallback 83.5")
            return 83.5

    async def _fetch_dxy(self) -> float:
        """Fetch DXY (Dollar Index) with fallback estimation.

        Attempts to fetch from Yahoo Finance. If unavailable, estimates DXY
        from EUR/USD rate using the formula: DXY ≈ 50.14348112 * (1/EURUSD)^0.576
        Falls back to 104.0 if all methods fail.
        """
        cache_key = "forex_dxy"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            client = await self._nse._ensure_session()
            # Try Yahoo Finance endpoint
            resp = await client.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB",
                timeout=httpx.Timeout(10.0),
            )
            resp.raise_for_status()
            data = resp.json()
            result = data.get("chart", {}).get("result", [])
            if result and "quote" in result[0]:
                quote = result[0]["quote"]
                current_price = quote.get("regularMarketPrice")
                if current_price:
                    dxy = current_price
                    cache.set(cache_key, dxy, ttl=300)
                    logger.info(f"DXY fetched from Yahoo Finance: {dxy}")
                    return dxy
        except Exception as e:
            logger.debug(f"Failed to fetch DXY from Yahoo Finance: {e}")

        # Fallback: estimate from EUR/USD
        try:
            client = await self._nse._ensure_session()
            resp = await client.get(
                "https://api.exchangerate-api.com/v4/latest/USD",
                timeout=httpx.Timeout(10.0),
            )
            resp.raise_for_status()
            data = resp.json()
            rates = data.get("rates", {})
            eur_usd = rates.get("EUR", 1.0)  # 1 USD = X EUR
            # Convert to EUR/USD (USD value in terms of EUR)
            usd_eur = 1.0 / eur_usd if eur_usd > 0 else 1.0
            # DXY formula: 50.14348112 * (1/EURUSD)^0.576
            # We have EURUSD (eur_usd), so use that
            dxy = 50.14348112 * (1.0 / usd_eur) ** 0.576
            cache.set(cache_key, dxy, ttl=300)
            logger.info(f"DXY estimated from EUR/USD: {dxy}")
            return dxy
        except Exception as e:
            logger.warning(f"Failed to estimate DXY from EUR/USD: {e}. Using fallback 104.0")
            return 104.0

    # ---- Utility Methods ----

    @staticmethod
    def _compute_max_pain(strike_data: Dict[int, Dict]) -> float:
        """Compute max pain strike from OI data.

        Max pain = strike where sum of (ITM call value + ITM put value) is minimum.
        """
        strikes = sorted(strike_data.keys())
        if not strikes:
            return 0

        min_pain = float("inf")
        max_pain_strike = strikes[len(strikes) // 2]

        for settle_strike in strikes:
            total_pain = 0
            for s, data in strike_data.items():
                # Calls are ITM when s < settle_strike
                if s < settle_strike:
                    total_pain += data["ce_oi"] * (settle_strike - s)
                # Puts are ITM when s > settle_strike
                elif s > settle_strike:
                    total_pain += data["pe_oi"] * (s - settle_strike)

            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = settle_strike

        return float(max_pain_strike)

    @staticmethod
    def _is_market_open() -> bool:
        """Check if Indian markets are currently open (IST)."""
        now = datetime.utcnow()
        # IST = UTC + 5:30
        ist_hour = now.hour + 5
        ist_minute = now.minute + 30
        if ist_minute >= 60:
            ist_hour += 1
            ist_minute -= 60

        # Market hours: 9:15 AM - 3:30 PM IST, Mon-Fri
        weekday = (now.weekday())  # 0=Mon
        if weekday >= 5:  # Sat/Sun
            return False

        market_start = 9 * 60 + 15
        market_end = 15 * 60 + 30
        current = ist_hour * 60 + ist_minute

        return market_start <= current <= market_end

    @staticmethod
    def _detect_context() -> str:
        """Auto-detect market context from date."""
        now = datetime.now()
        day_of_week = now.weekday()

        # Thursday is weekly expiry
        if day_of_week == 3:
            return "weekly_expiry"

        # Last Thursday of month is monthly expiry
        import calendar
        month_cal = calendar.monthcalendar(now.year, now.month)
        last_thu = max(
            week[3] for week in month_cal if week[3] != 0
        )
        if now.day == last_thu:
            return "monthly_expiry"

        return "normal"

    # ---- Error Data (Dhan failed, no silent fallback) ----

    @staticmethod
    def _error_nifty(reason: str) -> Dict[str, Any]:
        """Return zeroed Nifty data with error reason — no fake numbers."""
        return {
            "last": 0, "open": 0, "high": 0, "low": 0, "prev_close": 0,
            "change": 0, "change_pct": 0, "_error": reason,
        }

    # ---- Fallback Data (legacy, kept for preset scenarios) ----

    @staticmethod
    def _fallback_nifty() -> Dict[str, Any]:
        """Reasonable defaults when NSE is down."""
        return {
            "last": 23500,
            "open": 23480,
            "high": 23580,
            "low": 23420,
            "prev_close": 23450,
            "change": 50,
            "change_pct": 0.21,
        }

    @staticmethod
    def _fallback_options() -> Dict[str, Any]:
        return {
            "symbol": "NIFTY",
            "expiry": "N/A",
            "dte": 5,
            "underlying": 23500,
            "pcr": 1.0,
            "max_pain": 23500,
            "total_call_oi": 0,
            "total_put_oi": 0,
            "top_call_oi_strikes": [],
            "top_put_oi_strikes": [],
        }

    @staticmethod
    def _fallback_sectors() -> List[Dict[str, Any]]:
        defaults = {
            "NIFTY BANK": 49500,
            "NIFTY IT": 34000,
            "NIFTY PHARMA": 18500,
            "NIFTY AUTO": 23000,
            "NIFTY METAL": 8500,
            "NIFTY REALTY": 900,
            "NIFTY FMCG": 55000,
            "NIFTY ENERGY": 36000,
            "NIFTY FINANCIAL SERVICES": 22500,
        }
        return [
            {
                "name": name,
                "value": val,
                "change": 0,
                "change_pct": 0,
                "open": val,
                "high": val,
                "low": val,
                "prev_close": val,
            }
            for name, val in defaults.items()
        ]

    async def shutdown(self):
        """Clean up session."""
        await self._nse.close()


# Global singleton
market_data_service = MarketDataService()
