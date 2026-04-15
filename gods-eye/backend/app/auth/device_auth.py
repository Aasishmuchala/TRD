"""OAuth Device Code Flow authentication — Codex-style login.

Implements the device authorization grant (RFC 8628) for OpenAI-compatible APIs.
User gets a link + code, enters it in browser, and the system polls until authorized.

Flow:
  1. POST /device/code → returns device_code, user_code, verification_uri
  2. User opens verification_uri, enters user_code
  3. System polls /token until approved or expired
  4. Tokens stored in ~/.gods-eye/auth.json with auto-refresh

Adapted from NousResearch/hermes-agent auth pattern.
"""

import os
import json
import time
import asyncio
import logging
import socket
import hashlib
import base64
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta

import httpx
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────
AUTH_DIR = Path.home() / ".gods-eye"
AUTH_FILE = AUTH_DIR / "auth.json"
POLL_INTERVAL_CAP = 1  # seconds
ACCESS_TOKEN_REFRESH_SKEW = 120  # refresh 2 min before expiry


# ─── Encryption Helpers ───────────────────────────────────────────────────
def _get_encryption_key() -> bytes:
    """Derive machine-specific encryption key from hostname + username.

    The key is derived from a hash of the current user and hostname,
    preventing casual token theft if the auth.json file is accessed
    on a different machine.

    Returns:
        Fernet key (bytes) derived from hostname + username
    """
    try:
        username = os.getlogin()
    except (OSError, FileNotFoundError):
        # Fallback if getlogin() fails
        username = os.environ.get("USER", os.environ.get("USERNAME", "unknown"))

    hostname = socket.gethostname()
    machine_id = f"{username}@{hostname}".encode()

    # SHA256 hash (32 bytes) → base64-encode for Fernet key
    key_hash = hashlib.sha256(machine_id).digest()
    key = base64.urlsafe_b64encode(key_hash)  # Fernet requires 32-byte base64
    return key


def _encrypt_token(token: str) -> str:
    """Encrypt a token string.

    Args:
        token: Plain-text token

    Returns:
        Encrypted token (bytes, base64-encoded)
    """
    if not token:
        return token
    cipher = Fernet(_get_encryption_key())
    encrypted = cipher.encrypt(token.encode())
    return encrypted.decode()  # Return as string


def _decrypt_token(encrypted_token: str) -> str:
    """Decrypt a token string.

    Args:
        encrypted_token: Encrypted token (base64-encoded)

    Returns:
        Plain-text token

    Raises:
        InvalidToken: If decryption fails
    """
    if not encrypted_token:
        return encrypted_token
    cipher = Fernet(_get_encryption_key())
    decrypted = cipher.decrypt(encrypted_token.encode())
    return decrypted.decode()

# Provider presets
PROVIDERS = {
    "openai": {
        "name": "OpenAI (Codex)",
        "auth_base": "https://auth0.openai.com",
        "device_code_endpoint": "https://auth0.openai.com/oauth/device/code",
        "token_endpoint": "https://auth0.openai.com/oauth/token",
        "inference_base": "https://api.openai.com/v1",
        "client_id": "pdlLIX2Y72MIl2rhLhTE9VV9bN905kBh",  # OpenAI CLI client ID
        "scope": "openid profile email offline_access",
        "audience": "https://api.openai.com/v1",
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "default_model": "o4-mini",
    },
    "nous": {
        "name": "Nous Research",
        "auth_base": "https://portal.nousresearch.com",
        "device_code_endpoint": "https://portal.nousresearch.com/api/oauth/device/code",
        "token_endpoint": "https://portal.nousresearch.com/api/oauth/token",
        "inference_base": "https://inference-api.nousresearch.com/v1",
        "client_id": "hermes-cli",
        "scope": "inference:mint_agent_key",
        "audience": "",
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "default_model": "Hermes-3-Llama-3.1-70B",
    },
    "anthropic": {
        "name": "Anthropic (OpusCode)",
        "auth_base": "",
        "device_code_endpoint": "",
        "token_endpoint": "",
        "inference_base": "https://api.anthropic.com",
        "client_id": "",
        "scope": "",
        "audience": "",
        "grant_type": "",
        "default_model": "claude-opus-4-6",
        "api_format": "anthropic",  # Uses /v1/messages instead of /chat/completions
    },
    "custom": {
        "name": "Custom Provider",
        "auth_base": "",
        "device_code_endpoint": "",
        "token_endpoint": "",
        "inference_base": "",
        "client_id": "",
        "scope": "",
        "audience": "",
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "default_model": "",
    },
}


@dataclass
class AuthTokens:
    """Stored auth tokens for a provider."""
    access_token: str = ""
    refresh_token: str = ""
    expires_at: float = 0.0  # Unix timestamp
    id_token: str = ""
    token_type: str = "Bearer"
    provider: str = "openai"

    @property
    def is_expired(self) -> bool:
        return time.time() >= (self.expires_at - ACCESS_TOKEN_REFRESH_SKEW)

    @property
    def is_valid(self) -> bool:
        return bool(self.access_token) and not self.is_expired


