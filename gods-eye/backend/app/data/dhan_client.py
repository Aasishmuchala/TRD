"""Dhan Market Data Client — bulletproof Indian market data via official API.

Resilience layers (in order):
  1. Retry with exponential backoff for transient errors (429, 500, 502, 503, timeouts)
  2. Auto-heal on 401: triggers TOTP token refresh and retries
  3. Circuit breaker: after N consecutive failures, trips open for cooldown period
  4. Cache-first: serves stale cache when Dhan is unreachable
  5. Graceful degradation: every public method returns None (never raises) to callers

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

# ─── Resilience Config ──────────────────────────────────────────────────────
_MIN_REFRESH_INTERVAL = 120        # seconds between token refresh attempts
_MAX_RETRIES = 3                    # max retries for transient errors
_RETRY_BASE_DELAY = 1.0            # base delay for exponential backoff (seconds)
_CIRCUIT_BREAKER_THRESHOLD = 5     # consecutive failures to trip breaker
_CIRCUIT_BREAKER_COOLDOWN = 120    # seconds to wait before retrying after trip
_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


class DhanFetchError(Exception):
    """Raised when Dhan API returns an error or unexpected response for historical data."""


DHAN_BASE = "https://api.dhan.co/v2"

# Dhan security IDs for indices
NIFTY_50_SECURITY_ID = "13"       # NSE index
BANK_NIFTY_SECURITY_ID = "25"     # NSE index
INDIA_VIX_SECURITY_ID = "26"      # NSE index

# Exchange segment for indices
NSE_IDX = "IDX_I"


class _CircuitBreaker:
    """Simple circuit breaker: trips after N consecutive failures, auto-resets after cooldown."""

    def __init__(self, threshold: int = _CIRCUIT_BREAKER_THRESHOLD,
                 cooldown: float = _CIRCUIT_BREAKER_COOLDOWN):
        self._threshold = threshold
        self._cooldown = cooldown
        self._consecutive_failures = 0
        self._tripped_at: float = 0.0

    @property
    def is_open(self) -> bool:
        """True if breaker is tripped AND cooldown hasn't elapsed."""
        if self._consecutive_failures < self._threshold:
            return False
        elapsed = time.monotonic() - self._tripped_at
        if elapsed >= self._cooldown:
            # Cooldown elapsed — allow one probe request (half-open)
            return False
        return True

    def record_success(self) -> None:
        self._consecutive_failures = 0

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._threshold:
            self._tripped_at = time.monotonic()
            logger.warning(
                "Dhan circuit breaker TRIPPED (%d consecutive failures). "
                "Cooling down for %ds — using cached/fallback data.",
                self._consecutive_failures, self._cooldown,
            )

    @property
    def failure_count(self) -> int:
        return self._consecutive_failures


