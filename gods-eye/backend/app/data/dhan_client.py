"""Dhan Market Data Client — reliable Indian market data via official API.

Replaces flaky NSE scraping with Dhan's authenticated API.
Falls back to NSE scraping if Dhan is unavailable.

Dhan API docs: https://dhanhq.co/docs/v2/
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.data.cache import cache, MarketCache

logger = logging.getLogger("gods_eye.dhan")


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
    """Fetches live market data from Dhan API."""

    def __init__(self):
        self._access_token = os.getenv("DHAN_ACCESS_TOKEN", "")
        self._client_id = os.getenv("DHAN_CLIENT_ID", "")
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        return bool(self._access_token and self._client_id)

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=10.0),
                headers={
                    "access-token": self._access_token,
                    "client-id": self._client_id,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._http

    async def _get(self, endpoint: str) -> Optional[Dict]:
        client = await self._ensure_client()
        url = f"{DHAN_BASE}{endpoint}"
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Dhan API error for {endpoint}: {e}")
            return None

    async def _post(self, endpoint: str, payload: Dict) -> Optional[Dict]:
        client = await self._ensure_client()
        url = f"{DHAN_BASE}{endpoint}"
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Dhan API error for {endpoint}: {e}")
            return None

    # ---- Market Data Methods ----

    async def get_market_quote(self, security_ids: List[str], exchange_segment: str = "IDX_I") -> Optional[Dict]:
        """Get live market quotes for given security IDs.

        Uses Dhan's /marketfeed/quote endpoint.
        """
        cached = cache.get(f"dhan_quote_{','.join(security_ids)}")
        if cached:
            return cached

        data = await self._post("/marketfeed/quote", {
            exchange_segment: security_ids,
        })

        if data:
            cache.set(f"dhan_quote_{','.join(security_ids)}", data, ttl=10)

        return data

    async def get_ltp(self, security_ids: List[str], exchange_segment: str = "IDX_I") -> Optional[Dict]:
        """Get last traded price for securities."""
        cached = cache.get(f"dhan_ltp_{','.join(security_ids)}")
        if cached:
            return cached

        data = await self._post("/marketfeed/ltp", {
            exchange_segment: security_ids,
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

    async def fetch_nifty50(self) -> Dict[str, Any]:
        """Fetch Nifty 50 index quote via Dhan."""
        data = await self.get_ltp([NIFTY_50_SECURITY_ID])
        if data and "data" in data:
            for item in data["data"]:
                if str(item.get("security_id")) == NIFTY_50_SECURITY_ID:
                    ltp = item.get("LTP", 0) or item.get("last_price", 0)
                    return {
                        "last": ltp,
                        "open": item.get("open", 0),
                        "high": item.get("high", 0),
                        "low": item.get("low", 0),
                        "prev_close": item.get("close", 0),
                        "change": ltp - (item.get("close", 0) or ltp),
                        "change_pct": ((ltp - (item.get("close", 0) or ltp)) / (item.get("close", 0) or 1)) * 100 if item.get("close") else 0,
                    }
        return None

    async def fetch_bank_nifty(self) -> Dict[str, Any]:
        """Fetch Bank Nifty index quote via Dhan."""
        data = await self.get_ltp([BANK_NIFTY_SECURITY_ID])
        if data and "data" in data:
            for item in data["data"]:
                if str(item.get("security_id")) == BANK_NIFTY_SECURITY_ID:
                    ltp = item.get("LTP", 0) or item.get("last_price", 0)
                    prev = item.get("close", 0) or ltp
                    return {
                        "last": ltp,
                        "open": item.get("open", 0),
                        "high": item.get("high", 0),
                        "low": item.get("low", 0),
                        "prev_close": prev,
                        "change": ltp - prev,
                        "change_pct": ((ltp - prev) / prev) * 100 if prev else 0,
                    }
        return None

    async def fetch_india_vix(self) -> Dict[str, Any]:
        """Fetch India VIX via Dhan."""
        data = await self.get_ltp([INDIA_VIX_SECURITY_ID])
        if data and "data" in data:
            for item in data["data"]:
                if str(item.get("security_id")) == INDIA_VIX_SECURITY_ID:
                    current = item.get("LTP", 0) or item.get("last_price", 15.0)
                    prev = item.get("close", 0) or current
                    return {
                        "current": current,
                        "change": current - prev,
                        "change_pct": ((current - prev) / prev) * 100 if prev else 0,
                    }
        return None

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
    ) -> list:
        """Fetch daily OHLCV candles from Dhan /charts/historical.

        Args:
            security_id: Dhan security ID — "13" (Nifty), "25" (BankNifty), "26" (VIX)
            from_date: "YYYY-MM-DD"
            to_date: "YYYY-MM-DD"

        Returns:
            List of {"date": "YYYY-MM-DD", "open": float, "high": float,
                     "low": float, "close": float, "volume": int}

        Raises:
            DhanFetchError: If Dhan returns non-200 or response is missing OHLCV arrays.
        """
        client = await self._ensure_client()
        url = f"{DHAN_BASE}/charts/historical"
        payload = {
            "securityId": security_id,
            "exchangeSegment": "IDX_I",
            "instrument": "INDEX",
            "interval": "D",
            "fromDate": from_date,
            "toDate": to_date,
        }
        try:
            resp = await client.post(url, json=payload)
        except Exception as exc:
            raise DhanFetchError(f"HTTP request failed for securityId={security_id}: {exc}") from exc

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
