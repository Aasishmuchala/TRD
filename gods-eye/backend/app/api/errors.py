"""Structured error responses and safe error handling."""

import logging
import uuid
from typing import Optional
from pydantic import BaseModel
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    """Structured error response format."""
    error: str
    message: str
    request_id: str


def safe_error_response(
    status_code: int,
    error_code: str,
    message: str,
    request_id: Optional[str] = None,
) -> HTTPException:
    """Create a safe HTTPException with sanitized message.

    Server-side errors are logged with full details, but clients receive
    generic safe messages to avoid exposing internal implementation details.

    Args:
        status_code: HTTP status code
        error_code: Application error code (e.g., "SIMULATION_FAILED")
        message: User-safe message to send to client
        request_id: Optional request ID for tracking (auto-generated if not provided)

    Returns:
        HTTPException with sanitized detail
    """
    req_id = request_id or str(uuid.uuid4())

    # Return safe detail string (will be serialized as plain text by FastAPI)
    safe_detail = f'{{"error": "{error_code}", "message": "{message}", "request_id": "{req_id}"}}'

    return HTTPException(status_code=status_code, detail=safe_detail)


def log_error_safely(
    error: Exception,
    context: str = "",
    request_id: Optional[str] = None,
) -> str:
    """Log full error details server-side while returning a safe request ID.

    Args:
        error: The exception that occurred
        context: Additional context about what was being done
        request_id: Optional request ID for tracking

    Returns:
        request_id for logging to client
    """
    req_id = request_id or str(uuid.uuid4())
    log_msg = f"[{req_id}] Error in {context}: {type(error).__name__}: {str(error)}"
    logger.exception(log_msg)
    return req_id
