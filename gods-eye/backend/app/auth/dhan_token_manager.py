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

def _generate_totp(secret_base32: str, time_step: int = 30, digits: int = 6) -> str:
    """Generate a TOTP code from a base32-encoded secret.

    Implements RFC 6238 (TOTP) with RFC 4226 (HOTP) underneath.
    Compatible with Google Authenticator, Authy, etc.
    """
    import base64

    # Decode base32 secret (handle padding)
    secret_base32 = secret_base32.upper().replace(" ", "")
    padding = 8 - len(secret_base32) % 8
    if padding != 8:
        secret_base32 += "=" * padding
    key = base64.b32decode(secret_base32)

    # Time counter
    counter = int(time.time()) // time_step
    counter_bytes = struct.pack(">Q", counter)

    # HMAC-SHA1
    hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()

    # Dynamic truncation (RFC 4226 §5.4)
    offset = hmac_hash[-1] & 0x0F
    code = struct.unpack(">I", hmac_hash[offset:offset + 4])[0] & 0x7FFFFFFF

    return str(code % (10 ** digits)).zfill(digits)


# ─── Token Manager ───────────────────────────────────────────────────────────

class DhanTokenManager:
    """Manages Dhan API access tokens with automatic renewal."""

    GENERATE_URL = "https://auth.dhan.co/app/generateAccessToken"
    RENEW_URL = "https://api.dhan.co/v2/RenewToken"
    RENEWAL_INTERVAL_HOURS = 20  # Renew 4 hours before 24h expiry

    def __init__(self):
        self.client_id: str = os.getenv("DHAN_CLIENT_ID", "")
        self.pin: str = os.getenv("DHAN_PIN", "")
        self.totp_secret: str = os.getenv("DHAN_TOTP_SECRET", "")
        self._access_token: str = os.getenv("DHAN_ACCESS_TOKEN", "")
        self._token_expiry: Optional[datetime] = None
        self._renewal_task: Optional[asyncio.Task] = None
        self._http: Optional[httpx.AsyncClient] = None

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

        Returns True on success, False on failure.
        """
        if not self.is_totp_configured:
            logger.warning("TOTP not configured: need DHAN_CLIENT_ID, DHAN_PIN, DHAN_TOTP_SECRET")
            return False

        totp_code = _generate_totp(self.totp_secret)
        logger.info(f"Generating Dhan token via TOTP for client {self.client_id}...")

        client = await self._ensure_client()
        try:
            resp = await client.post(
                self.GENERATE_URL,
                params={
                    "dhanClientId": self.client_id,
                    "pin": self.pin,
                    "totp": totp_code,
                },
            )

            if resp.status_code != 200:
                logger.error(f"Dhan TOTP token generation failed: HTTP {resp.status_code} — {resp.text[:200]}")
                return False

            data = resp.json()
            new_token = data.get("accessToken")
            if not new_token:
                logger.error(f"Dhan response missing accessToken: {data}")
                return False

            self._access_token = new_token
            # Parse expiry or default to 24h from now
            expiry_str = data.get("expiryTime")
            if expiry_str:
                try:
                    self._token_expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
                except Exception:
                    self._token_expiry = datetime.utcnow() + timedelta(hours=24)
            else:
                self._token_expiry = datetime.utcnow() + timedelta(hours=24)

            # Update env var so DhanClient picks it up
            os.environ["DHAN_ACCESS_TOKEN"] = new_token

            logger.info(f"Dhan token generated successfully. Expires: {self._token_expiry}")
            return True

        except Exception as e:
            logger.error(f"Dhan TOTP token generation error: {e}")
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

    async def _renewal_loop(self):
        """Background task that renews the token every 20 hours."""
        while True:
            try:
                await asyncio.sleep(self.RENEWAL_INTERVAL_HOURS * 3600)
                logger.info("Scheduled Dhan token renewal...")
                success = await self.ensure_valid_token()
                if not success:
                    # Retry in 30 min
                    logger.warning("Token renewal failed, retrying in 30 minutes...")
                    await asyncio.sleep(1800)
                    await self.ensure_valid_token()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Token renewal loop error: {e}")
                await asyncio.sleep(300)  # Wait 5 min on error

    def start_auto_renewal(self):
        """Start the background token renewal task."""
        if self._renewal_task is None or self._renewal_task.done():
            self._renewal_task = asyncio.create_task(self._renewal_loop())
            logger.info(f"Dhan token auto-renewal started (every {self.RENEWAL_INTERVAL_HOURS}h)")

    def stop_auto_renewal(self):
        """Stop the background token renewal task."""
        if self._renewal_task and not self._renewal_task.done():
            self._renewal_task.cancel()
            logger.info("Dhan token auto-renewal stopped")

    async def shutdown(self):
        """Clean up resources."""
        self.stop_auto_renewal()
        if self._http:
            await self._http.aclose()
            self._http = None


# Global singleton
dhan_token_manager = DhanTokenManager()