@dataclass
class DeviceCodeResponse:
    """Response from device code request."""
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str = ""
    expires_in: int = 600
    interval: int = 5


@dataclass
class AuthState:
    """Full persistent auth state."""
    version: int = 1
    active_provider: str = "openai"
    providers: Dict[str, Dict] = field(default_factory=dict)

    def get_tokens(self, provider: str = None) -> Optional[AuthTokens]:
        p = provider or self.active_provider
        if p in self.providers:
            return AuthTokens(**self.providers[p])
        return None

    def set_tokens(self, tokens: AuthTokens, provider: str = None):
        p = provider or self.active_provider
        self.providers[p] = asdict(tokens)


class DeviceAuthManager:
    """Manages OAuth device code flow for OpenAI-compatible APIs.

    Usage:
        auth = DeviceAuthManager(provider="openai")
        device_info = await auth.request_device_code()
        # Show user: device_info.verification_uri + device_info.user_code
        tokens = await auth.poll_for_token(device_info)
        # Use tokens.access_token for API calls
    """

    def __init__(self, provider: str = "openai"):
        self.provider_key = provider
        self.provider = PROVIDERS.get(provider, PROVIDERS["openai"])
        self._state: Optional[AuthState] = None
        self._client = httpx.AsyncClient(timeout=30.0)
        self._ensure_auth_dir()

    def _ensure_auth_dir(self):
        AUTH_DIR.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> AuthState:
        if self._state:
            return self._state
        if AUTH_FILE.exists():
            try:
                data = json.loads(AUTH_FILE.read_text())
                providers = data.get("providers", {})

                # Decrypt tokens if they're encrypted
                for provider_key, provider_data in providers.items():
                    if isinstance(provider_data, dict):
                        # Try to decrypt access_token
                        if "access_token" in provider_data:
                            try:
                                provider_data["access_token"] = _decrypt_token(provider_data["access_token"])
                            except (InvalidToken, Exception):
                                # Token is not encrypted (old format) or decryption failed
                                # Log a warning but continue with plaintext
                                logger.debug(f"Could not decrypt access_token for {provider_key}, using as-is")

                        # Try to decrypt refresh_token
                        if "refresh_token" in provider_data:
                            try:
                                provider_data["refresh_token"] = _decrypt_token(provider_data["refresh_token"])
                            except (InvalidToken, Exception):
                                logger.debug(f"Could not decrypt refresh_token for {provider_key}, using as-is")

                self._state = AuthState(
                    version=data.get("version", 1),
                    active_provider=data.get("active_provider", "openai"),
                    providers=providers,
                )
            except (json.JSONDecodeError, KeyError):
                self._state = AuthState()
        else:
            self._state = AuthState()
        return self._state

    def _save_state(self):
        if self._state:
            # Create a copy of state with encrypted tokens
            state_dict = asdict(self._state)
            providers = state_dict.get("providers", {})

            for provider_key, provider_data in providers.items():
                if isinstance(provider_data, dict):
                    # Encrypt access_token
                    if "access_token" in provider_data and provider_data["access_token"]:
                        provider_data["access_token"] = _encrypt_token(provider_data["access_token"])

                    # Encrypt refresh_token
                    if "refresh_token" in provider_data and provider_data["refresh_token"]:
                        provider_data["refresh_token"] = _encrypt_token(provider_data["refresh_token"])

            # Write encrypted state to file
            AUTH_FILE.write_text(json.dumps(state_dict, indent=2))

            # Set secure permissions (owner read/write only)
            os.chmod(AUTH_FILE, 0o600)
            logger.debug(f"Saved auth state to {AUTH_FILE} with mode 0o600")

    # ─── Core OAuth Flow ──────────────────────────────────────────────────

    async def request_device_code(self) -> DeviceCodeResponse:
        """Step 1: Request a device code from the auth server.

        Returns device_code + user_code + verification_uri for the user.
        """
        payload = {
            "client_id": self.provider["client_id"],
            "scope": self.provider["scope"],
        }
        if self.provider.get("audience"):
            payload["audience"] = self.provider["audience"]

        response = await self._client.post(
            self.provider["device_code_endpoint"],
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        data = response.json()

        return DeviceCodeResponse(
            device_code=data["device_code"],
            user_code=data["user_code"],
            verification_uri=data.get("verification_uri", data.get("verification_url", "")),
            verification_uri_complete=data.get("verification_uri_complete", ""),
            expires_in=data.get("expires_in", 600),
            interval=data.get("interval", 5),
        )

    async def poll_for_token(
        self,
        device_code_response: DeviceCodeResponse,
        on_status: callable = None,
    ) -> AuthTokens:
        """Step 2: Poll until user approves or code expires.

        Args:
            device_code_response: Response from request_device_code
            on_status: Optional callback(status_str) for progress updates

        Returns:
            AuthTokens on success

        Raises:
            TimeoutError: If device code expires
            RuntimeError: If auth server returns terminal error
        """
        deadline = time.time() + device_code_response.expires_in
        interval = min(device_code_response.interval, POLL_INTERVAL_CAP)

        while time.time() < deadline:
            await asyncio.sleep(interval)

            try:
                payload = {
                    "grant_type": self.provider["grant_type"],
                    "device_code": device_code_response.device_code,
                    "client_id": self.provider["client_id"],
                }

                response = await self._client.post(
                    self.provider["token_endpoint"],
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                data = response.json()

                if response.status_code == 200 and "access_token" in data:
                    # Success!
                    tokens = AuthTokens(
                        access_token=data["access_token"],
                        refresh_token=data.get("refresh_token", ""),
                        expires_at=time.time() + data.get("expires_in", 3600),
                        id_token=data.get("id_token", ""),
                        token_type=data.get("token_type", "Bearer"),
                        provider=self.provider_key,
                    )

                    # Persist
                    state = self._load_state()
                    state.active_provider = self.provider_key
                    state.set_tokens(tokens)
                    self._save_state()

                    if on_status:
                        on_status("authorized")

                    logger.info(f"Device auth successful for {self.provider['name']}")
                    return tokens

                error = data.get("error", "")

                if error == "authorization_pending":
                    if on_status:
                        on_status("waiting")
                    continue

                elif error == "slow_down":
                    interval = min(interval + 1, 30)
                    if on_status:
                        on_status("slow_down")
                    continue

                elif error == "expired_token":
                    raise TimeoutError("Device code expired. Please try again.")

                else:
                    # Terminal error (access_denied, etc.)
                    desc = data.get("error_description", error)
                    raise RuntimeError(f"Auth failed: {desc}")

            except httpx.HTTPError as e:
                logger.warning(f"Network error during polling: {e}")
                await asyncio.sleep(2)
                continue

        raise TimeoutError("Device code expired before user authorized.")

    # ─── Token Management ─────────────────────────────────────────────────

    async def get_valid_token(self) -> Optional[str]:
        """Get a valid access token, refreshing if needed.

        Returns None if not authenticated.
        """
        state = self._load_state()
        tokens = state.get_tokens(self.provider_key)

        if not tokens:
            return None

        if tokens.is_valid:
            return tokens.access_token

        # Try refresh
        if tokens.refresh_token:
            try:
                new_tokens = await self._refresh_token(tokens.refresh_token)
                state.set_tokens(new_tokens)
                self._save_state()
                return new_tokens.access_token
            except Exception as e:
                logger.warning(f"Token refresh failed: {e}")
                return None

        return None

    async def _refresh_token(self, refresh_token: str) -> AuthTokens:
        """Refresh an expired access token."""
        response = await self._client.post(
            self.provider["token_endpoint"],
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.provider["client_id"],
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        data = response.json()

        return AuthTokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", refresh_token),
            expires_at=time.time() + data.get("expires_in", 3600),
            id_token=data.get("id_token", ""),
            token_type=data.get("token_type", "Bearer"),
            provider=self.provider_key,
        )

    # ─── Status Helpers ───────────────────────────────────────────────────

    def get_auth_status(self) -> Dict[str, Any]:
        """Get current authentication status."""
        state = self._load_state()
        tokens = state.get_tokens(self.provider_key)

        if not tokens:
            return {
                "authenticated": False,
                "provider": self.provider_key,
                "provider_name": self.provider["name"],
            }

        return {
            "authenticated": tokens.is_valid,
            "provider": self.provider_key,
            "provider_name": self.provider["name"],
            "expires_at": datetime.fromtimestamp(tokens.expires_at).isoformat() if tokens.expires_at else None,
            "has_refresh_token": bool(tokens.refresh_token),
            "inference_base": self.provider["inference_base"],
            "default_model": self.provider["default_model"],
        }

    def logout(self):
        """Clear stored tokens for current provider."""
        state = self._load_state()
        if self.provider_key in state.providers:
            del state.providers[self.provider_key]
            self._save_state()
            logger.info(f"Logged out from {self.provider['name']}")

    async def close(self):
        await self._client.aclose()


# ─── Global singleton ─────────────────────────────────────────────────────
_auth_manager: Optional[DeviceAuthManager] = None


def get_auth_manager(provider: str = None) -> DeviceAuthManager:
    """Get or create the global auth manager."""
    global _auth_manager
    from app.config import config
    p = provider or config.LLM_PROVIDER
    if _auth_manager is None or _auth_manager.provider_key != p:
        _auth_manager = DeviceAuthManager(provider=p)
    return _auth_manager
