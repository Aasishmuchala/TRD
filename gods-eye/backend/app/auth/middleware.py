"""FastAPI authentication middleware using OAuth device code flow tokens."""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.auth.device_auth import get_auth_manager
from app.config import config

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

    # Accept any non-empty Bearer token when LLM_API_KEY is set
    # (local mode — frontend sends the key entered on Welcome page)
    if credentials and credentials.credentials and config.LLM_API_KEY:
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