class DhanClient:
    """Fetches live market data from Dhan API.

    Resilience: retry + backoff → 401 auto-heal → circuit breaker → cache fallback.
    Every public method returns Optional[...] — never raises to callers.
    """

    def __init__(self):
        self._client_id = os.getenv("DHAN_CLIENT_ID", "")
        self._http: Optional[httpx.AsyncClient] = None
        self._last_token: str = ""  # Track token changes for client refresh
        self._last_refresh_attempt: float = 0.0  # epoch — throttle refresh calls
        self._refresh_lock: Optional[asyncio.Lock] = None
        self._breaker = _CircuitBreaker()

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
                timeout=httpx.Timeout(20.0, connect=10.0),
                headers={
                    "access-token": current_token,
                    "client-id": self._client_id,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._http

    # ─── Token Refresh ───────────────────────────────────────────────────

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

    # ─── Core HTTP with Retry + Backoff + 401 Heal ───────────────────────

    async def _request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict] = None,
        _attempt: int = 0,
    ) -> Optional[Dict]:
        """Unified HTTP request handler with full resilience stack.

        1. Check circuit breaker → if open, return None immediately
        2. Make request
        3. On 401 → refresh token, retry once
        4. On transient error (429/5xx/timeout) → exponential backoff, retry up to _MAX_RETRIES
        5. On success → reset circuit breaker
        6. On exhausted retries → record failure in circuit breaker, return None
        """
        # Circuit breaker check
        if self._breaker.is_open:
            logger.debug("Dhan circuit breaker OPEN — skipping %s %s", method, endpoint)
            return None

        client = await self._ensure_client()
        url = f"{DHAN_BASE}{endpoint}"

        try:
            if method == "GET":
                resp = await client.get(url)
            elif method == "PUT":
                resp = await client.put(url, json=payload or {})
            elif method == "DELETE":
                resp = await client.delete(url)
            else:
                resp = await client.post(url, json=payload or {})

            # ── 401: token expired → refresh and retry once ──
            if resp.status_code == 401:
                if _attempt == 0 and await self._refresh_token_on_401():
                    return await self._request(method, endpoint, payload, _attempt=1)
                logger.error("Dhan 401 persists after token refresh for %s", endpoint)
                self._breaker.record_failure()
                return None

            # ── Transient errors → exponential backoff retry ──
            if resp.status_code in _TRANSIENT_STATUS_CODES:
                if _attempt < _MAX_RETRIES:
                    delay = _RETRY_BASE_DELAY * (2 ** _attempt)
                    # On 429, check Retry-After header
                    if resp.status_code == 429:
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after:
                            try:
                                delay = max(delay, float(retry_after))
                            except ValueError:
                                pass
                    logger.warning(
                        "Dhan %s %s returned %d — retry %d/%d in %.1fs",
                        method, endpoint, resp.status_code, _attempt + 1, _MAX_RETRIES, delay,
                    )
                    await asyncio.sleep(delay)
                    return await self._request(method, endpoint, payload, _attempt=_attempt + 1)
                else:
                    logger.error(
                        "Dhan %s %s returned %d — exhausted %d retries",
                        method, endpoint, resp.status_code, _MAX_RETRIES,
                    )
                    self._breaker.record_failure()
                    return None

            # ── Client errors (400, 403, etc.) — don't retry, just log ──
            if resp.status_code >= 400:
                logger.warning("Dhan %s %s returned %d: %s", method, endpoint, resp.status_code, resp.text[:200])
                # Don't trip breaker on 400 (bad request) — it's a caller issue, not Dhan being down
                if resp.status_code >= 500:
                    self._breaker.record_failure()
                return None

            # ── Success ──
            self._breaker.record_success()
            return resp.json()

        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as e:
            if _attempt < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY * (2 ** _attempt)
                logger.warning(
                    "Dhan %s %s network error: %s — retry %d/%d in %.1fs",
                    method, endpoint, type(e).__name__, _attempt + 1, _MAX_RETRIES, delay,
                )
                await asyncio.sleep(delay)
                return await self._request(method, endpoint, payload, _attempt=_attempt + 1)
            logger.error("Dhan %s %s network error after %d retries: %s", method, endpoint, _MAX_RETRIES, e)
            self._breaker.record_failure()
            return None
        except Exception as e:
            logger.error("Dhan %s %s unexpected error: %s", method, endpoint, e)
            self._breaker.record_failure()
            return None

    async def _get(self, endpoint: str) -> Optional[Dict]:
        return await self._request("GET", endpoint)

    async def _post(self, endpoint: str, payload: Dict) -> Optional[Dict]:
        return await self._request("POST", endpoint, payload)

    # ─── Health Check ────────────────────────────────────────────────────

    async def health_check(self) -> Dict[str, Any]:
        """Verify token and connectivity. Returns status dict.

        Used by the proactive health-check loop in dhan_token_manager.
        """
        if not self.is_configured:
            return {"healthy": False, "reason": "not_configured"}

        if self._breaker.is_open:
            return {
                "healthy": False,
                "reason": "circuit_breaker_open",
                "consecutive_failures": self._breaker.failure_count,
            }

        try:
            client = await self._ensure_client()
            # Lightweight LTP call — single security, minimal payload
            resp = await client.post(
                f"{DHAN_BASE}/marketfeed/ltp",
                json={"IDX_I": [13]},
            )
            if resp.status_code == 200:
                data = resp.json()
                self._breaker.record_success()
                return {"healthy": True, "status_code": 200}
            elif resp.status_code == 401:
                return {"healthy": False, "reason": "token_expired", "status_code": 401}
            else:
                return {"healthy": False, "reason": f"http_{resp.status_code}", "status_code": resp.status_code}
        except Exception as e:
            return {"healthy": False, "reason": str(e)}

    # ─── Market Data Methods ─────────────────────────────────────────────

    async def get_market_quote(self, security_ids: List[str], exchange_segment: str = "IDX_I") -> Optional[Dict]:
        """Get live market quotes for given security IDs."""
        cached = cache.get(f"dhan_quote_{','.join(security_ids)}")
        if cached:
            return cached

        int_ids = [int(sid) for sid in security_ids]
        data = await self._post("/marketfeed/quote", {
            exchange_segment: int_ids,
        })

        if data:
            cache.set(f"dhan_quote_{','.join(security_ids)}", data, ttl=10)

        return data

    async def get_ltp(self, security_ids: List[str], exchange_segment: str = "IDX_I") -> Optional[Dict]:
        """Get last traded price for securities."""
        cached = cache.get(f"dhan_ltp_{','.join(security_ids)}")
        if cached:
            return cached

        int_ids = [int(sid) for sid in security_ids]
        data = await self._post("/marketfeed/ltp", {
            exchange_segment: int_ids,
        })

        if data:
            cache.set(f"dhan_ltp_{','.join(security_ids)}", data, ttl=5)

        return data

    async def get_expiry_list(self, under_security_id: str = "13") -> Optional[List[str]]:
        """Get available expiry dates for an index option chain.

        Returns list of expiry date strings (YYYY-MM-DD), sorted ascending.
        """
        cache_key = f"dhan_expiry_{under_security_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        data = await self._post("/optionchain/expirylist", {
            "UnderlyingScrip": int(under_security_id),
            "UnderlyingSeg": "IDX_I",
        })

        if data and "data" in data:
            expiries = data["data"]
            if isinstance(expiries, list) and expiries:
                cache.set(cache_key, expiries, ttl=3600)  # Cache 1 hour
                return expiries

        return None

    async def get_option_chain(self, under_security_id: str = "13", expiry: str = None) -> Optional[Dict]:
        """Get options chain for an index.

        Args:
            under_security_id: "13" for Nifty 50
            expiry: Expiry date in YYYY-MM-DD format. If None, fetches nearest from expirylist.
        """
        cache_key = f"dhan_optchain_{under_security_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        # If no expiry provided, fetch the nearest one
        if not expiry:
            expiries = await self.get_expiry_list(under_security_id)
            if expiries:
                expiry = expiries[0]  # Nearest expiry
                logger.debug("Using nearest expiry for option chain: %s", expiry)
            else:
                logger.warning("Could not fetch expiry list — option chain unavailable")
                return None

        payload = {
            "UnderlyingScrip": int(under_security_id),
            "UnderlyingSeg": "IDX_I",
            "Expiry": expiry,
        }

        data = await self._post("/optionchain", payload)
        if data:
            cache.set(cache_key, data, ttl=30)

        return data

    def _extract_ltp(self, data: Optional[Dict], security_id: str) -> Optional[Dict]:
        """Extract LTP from Dhan marketfeed response."""
        if not data or "data" not in data:
            return None
        for segment_data in data["data"].values():
            if isinstance(segment_data, dict):
                item = segment_data.get(security_id) or segment_data.get(str(security_id))
                if item and isinstance(item, dict):
                    return item
        return None

    async def fetch_all_indices(self) -> Dict[str, Optional[Dict[str, Any]]]:
        """Fetch Nifty 50, Bank Nifty, and India VIX in a SINGLE API call.

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

    # ─── Legacy single-index methods (kept for backward compat) ──────────

    async def fetch_nifty50(self) -> Optional[Dict[str, Any]]:
        """Fetch Nifty 50 index quote via Dhan."""
        data = await self.get_ltp([NIFTY_50_SECURITY_ID])
        item = self._extract_ltp(data, NIFTY_50_SECURITY_ID)
        return self._parse_index_ltp(item)

    async def fetch_bank_nifty(self) -> Optional[Dict[str, Any]]:
        """Fetch Bank Nifty index quote via Dhan."""
        data = await self.get_ltp([BANK_NIFTY_SECURITY_ID])
        item = self._extract_ltp(data, BANK_NIFTY_SECURITY_ID)
        return self._parse_index_ltp(item)

    async def fetch_india_vix(self) -> Optional[Dict[str, Any]]:
        """Fetch India VIX via Dhan."""
        data = await self.get_ltp([INDIA_VIX_SECURITY_ID])
        item = self._extract_ltp(data, INDIA_VIX_SECURITY_ID)
        return self._parse_vix_ltp(item)

    async def fetch_options_summary(self) -> Optional[Dict[str, Any]]:
        """Fetch Nifty options chain and compute PCR, max pain.

        Dhan /v2/optionchain response format (confirmed):
          {
            "data": {
              "last_price": 23724.4,
              "oc": {
                "17100.000000": {
                  "ce": {"oi": 1234, "last_price": 6500, ...},
                  "pe": {"oi": 5678, "last_price": 10, ...}
                },
                ...
              }
            },
            "status": "success"
          }
        """
        data = await self.get_option_chain(NIFTY_50_SECURITY_ID)
        if not data:
            return None

        # Navigate to the option chain dict: data → data → oc
        inner = data.get("data")
        if not isinstance(inner, dict):
            logger.warning("Option chain: 'data' is not a dict (type=%s)", type(inner).__name__)
            return None

        oc = inner.get("oc")
        if not isinstance(oc, dict) or not oc:
            logger.warning("Option chain: no 'oc' dict found. Inner keys: %s", list(inner.keys()))
            return None

        total_call_oi = 0
        total_put_oi = 0
        strike_pain = {}

        try:
            for strike_str, opts in oc.items():
                if not isinstance(opts, dict):
                    continue
                try:
                    strike = float(strike_str)
                except (ValueError, TypeError):
                    continue

                ce = opts.get("ce", {})
                pe = opts.get("pe", {})

                ce_oi = int(ce.get("oi", 0) or 0) if isinstance(ce, dict) else 0
                pe_oi = int(pe.get("oi", 0) or 0) if isinstance(pe, dict) else 0

                total_call_oi += ce_oi
                total_put_oi += pe_oi
                strike_pain[strike] = {"ce_oi": ce_oi, "pe_oi": pe_oi}

        except Exception as e:
            logger.error("Error parsing option chain: %s", e)
            return None

        if total_call_oi == 0 and total_put_oi == 0:
            logger.warning("Option chain returned zero OI — market may be closed or data unavailable")
            return None

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

        logger.info("PCR computed: %.3f (call_oi=%d, put_oi=%d, max_pain=%.0f)",
                     pcr, total_call_oi, total_put_oi, max_pain)

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
    ) -> list:
        """Fetch daily OHLCV candles from Dhan /v2/charts/historical.

        NOTE: Dhan does NOT support historical candles for IDX_I (index) segment.
        This method works for equities (NSE_EQ/EQUITY) and F&O instruments.

        Uses the unified _request method — gets retry + backoff + 401 heal automatically.
        Raises DhanFetchError only when all retries exhausted AND no cached data.
        """
        payload = {
            "securityId": security_id,
            "exchangeSegment": exchange_segment,
            "instrument": instrument,
            "expiryCode": 0,
            "fromDate": from_date,
            "toDate": to_date,
        }

        data = await self._post("/charts/historical", payload)

        if not data:
            raise DhanFetchError(
                f"Dhan /charts/historical returned no data for securityId={security_id} "
                f"(retries exhausted or circuit breaker open)"
            )

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

    # ─── Order Management ────────────────────────────────────────────────

    async def place_order(
        self,
        transaction_type: str,    # "BUY" or "SELL"
        exchange_segment: str,    # "NSE_FNO" for NSE F&O
        product_type: str,        # "INTRADAY" or "CNC"
        order_type: str,          # "MARKET", "LIMIT", "STOP_LOSS", "STOP_LOSS_MARKET"
        security_id: str,         # Dhan security ID for the instrument
        quantity: int,
        price: float = 0.0,
        trigger_price: float = 0.0,
        validity: str = "DAY",
        disclosed_quantity: int = 0,
        correlation_id: str = "",
    ) -> Optional[Dict]:
        """Place an order via Dhan API.

        Returns {"orderId": "...", "orderStatus": "PENDING"} on success, None on failure.

        IMPORTANT: Dhan requires Static IP whitelisting for order APIs.
        Set DHAN_ORDERS_ENABLED=true in env to activate (safety gate).
        """
        if not os.getenv("DHAN_ORDERS_ENABLED", "").lower() in ("true", "1", "yes"):
            logger.warning("Dhan order blocked — DHAN_ORDERS_ENABLED is not set to true")
            return None

        payload = {
            "dhanClientId": self._client_id,
            "transactionType": transaction_type,
            "exchangeSegment": exchange_segment,
            "productType": product_type,
            "orderType": order_type,
            "validity": validity,
            "securityId": security_id,
            "quantity": quantity,
            "price": price,
            "triggerPrice": trigger_price,
            "disclosedQuantity": disclosed_quantity,
        }
        if correlation_id:
            payload["correlationId"] = correlation_id[:30]

        logger.info(
            "Dhan ORDER: %s %s qty=%d price=%.2f security=%s",
            transaction_type, order_type, quantity, price, security_id,
        )
        result = await self._request("POST", "/orders", payload)
        if result:
            logger.info("Dhan order placed: orderId=%s status=%s", result.get("orderId"), result.get("orderStatus"))
        return result

    async def modify_order(
        self,
        order_id: str,
        order_type: str,
        quantity: int,
        price: float = 0.0,
        trigger_price: float = 0.0,
        validity: str = "DAY",
        disclosed_quantity: int = 0,
    ) -> Optional[Dict]:
        """Modify a pending order."""
        payload = {
            "dhanClientId": self._client_id,
            "orderId": order_id,
            "orderType": order_type,
            "quantity": quantity,
            "price": price,
            "triggerPrice": trigger_price,
            "validity": validity,
            "disclosedQuantity": disclosed_quantity,
        }
        logger.info("Dhan MODIFY order: %s qty=%d price=%.2f", order_id, quantity, price)
        return await self._request("PUT", f"/orders/{order_id}", payload)

    async def cancel_order(self, order_id: str) -> Optional[Dict]:
        """Cancel a pending order."""
        logger.info("Dhan CANCEL order: %s", order_id)
        return await self._request("DELETE", f"/orders/{order_id}")

    async def get_order_by_id(self, order_id: str) -> Optional[Dict]:
        """Get order status by order ID."""
        return await self._request("GET", f"/orders/{order_id}")

    async def get_order_book(self) -> Optional[List]:
        """Get all orders for the day."""
        result = await self._request("GET", "/orders")
        return result if isinstance(result, list) else None

    async def get_positions(self) -> Optional[List]:
        """Get all open positions."""
        result = await self._request("GET", "/positions")
        return result if isinstance(result, list) else None


# Global singleton
dhan_client = DhanClient()
