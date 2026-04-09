"""Dhan Market Data Client — reliable Indian market data via official API.

Replaces flaky NSE scraping with Dhan's authenticated API.
Falls back to NSE scraping if Dhan is unavailable.

Auto-heals on 401: triggers TOTP token refresh and retries once.

Dhan API docs: https://dhanhq.co/docs/v2/
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.data.cache import cache, MarketCache

logger = logging.getLogger("gods_eye.dhan")

# Minimum seconds between token refresh attempts (avoid hammering Dhan auth)
_MIN_REFRESH_INTERVAL = 120


class DhanFetchError(Exception):
    """Raised when Dhan API returns an error or unexpected response for historical data."""

DHAN_BASE = "https://api.dhan.co/v2"

# Dhan security IDs for indices
NIFTY_50_SECURITY_ID = "13"       # NSE index
BANK_NIFTY_SECURITY_ID = "25"     # NSE index
INDIA_VIX_SECURITY_ID = "26"      # NSE index

# Exchange segment for indices
NSE_IDX = "IDX_I"


class DhanClient:
    """Fetches live market data from Dhan API.

    Self-heals on 401: triggers TOTP token refresh via DhanTokenManager
    and retries the request once with the new token.
    """

    def __init__(self):
        self._client_id = os.getenv("DHAN_CLIENT_ID", "")
        self._http: Optional[httpx.AsyncClient] = None
        self._last_token: str = ""  # Track token changes for client refresh
        self._last_refresh_attempt: float = 0.0  # epoch — throttle refresh calls
        self._refresh_lock: Optional[asyncio.Lock] = None

    @property
    def _access_token(self) -> str:
        """Always read from env so auto-renewed tokens are picked up."""
        return os.getenv("DHAN_ACCESS_TOKEN", "")

    @property
    def is_configured(self) -> bool:
        return bool(self._access_token and self._client_id)

    def _get_lock(self) -> asyncio.Lock:
        """Lazy-init asyncio.Lock (must be created inside a running loop)."""
        if self._refresh_lock is None:
            self._refresh_lock = asyncio.Lock()
        return self._refresh_lock

    async def _ensure_client(self) -> httpx.AsyncClient:
        current_token = self._access_token
        # Recreate client if token changed (after renewal)
        if self._http is not None and current_token != self._last_token:
            await self._http.aclose()
            self._http = None
        if self._http is None:
            self._last_token = current_token
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=10.0),
                headers={
                    "access-token": current_token,
                    "client-id": self._client_id,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._http

    async def _refresh_token_on_401(self) -> bool:
        """Trigger token refresh via DhanTokenManager. Returns True if new token obtained.

        Throttled: at most once per _MIN_REFRESH_INTERVAL seconds.
        Serialized: only one refresh at a time (asyncio.Lock).
        """
        now = time.monotonic()
        if now - self._last_refresh_attempt < _MIN_REFRESH_INTERVAL:
            logger.debug("Dhan 401 refresh throttled (last attempt %.0fs ago)", now - self._last_refresh_attempt)
            return False

        lock = self._get_lock()
        if lock.locked():
            # Another coroutine is already refreshing — wait for it
            async with lock:
                return bool(self._access_token)

        async with lock:
            self._last_refresh_attempt = time.monotonic()
            try:
                from app.auth.dhan_token_manager import dhan_token_manager
                old_token = self._access_token[:20] if self._access_token else "(empty)"
                logger.warning("Dhan 401 detected — triggering token refresh (old token starts: %s...)", old_token)
                success = await dhan_token_manager.ensure_valid_token()
                if success:
                    new_token = self._access_token
                    logger.info("Dhan token refreshed successfully (new token starts: %s...)", new_token[:20])
                    # Force httpx client rebuild on next call
                    if self._http is not None:
                        await self._http.aclose()
                        self._http = None
                    return True
                else:
                    logger.error("Dhan token refresh failed — all strategies exhausted")
                    return False
            except Exception as e:
                logger.error("Dhan token refresh error: %s", e)
                return False

    async def _get(self, endpoint: str, _retried: bool = False) -> Optional[Dict]:
        client = await self._ensure_client()
        url = f"{DHAN_BASE}{endpoint}"
        try:
            resp = await client.get(url)
            if resp.status_code == 401 and not _retried:
                if await self._refresh_token_on_401():
                    return await self._get(endpoint, _retried=True)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401 and not _retried:
                if await self._refresh_token_on_401():
                    return await self._get(endpoint, _retried=True)
            logger.warning("Dhan API error for %s: %s", endpoint, e)
            return None
        except Exception as e:
            logger.warning("Dhan API error for %s: %s", endpoint, e)
            return None

    async def _post(self, endpoint: str, payload: Dict, _retried: bool = False) -> Optional[Dict]:
        client = await self._ensure_client()
        url = f"{DHAN_BASE}{endpoint}"
        try:
            resp = await client.post(url, json=payload)
            if resp.status_code == 401 and not _retried:
                if await self._refresh_token_on_401():
                    return await self._post(endpoint, payload, _retried=True)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401 and not _retried:
                if await self._refresh_token_on_401():
                    return await self._post(endpoint, payload, _retried=True)
            logger.warning("Dhan API error for %s: %s", endpoint, e)
            return None
        except Exception as e:
            logger.warning("Dhan API error for %s: %s", endpoint, e)
            return None

    # ---- Market Data Methods ----

    async def get_market_quote(self, security_ids: List[str], exchange_segment: str = "IDX_I") -> Optional[Dict]:
        """Get live market quotes for given security IDs.

        Uses Dhan's /marketfeed/quote endpoint.
        """
        cached = cache.get(f"dhan_quote_{','.join(security_ids)}")
        if cached:
            return cached

        # Dhan marketfeed requires integer IDs
        int_ids = [int(sid) for sid in security_ids]
        data = await self._post("/marketfeed/quote", {
            exchange_segment: int_ids,
        })

        if data:
            cache.set(f"dhan_quote_{','.join(security_ids)}", data, ttl=10)

        return data

    async def get_ltp(self, security_ids: List[str], exchange_segment: str = "IDX_I") -> Optional[Dict]:
        """Get last traded price for securities.

        Note: Dhan marketfeed requires integer security IDs, not strings.
        """
        cached = cache.get(f"dhan_ltp_{','.join(security_ids)}")
        if cached:
            return cached

        # Dhan marketfeed requires integer IDs
        int_ids = [int(sid) for sid in security_ids]
        data = await self._post("/marketfeed/ltp", {
            exchange_segment: int_ids,
        })

        if data:
            cache.set(f"dhan_ltp_{','.join(security_ids)}", data, ttl=5)

        return data

    async def get_option_chain(self, under_security_id: str = "13", expiry: str = None) -> Optional[Dict]:
        """Get options chain for an index.

        Args:
            under_security_id: "13" for Nifty 50
            expiry: Expiry date in YYYY-MM-DD format. If None, uses nearest.
        """
        cache_key = f"dhan_optchain_{under_security_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        payload = {
            "UnderlyingScrip": int(under_security_id),
            "UnderlyingSeg": "IDX_I",
        }
        if expiry:
            payload["ExpiryDate"] = expiry

        data = await self._post("/optionchain", payload)
        if data:
            cache.set(cache_key, data, ttl=30)

        return data

    def _extract_ltp(self, data: Optional[Dict], security_id: str) -> Optional[Dict]:
        """Extract LTP from Dhan marketfeed response.

        Dhan returns: {"data": {"IDX_I": {"13": {"last_price": 22804.9}}}, "status": "success"}
        """
        if not data or "data" not in data:
            return None
        # Navigate nested structure: data -> segment -> security_id
        for segment_data in data["data"].values():
            if isinstance(segment_data, dict):
                item = segment_data.get(security_id) or segment_data.get(str(security_id))
                if item and isinstance(item, dict):
                    return item
        return None

    async def fetch_all_indices(self) -> Dict[str, Optional[Dict[str, Any]]]:
        """Fetch Nifty 50, Bank Nifty, and India VIX in a SINGLE API call.

        This avoids Dhan 429 rate limits by batching all 3 index security IDs
        into one /marketfeed/ltp request: {"IDX_I": [13, 25, 26]}.

        Returns:
            {"nifty": {...}, "bank_nifty": {...}, "vix": {...}}
            Each value is the parsed result dict or None if extraction failed.
        """
        all_ids = [NIFTY_50_SECURITY_ID, BANK_NIFTY_SECURITY_ID, INDIA_VIX_SECURITY_ID]

        # Single batched LTP call
        cached = cache.get("dhan_ltp_all_indices")
        if cached:
            data = cached
        else:
            int_ids = [int(sid) for sid in all_ids]
            data = await self._post("/marketfeed/ltp", {
                "IDX_I": int_ids,
            })
            if data:
                cache.set("dhan_ltp_all_indices", data, ttl=5)

        # Extract each index from the single response
        nifty_item = self._extract_ltp(data, NIFTY_50_SECURITY_ID)
        bank_item = self._extract_ltp(data, BANK_NIFTY_SECURITY_ID)
        vix_item = self._extract_ltp(data, INDIA_VIX_SECURITY_ID)

        return {
            "nifty": self._parse_index_ltp(nifty_item),
            "bank_nifty": self._parse_index_ltp(bank_item),
            "vix": self._parse_vix_ltp(vix_item),
        }

    def _parse_index_ltp(self, item: Optional[Dict]) -> Optional[Dict[str, Any]]:
        """Parse a Dhan LTP item into standard index dict."""
        if not item:
            return None
        ltp = float(item.get("last_price", 0) or item.get("LTP", 0) or 0)
        prev = float(item.get("close", 0) or 0) or ltp
        return {
            "last": ltp,
            "open": float(item.get("open", 0) or 0),
            "high": float(item.get("high", 0) or 0),
            "low": float(item.get("low", 0) or 0),
            "prev_close": prev,
            "change": ltp - prev if prev else 0,
            "change_pct": ((ltp - prev) / prev * 100) if prev else 0,
        }

    def _parse_vix_ltp(self, item: Optional[Dict]) -> Optional[Dict[str, Any]]:
        """Parse a Dhan LTP item into standard VIX dict."""
        if not item:
            return None
        current = float(item.get("last_price", 0) or item.get("LTP", 0) or 15.0)
        prev = float(item.get("close", 0) or 0) or current
        return {
            "current": current,
            "change": current - prev,
            "change_pct": ((current - prev) / prev * 100) if prev else 0,
        }

    # ---- Legacy single-index methods (kept for backward compat) ----

    async def fetch_nifty50(self) -> Dict[str, Any]:
        """Fetch Nifty 50 index quote via Dhan."""
        data = await self.get_ltp([NIFTY_50_SECURITY_ID])
        item = self._extract_ltp(data, NIFTY_50_SECURITY_ID)
        return self._parse_index_ltp(item)

    async def fetch_bank_nifty(self) -> Dict[str, Any]:
        """Fetch Bank Nifty index quote via Dhan."""
        data = await self.get_ltp([BANK_NIFTY_SECURITY_ID])
        item = self._extract_ltp(data, BANK_NIFTY_SECURITY_ID)
        return self._parse_index_ltp(item)

    async def fetch_india_vix(self) -> Dict[str, Any]:
        """Fetch India VIX via Dhan."""
        data = await self.get_ltp([INDIA_VIX_SECURITY_ID])
        item = self._extract_ltp(data, INDIA_VIX_SECURITY_ID)
        return self._parse_vix_ltp(item)

    async def fetch_options_summary(self) -> Dict[str, Any]:
        """Fetch Nifty options chain and compute PCR, max pain."""
        data = await self.get_option_chain(NIFTY_50_SECURITY_ID)
        if not data or "data" not in data:
            return None

        chain = data["data"]
        total_call_oi = 0
        total_put_oi = 0
        strike_pain = {}

        for row in chain:
            strike = row.get("strike_price", 0)
            oi = row.get("oi", 0) or 0
            opt_type = row.get("option_type", "").upper()

            if opt_type == "CE":
                total_call_oi += oi
                strike_pain.setdefault(strike, {"ce_oi": 0, "pe_oi": 0})
                strike_pain[strike]["ce_oi"] = oi
            elif opt_type == "PE":
                total_put_oi += oi
                strike_pain.setdefault(strike, {"ce_oi": 0, "pe_oi": 0})
                strike_pain[strike]["pe_oi"] = oi

        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0

        # Compute max pain
        max_pain = 0
        min_pain_val = float("inf")
        for settle in sorted(strike_pain.keys()):
            total = 0
            for s, d in strike_pain.items():
                if s < settle:
                    total += d["ce_oi"] * (settle - s)
                elif s > settle:
                    total += d["pe_oi"] * (s - settle)
            if total < min_pain_val:
                min_pain_val = total
                max_pain = settle

        return {
            "pcr": round(pcr, 3),
            "max_pain": float(max_pain),
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
        }

    async def fetch_historical_candles(
        self,
        security_id: str,
        from_date: str,
        to_date: str,
        exchange_segment: str = "NSE_EQ",
        instrument: str = "EQUITY",
        _retried: bool = False,
    ) -> list:
        """Fetch daily OHLCV candles from Dhan /v2/charts/historical.

        NOTE: Dhan does NOT support historical candles for IDX_I (index) segment.
        For NIFTY/BANKNIFTY/VIX historical data, use Yahoo Finance or another source.
        This method works for equities (NSE_EQ/EQUITY) and F&O instruments.

        Auto-retries once on 401 after refreshing the token.
        """
        client = await self._ensure_client()
        url = f"{DHAN_BASE}/charts/historical"
        payload = {
            "securityId": security_id,
            "exchangeSegment": exchange_segment,
            "instrument": instrument,
            "expiryCode": 0,
            "fromDate": from_date,
            "toDate": to_date,
        }
        try:
            resp = await client.post(url, json=payload)
        except Exception as exc:
            raise DhanFetchError(f"HTTP request failed for securityId={security_id}: {exc}") from exc

        if resp.status_code == 401 and not _retried:
            if await self._refresh_token_on_401():
                return await self.fetch_historical_candles(
                    security_id, from_date, to_date,
                    exchange_segment, instrument, _retried=True,
                )

        if resp.status_code != 200:
            raise DhanFetchError(
                f"Dhan /charts/historical returned HTTP {resp.status_code} "
                f"for securityId={security_id}: {resp.text[:200]}"
            )

        data = resp.json()
        opens = data.get("open")
        closes = data.get("close")
        highs = data.get("high")
        lows = data.get("low")
        volumes = data.get("volume")
        timestamps = data.get("timestamp") or data.get("start_Time")

        if not closes or not timestamps:
            raise DhanFetchError(
                f"Dhan /charts/historical response missing OHLCV data "
                f"for securityId={security_id}. Keys: {list(data.keys())}"
            )

        candles = []
        for i, ts in enumerate(timestamps):
            date_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
            candles.append({
                "date": date_str,
                "open": float(opens[i]) if opens else 0.0,
                "high": float(highs[i]) if highs else 0.0,
                "low": float(lows[i]) if lows else 0.0,
                "close": float(closes[i]),
                "volume": int(volumes[i]) if volumes else 0,
            })
        return candles

    async def shutdown(self):
        if self._http:
            await self._http.aclose()
            self._http = None


# Global singleton
dhan_client = DhanClient()
