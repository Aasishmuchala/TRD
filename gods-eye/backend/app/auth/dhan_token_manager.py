"""Dhan Token Manager — automatic token generation and renewal.

Supports two strategies:
  1. TOTP-based generation: Generates a fresh 24h token using your PIN + TOTP secret.
     Requires: DHAN_CLIENT_ID, DHAN_PIN, DHAN_TOTP_SECRET
  2. Token renewal: Extends an active token by 24h via /v2/RenewToken.
     Requires: DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN (still valid)

The manager runs a background task that renews the token every 20 hours
(4 hours before expiry) to ensure uninterrupted access.

Setup:
  1. Enable TOTP on your Dhan account (Settings → Security → Enable TOTP)
  2. When scanning the QR code, also copy the TOTP secret string
  3. Set these env vars:
     - DHAN_CLIENT_ID=1111059578
     - DHAN_PIN=123456          (your 6-digit Dhan PIN)
     - DHAN_TOTP_SECRET=JBSWY3DPEHPK3PXP  (base32 TOTP seed from setup)

Dhan API docs: https://dhanhq.co/docs/v2/authentication/
"""

import asyncio
import hmac
import hashlib
import struct
import time
import os
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger("gods_eye.dhan_token")

# ─── TOTP Generator (RFC 6238) ──────────────────────────────────────────────
# Pure Python — no pyotp dependency needed.

def _generate_totp(secret_base32: str, time_step: int = 30, digits: int = 6, counter_offset: int = 0) -> str:
    """Generate a TOTP code from a base32-encoded secret.

    Implements RFC 6238 (TOTP) with RFC 4226 (HOTP) underneath.
    Compatible with Google Authenticator, Authy, etc.

    Args:
        counter_offset: Adjust the time counter by ±N steps.
                        0 = current, -1 = previous step, +1 = next step.
    """
    import base64

    # Decode base32 secret (handle padding)
    secret_base32 = secret_base32.upper().replace(" ", "")
    padding = 8 - len(secret_base32) % 8
    if padding != 8:
        secret_base32 += "=" * padding
    key = base64.b32decode(secret_base32)

    # Time counter (with optional offset for clock-skew tolerance)
    counter = int(time.time()) // time_step + counter_offset
    counter_bytes = struct.pack(">Q", counter)

    # HMAC-SHA1
    hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()

    # Dynamic truncation (RFC 4226 §5.4)
    offset = hmac_hash[-1] & 0x0F
    code = struct.unpack(">I", hmac_hash[offset:offset + 4])[0] & 0x7FFFFFFF

    return str(code % (10 ** digits)).zfill(digits)


def _jwt_exp_utc(token: str) -> Optional[datetime]:
    """Best-effort decode of an unsigned JWT's `exp` claim → UTC datetime."""
    if not token or token.count(".") != 2:
        return None
    try:
        import base64
        import json as _json
        _, body_b64, _ = token.split(".")
        body_b64 += "=" * (-len(body_b64) % 4)
        claims = _json.loads(base64.urlsafe_b64decode(body_b64))
        exp = claims.get("exp")
        if exp:
            return datetime.utcfromtimestamp(int(exp))
    except Exception:
        pass
    return None


# ─── Token Manager ───────────────────────────────────────────────────────────

