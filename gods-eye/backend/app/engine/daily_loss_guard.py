"""DailyLossGuard — in-memory daily max-loss gate for paper trading.

Tracks cumulative realised paper losses for the current trading day.
"Day" = calendar date in Asia/Kolkata timezone (IST = UTC+5:30).
Resets automatically when the IST calendar date changes.

This is a paper trading guard — no real money, no DB persistence.
State lives in the server process only; restarts reset it.

No locks needed — single worker gunicorn (established decision: [v1.0]).
"""

from datetime import datetime, timezone, timedelta, date as _date_type

from app.config import config

# IST offset constant
_IST = timezone(timedelta(hours=5, minutes=30))


def _today_ist() -> _date_type:
    """Return the current calendar date in Asia/Kolkata (IST)."""
    return datetime.now(tz=_IST).date()


class DailyLossGuard:
    """Tracks cumulative paper losses and blocks signals once the daily limit is hit.

    The guard auto-resets when the IST calendar date rolls over.

    Parameters
    ----------
    max_daily_loss : float
        Maximum cumulative loss allowed per trading day (in index points).
        Once cumulative loss reaches this value, ``is_blocked()`` returns True.
    """

    def __init__(self, max_daily_loss: float) -> None:
        self.max_daily_loss = max_daily_loss
        self._date: _date_type | None = None
        self._cumulative_loss: float = 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _maybe_reset(self) -> None:
        """Reset cumulative loss when the IST calendar date has changed."""
        today = _today_ist()
        if self._date != today:
            self._cumulative_loss = 0.0
            self._date = today

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_blocked(self) -> bool:
        """Return True if cumulative daily loss has reached the configured limit."""
        self._maybe_reset()
        return self._cumulative_loss >= self.max_daily_loss

    def record_loss(self, loss_points: float) -> None:
        """Add loss_points to the cumulative total.

        Only non-negative values are recorded — negative inputs (i.e. profits)
        are silently ignored so the guard never unwinds past zero.

        Parameters
        ----------
        loss_points : float
            Points lost on the most recent trade. Must be >= 0 to take effect.
        """
        self._maybe_reset()
        self._cumulative_loss += max(0.0, loss_points)

    def cumulative_loss(self) -> float:
        """Return the cumulative loss accumulated so far today (IST)."""
        self._maybe_reset()
        return self._cumulative_loss

    def reset(self) -> None:
        """Force-reset the guard to zero for today's IST date.

        Intended for use in tests or manual operator overrides.
        """
        self._cumulative_loss = 0.0
        self._date = _today_ist()


# ---------------------------------------------------------------------------
# Module-level singleton — initialised from config at import time.
# ---------------------------------------------------------------------------

daily_loss_guard = DailyLossGuard(max_daily_loss=config.RISK_MAX_DAILY_LOSS)
