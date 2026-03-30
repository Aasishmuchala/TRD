"""In-memory cache with TTL for market data — avoids hammering NSE."""

import time
from typing import Any, Optional, Dict


class MarketCache:
    """Simple TTL-based in-memory cache.

    TTL defaults:
        - spot prices / VIX: 300s (5 min)
        - FII/DII flows:    1800s (30 min)
        - options chain:    7200s (2 hr)
        - sector indices:   300s (5 min)
    """

    DEFAULT_TTLS: Dict[str, int] = {
        "spot": 300,
        "vix": 300,
        "fii_dii": 1800,
        "options": 7200,
        "sectors": 300,
        "breadth": 300,
    }

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        # {key: {"value": ..., "expires_at": float}}

    def get(self, key: str) -> Optional[Any]:
        """Return cached value if not expired, else None."""
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() > entry["expires_at"]:
            del self._store[key]
            return None
        return entry["value"]

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Cache a value with TTL in seconds."""
        self._store[key] = {
            "value": value,
            "expires_at": time.time() + ttl,
        }

    def invalidate(self, key: str) -> None:
        """Remove a specific key."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._store.clear()

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        now = time.time()
        total = len(self._store)
        alive = sum(1 for e in self._store.values() if now < e["expires_at"])
        return {
            "total_entries": total,
            "alive_entries": alive,
            "expired_entries": total - alive,
        }


# Global singleton
cache = MarketCache()