class DhanTokenManager:
    """Manages Dhan API access tokens with automatic renewal."""

    GENERATE_URL = "https://auth.dhan.co/app/generateAccessToken"
    RENEW_URL = "https://api.dhan.co/v2/RenewToken"
    RENEWAL_INTERVAL_HOURS = 20  # Legacy fallback interval
    # IST times to renew token (HH:MM).  Twice daily keeps the 24h token
    # alive: once before market open, once after close.
    RENEWAL_SCHEDULE_IST = ["08:30", "16:00"]

    # Number of consecutive failed self-heal attempts before we page out via
    # the webhook.  3 cycles at the market-hours interval (5 min) = 15 min
    # of broken data feed — enough to be real, not noise.
    SELF_HEAL_ALERT_THRESHOLD = 3

    def __init__(self):
        self.client_id: str = os.getenv("DHAN_CLIENT_ID", "")
        self.pin: str = os.getenv("DHAN_PIN", "")
        self.totp_secret: str = os.getenv("DHAN_TOTP_SECRET", "")
        self._access_token: str = os.getenv("DHAN_ACCESS_TOKEN", "")
        # Seed expiry from JWT if possible — so load-from-disk can compare freshness.
        self._token_expiry: Optional[datetime] = _jwt_exp_utc(self._access_token)
        self._renewal_task: Optional[asyncio.Task] = None
        self._http: Optional[httpx.AsyncClient] = None
        # Self-heal alerting state. Tracks consecutive health-check cycles
        # where the reactive renewal failed — used to escalate to an
        # outbound webhook alert after N strikes so silent failure stops
        # being silent.  Deduplicated per incident: one alert, one all-clear.
        self._consecutive_self_heal_failures: int = 0
        self._alert_sent_for_current_incident: bool = False

        # Disk persistence path — lives on the Railway volume by default so
        # renewed tokens survive container restarts/redeploys. A fresher token
        # on disk always wins over the env-var token at boot time.
        self.token_store_path: str = os.getenv(
            "DHAN_TOKEN_STORE_PATH", "/app/data/dhan_token.json"
        )
        self._load_persisted_token()

    # ─── Disk persistence (survives container restarts) ───────────────────

    def _load_persisted_token(self) -> None:
        """Load token from disk if the file is present and fresher than env var.

        Compared against ``self._token_expiry`` (set from env JWT's ``exp`` claim).
        A disk token that is already expired is ignored.
        """
        try:
            import json as _json
            if not os.path.exists(self.token_store_path):
                return
            with open(self.token_store_path, "r") as f:
                data = _json.load(f)
            disk_token = (data.get("access_token") or "").strip()
            if not disk_token:
                return

            disk_exp: Optional[datetime] = None
            exp_str = data.get("expires_at")
            if exp_str:
                try:
                    disk_exp = datetime.fromisoformat(exp_str.replace("Z", ""))
                except Exception:
                    disk_exp = None
            if disk_exp is None:
                disk_exp = _jwt_exp_utc(disk_token)

            # Skip if already expired.
            if disk_exp and datetime.utcnow() >= disk_exp:
                logger.info(
                    "Persisted Dhan token at %s is expired (%s) — ignoring",
                    self.token_store_path, disk_exp,
                )
                return

            # Prefer disk token if fresher than env var's JWT exp.
            env_exp = self._token_expiry
            if env_exp and disk_exp and disk_exp <= env_exp:
                logger.info(
                    "Persisted Dhan token (exp %s) is not fresher than env var (exp %s) — keeping env var",
                    disk_exp, env_exp,
                )
                return

            logger.info(
                "Loaded Dhan token from disk %s (expires %s)",
                self.token_store_path, disk_exp,
            )
            self._access_token = disk_token
            self._token_expiry = disk_exp
            # Keep os.environ in sync so any subprocess / re-init picks it up.
            os.environ["DHAN_ACCESS_TOKEN"] = disk_token
        except Exception as e:
            logger.warning("Failed to load persisted Dhan token: %s", e)

    def _save_token_to_disk(self) -> None:
        """Atomically write current token + expiry to disk. Silent on failure."""
        if not self._access_token:
            return
        try:
            import json as _json
            directory = os.path.dirname(self.token_store_path) or "."
            os.makedirs(directory, exist_ok=True)
            payload = {
                "access_token": self._access_token,
                "expires_at": (self._token_expiry.isoformat() + "Z")
                              if self._token_expiry else None,
                "saved_at": datetime.utcnow().isoformat() + "Z",
            }
            tmp = self.token_store_path + ".tmp"
            with open(tmp, "w") as f:
                _json.dump(payload, f)
            os.replace(tmp, self.token_store_path)
            logger.info(
                "Persisted Dhan token to %s (expires %s)",
                self.token_store_path, self._token_expiry,
            )
        except Exception as e:
            logger.warning("Failed to persist Dhan token to disk: %s", e)

    @property
    def access_token(self) -> str:
        return self._access_token

    @property
    def is_totp_configured(self) -> bool:
        return bool(self.client_id and self.pin and self.totp_secret)

    @property
    def is_token_valid(self) -> bool:
        if not self._access_token:
            return False
        if self._token_expiry and datetime.utcnow() >= self._token_expiry:
            return False
        return True

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=10.0))
        return self._http

    # ─── Strategy 1: TOTP-based generation ────────────────────────────────

    async def generate_token_via_totp(self) -> bool:
        """Generate a fresh 24h access token using PIN + TOTP.

        Tries 3 TOTP codes to handle clock skew:
          1. Current time step (offset 0)
          2. Previous time step (offset -1) — covers server clock ahead
          3. Wait 35s + next time step (offset 0 recalculated) — covers
             boundary conditions where current code just expired

        Returns True on success, False on failure.
        """
        if not self.is_totp_configured:
            logger.warning("TOTP not configured: need DHAN_CLIENT_ID, DHAN_PIN, DHAN_TOTP_SECRET")
            return False

        client = await self._ensure_client()

        # Try current TOTP, then previous step, then wait for fresh step
        attempts = [
            ("current", 0, False),
            ("previous", -1, False),
            ("fresh (after 35s wait)", 0, True),
        ]

        for label, offset, should_wait in attempts:
            if should_wait:
                # Wait for the next TOTP window to open (max 35s)
                import asyncio as _aio
                wait_secs = 35 - (int(time.time()) % 30)
                if wait_secs < 5:
                    wait_secs += 30
                logger.info(f"TOTP {label}: waiting {wait_secs}s for fresh window...")
                await _aio.sleep(wait_secs)

            totp_code = _generate_totp(self.totp_secret, counter_offset=offset)
            logger.info(f"Generating Dhan token via TOTP ({label}) for client {self.client_id}...")

            try:
                resp = await client.post(
                    self.GENERATE_URL,
                    json={
                        "dhanClientId": self.client_id,
                        "pin": self.pin,
                        "totp": totp_code,
                    },
                )

                if resp.status_code == 200:
                    data = resp.json()
                    new_token = data.get("accessToken")
                    if new_token:
                        self._access_token = new_token
                        expiry_str = data.get("expiryTime")
                        if expiry_str:
                            try:
                                self._token_expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
                            except Exception:
                                self._token_expiry = datetime.utcnow() + timedelta(hours=24)
                        else:
                            self._token_expiry = datetime.utcnow() + timedelta(hours=24)

                        os.environ["DHAN_ACCESS_TOKEN"] = new_token
                        logger.info(f"Dhan token generated successfully ({label}). Expires: {self._token_expiry}")
                        return True
                    else:
                        logger.warning(f"Dhan TOTP ({label}) response missing accessToken: {data}")
                else:
                    body = resp.text[:200]
                    logger.warning(f"Dhan TOTP ({label}) failed: HTTP {resp.status_code} — {body}")

                    # Rate limit: "Token can be generated once every 2 minutes"
                    if "once every" in body.lower() or resp.status_code == 429:
                        import asyncio as _aio
                        logger.info("Dhan rate-limited — waiting 130s before retry...")
                        await _aio.sleep(130)

            except Exception as e:
                logger.error(f"Dhan TOTP ({label}) error: {e}")

        logger.error("Dhan TOTP: all 3 attempts failed")
        return False

    # ─── Strategy 2: Renew existing token ─────────────────────────────────

    async def renew_token(self) -> bool:
        """Renew the current active token for another 24 hours.

        Uses GET /v2/RenewToken with access-token + dhanClientId headers.
        The old token is invalidated and a new one is returned.
        Only works if the current token is still valid (not expired).
        Returns True on success, False on failure.
        """
        if not self._access_token or not self.client_id:
            logger.warning("Cannot renew: no active token or client ID")
            return False

        client = await self._ensure_client()
        try:
            resp = await client.get(
                self.RENEW_URL,
                headers={
                    "access-token": self._access_token,
                    "dhanClientId": self.client_id,
                },
            )

            if resp.status_code != 200:
                logger.warning(f"Dhan token renewal failed: HTTP {resp.status_code} — {resp.text[:200]}")
                return False

            data = resp.json()
            new_token = data.get("token") or data.get("accessToken")
            if not new_token:
                logger.error(f"Dhan renewal response missing token: {data}")
                return False

            self._access_token = new_token
            os.environ["DHAN_ACCESS_TOKEN"] = new_token

            # Parse expiry from response or default to 24h
            expiry_str = data.get("expiryTime")
            if expiry_str:
                try:
                    self._token_expiry = datetime.fromisoformat(expiry_str)
                except Exception:
                    self._token_expiry = datetime.utcnow() + timedelta(hours=24)
            else:
                self._token_expiry = datetime.utcnow() + timedelta(hours=24)

            logger.info(f"Dhan token renewed successfully. Expires: {self._token_expiry}")
            self._save_token_to_disk()
            return True

        except Exception as e:
            logger.error(f"Dhan token renewal error: {e}")
            return False

    # ─── Combined: Try renew, fallback to TOTP ────────────────────────────

    async def ensure_valid_token(self) -> bool:
        """Ensure we have a valid token. Try renewal first, then TOTP generation."""
        # If token looks valid and expiry is >4h away, skip
        if self.is_token_valid and self._token_expiry:
            remaining = (self._token_expiry - datetime.utcnow()).total_seconds() / 3600
            if remaining > 4:
                return True

        # Try renewing first (cheaper, no TOTP needed)
        if self._access_token:
            if await self.renew_token():
                return True

        # Fallback to TOTP generation
        if self.is_totp_configured:
            return await self.generate_token_via_totp()

        logger.error("No valid token and no way to generate one. "
                     "Set DHAN_TOTP_SECRET + DHAN_PIN for auto-generation.")
        return False

    # ─── Background renewal loop ──────────────────────────────────────────

    @staticmethod
    def _utc_now_ist() -> datetime:
        """Current time in IST (UTC+5:30) as a naive datetime."""
        return datetime.utcnow() + timedelta(hours=5, minutes=30)

    def _seconds_until_next_slot(self) -> float:
        """Return seconds until the next scheduled renewal slot (IST).

        If all today's slots have passed, target the first slot tomorrow.
        Adds a 30-second jitter to avoid thundering-herd on restart.
        """
        now_ist = self._utc_now_ist()
        slots = []
        for t_str in self.RENEWAL_SCHEDULE_IST:
            h, m = map(int, t_str.split(":"))
            slot = now_ist.replace(hour=h, minute=m, second=0, microsecond=0)
            if slot <= now_ist:
                slot += timedelta(days=1)
            slots.append(slot)
        next_slot = min(slots)
        delta = (next_slot - now_ist).total_seconds()
        return max(delta, 60)  # at least 60s

    async def _renewal_loop(self):
        """Background task that renews the token at scheduled IST times.

        Schedule: 08:30 IST (before market open) and 16:00 IST (after close).
        Also renews immediately on startup, then sleeps until next slot.
        """
        # ── Immediate renewal on startup ──
        try:
            logger.info("Dhan token: startup renewal attempt...")
            success = await self.ensure_valid_token()
            if success:
                logger.info("Dhan token: startup renewal succeeded")
            else:
                logger.warning("Dhan token: startup renewal failed — will retry at next slot")
        except Exception as e:
            logger.error(f"Dhan token: startup renewal error: {e}")

        # ── Scheduled loop ──
        while True:
            try:
                wait_secs = self._seconds_until_next_slot()
                next_ist = self._utc_now_ist() + timedelta(seconds=wait_secs)
                logger.info(
                    "Dhan token: next renewal at ~%s IST (in %.0f min)",
                    next_ist.strftime("%H:%M"), wait_secs / 60,
                )
                await asyncio.sleep(wait_secs)

                logger.info("Scheduled Dhan token renewal (%s IST)...",
                            self._utc_now_ist().strftime("%H:%M"))
                success = await self.ensure_valid_token()
                if not success:
                    # Retry every 15 min up to 3 times
                    for attempt in range(1, 4):
                        logger.warning(
                            "Token renewal failed, retry %d/3 in 15 min...", attempt
                        )
                        await asyncio.sleep(900)
                        if await self.ensure_valid_token():
                            break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Token renewal loop error: {e}")
                await asyncio.sleep(300)  # Wait 5 min on error

    # ─── Proactive Health Check ─────────────────────────────────────────

    HEALTH_CHECK_INTERVAL = 300       # 5 minutes during market hours
    HEALTH_CHECK_INTERVAL_OFF = 900   # 15 minutes outside market hours
    HEALTH_CHECK_INTERVAL_BROKEN = 60 # 60 seconds while data is not flowing

    async def _health_check_loop(self):
        """Background task that proactively verifies Dhan data is flowing.

        Normal cadence: 5 min during market hours, 15 min off-hours.
        Broken cadence: 60 s while data is not flowing (breaker open, 5xx, 401,
        timeouts, etc.). On ANY non-healthy state the loop forces a token
        renewal via Strategy 2 and resets the circuit breaker on success —
        so a stuck data feed unblocks itself within ~60 seconds without
        waiting for the next scheduled (08:30 / 16:00 IST) slot.
        """
        await asyncio.sleep(60)  # Wait 1 min after startup before first check
        while True:
            try:
                now_ist = self._utc_now_ist()
                hour = now_ist.hour
                # More frequent checks during/around market hours (8:30-16:30)
                is_market_time = 8 <= hour <= 16 and now_ist.weekday() < 5
                normal_interval = (
                    self.HEALTH_CHECK_INTERVAL if is_market_time
                    else self.HEALTH_CHECK_INTERVAL_OFF
                )

                from app.data.dhan_client import dhan_client
                from app.alerts import send_alert
                result = await dhan_client.health_check()
                healthy = bool(result.get("healthy"))
                reason = result.get("reason", "")

                if healthy:
                    logger.debug("Dhan health check OK")
                    # Recovery: if we paged out earlier this incident, send
                    # an all-clear once data is flowing again.
                    if self._alert_sent_for_current_incident:
                        try:
                            await send_alert(
                                title="Dhan self-heal recovered",
                                message=(
                                    f"Data feed healthy again after "
                                    f"{self._consecutive_self_heal_failures} "
                                    f"failed cycles."
                                ),
                                severity="info",
                            )
                        except Exception as e:
                            logger.error("Recovery alert failed: %s", e)
                    self._consecutive_self_heal_failures = 0
                    self._alert_sent_for_current_incident = False
                    interval = normal_interval
                elif reason == "not_configured":
                    interval = normal_interval  # nothing to fix
                else:
                    # ── Any non-healthy, configured state → force renewal ──
                    # Covers: token_expired (401), circuit_breaker_open,
                    # http_5xx, http_403, network timeouts/errors, etc.
                    logger.warning(
                        "Dhan data not flowing (reason=%s, failures=%s) — "
                        "forcing token renewal to self-heal",
                        reason, result.get("consecutive_failures", "n/a"),
                    )
                    renewed = False
                    try:
                        renewed = await self.ensure_valid_token()
                    except Exception as e:
                        logger.error("Forced renewal raised: %s", e)

                    if renewed:
                        # Unstick the breaker immediately so the next request
                        # actually reaches Dhan with the fresh token rather
                        # than being short-circuited by the cooldown.
                        try:
                            dhan_client._breaker.reset()
                        except Exception:
                            pass
                        # Persist the refreshed token to the Railway volume
                        # so a container restart mid-recovery keeps the gain.
                        try:
                            self._save_token_to_disk()
                        except Exception:
                            pass
                        logger.info(
                            "Dhan self-heal succeeded (reason was %s) — "
                            "breaker reset, token persisted.", reason,
                        )
                        # Do NOT reset the strike counter here — wait for
                        # the next healthy probe as proof the fix stuck.
                    else:
                        self._consecutive_self_heal_failures += 1
                        logger.warning(
                            "Dhan self-heal FAILED (reason was %s, "
                            "consecutive=%d) — will retry in %ds.",
                            reason,
                            self._consecutive_self_heal_failures,
                            self.HEALTH_CHECK_INTERVAL_BROKEN,
                        )
                        # Escalate once per incident when we cross the
                        # threshold. Do not spam on every subsequent failure.
                        if (
                            self._consecutive_self_heal_failures
                            >= self.SELF_HEAL_ALERT_THRESHOLD
                            and not self._alert_sent_for_current_incident
                        ):
                            try:
                                await send_alert(
                                    title="Dhan self-heal failing",
                                    message=(
                                        f"reason={reason}, "
                                        f"{self._consecutive_self_heal_failures} "
                                        f"consecutive cycles.\n"
                                        f"Manual action: check "
                                        f"GET /api/admin/dhan/status and, if "
                                        f"needed, POST /api/admin/dhan/renew."
                                    ),
                                    severity="critical",
                                )
                                self._alert_sent_for_current_incident = True
                            except Exception as e:
                                logger.error("Self-heal alert failed: %s", e)
                    # Poll fast until data is flowing again
                    interval = self.HEALTH_CHECK_INTERVAL_BROKEN

                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Health check loop error: %s", e)
                await asyncio.sleep(300)

    def start_auto_renewal(self):
        """Start the background token renewal + health check tasks."""
        if self._renewal_task is None or self._renewal_task.done():
            self._renewal_task = asyncio.create_task(self._renewal_loop())
            schedule_str = ", ".join(self.RENEWAL_SCHEDULE_IST)
            logger.info(f"Dhan token auto-renewal started (schedule: {schedule_str} IST + startup)")

        # Start health check as a separate task
        if not hasattr(self, '_health_task') or self._health_task is None or self._health_task.done():
            self._health_task = asyncio.create_task(self._health_check_loop())
            logger.info("Dhan proactive health-check started (every 5 min during market hours)")

    def stop_auto_renewal(self):
        """Stop the background token renewal + health check tasks."""
        if self._renewal_task and not self._renewal_task.done():
            self._renewal_task.cancel()
            logger.info("Dhan token auto-renewal stopped")
        if hasattr(self, '_health_task') and self._health_task and not self._health_task.done():
            self._health_task.cancel()
            logger.info("Dhan health-check stopped")

    async def shutdown(self):
        """Clean up resources."""
        self.stop_auto_renewal()
        if self._http:
            await self._http.aclose()
            self._http = None


# Global singleton
dhan_token_manager = DhanTokenManager()
