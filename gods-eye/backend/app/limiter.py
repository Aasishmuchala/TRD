"""Shared rate limiter instance for use across the application."""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Create a singleton limiter instance
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
