"""FastAPI authentication middleware using OAuth device code flow tokens."""

import hmac
import logging
import os
from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.auth.device_auth import get_auth_manager
from app.config import config

logger = logging.getLogger("gods_eye.auth")

security = HTTPBearer(auto_error=False)


async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """FastAPI dependency that validates Bearer token authentication.

    Checks for Authorization: Bearer <token> header and verifies the token
    matches the stored valid token from device OAuth flow.

    Args:
        credentials: Optional HTTPAuthCredentials from Authorization header

    Returns:
        The valid token string if authenticated

    Raises:
        HTTPException 401: If no valid token or MOCK_MODE disabled auth
    """
    # If MOCK_MODE is enabled, bypass auth entirely
    if config.MOCK_MODE:
        return "mock_token"

    # Direct API key mode: backend already has the LLM key configured,
    # still require a non-empty Bearer token (single-user tool — any token accepted)
    if config.LLM_API_KEY:
        if not credentials or not credentials.credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Authorization header",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return credentials.credentials

    # If no credentials provided, return 401
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get the token from the Authorization header
    token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify token matches stored valid token
    auth_manager = get_auth_manager()
    valid_token = await auth_manager.get_valid_token()

    if not valid_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No valid authentication token stored. Please login first.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if token != valid_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Token is valid
    return token


# ─── Admin-endpoint gate ────────────────────────────────────────────────────
#
# The regular ``require_auth`` accepts any non-empty Bearer when LLM_API_KEY
# is set (single-user tool convenience). That's fine for /simulate and
# read-only routes but NOT for /admin/* — those can rotate the Dhan token,
# wipe caches, and reseed the DB.  Layer a second secret on top.

_ADMIN_SECRET_ENV = "GODS_EYE_ADMIN_SECRET"
_ADMIN_HEADER_NAME = "X-Admin-Secret"


def _load_admin_secret() -> str:
    """Read the admin secret fresh on each request.

    Reading at call-time (not import-time) means a Railway env-var update
    takes effect on the next request without a restart.
    """
    return os.getenv(_ADMIN_SECRET_ENV, "").strip()


async def require_admin_auth(
    x_admin_secret: Optional[str] = Header(None, alias=_ADMIN_HEADER_NAME),
) -> None:
    """FastAPI dependency enforcing the admin shared secret.

    Stacks on top of ``require_auth`` — caller must also present a valid
    Bearer.  Uses ``hmac.compare_digest`` for constant-time comparison to
    avoid timing side channels.

    Fail-closed behaviour:
        * secret env unset AND MOCK_MODE → allow (local dev convenience)
        * secret env unset AND NOT MOCK_MODE → 503 (misconfiguration, do
          not silently open admin endpoints)
        * header missing or mismatched → 401

    Raises:
        HTTPException 503 if the env var is not configured in prod.
        HTTPException 401 if the header is missing or wrong.
    """
    expected = _load_admin_secret()

    if not expected:
        if config.MOCK_MODE:
            return None
        logger.error(
            "Admin endpoint hit but %s env var not set — denying.",
            _ADMIN_SECRET_ENV,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Admin endpoints are disabled: {_ADMIN_SECRET_ENV} is not "
                "configured on the server."
            ),
        )

    provided = (x_admin_secret or "").strip()
    if not provided or not hmac.compare_digest(provided, expected):
        # Don't log the provided value — it could be a near-miss of the
        # real secret.  Only log that an attempt happened.
        logger.warning("Admin auth failed: header missing or mismatched")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing or invalid {_ADMIN_HEADER_NAME} header",
        )

    return None
