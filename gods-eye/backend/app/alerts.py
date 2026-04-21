"""Outbound webhook for production alerts.

Silent no-op unless ``GODS_EYE_ALERT_WEBHOOK`` is set. Payload is shaped to
work for Slack Incoming Webhooks (reads ``text``), Discord Webhooks (reads
``content``), and ntfy.sh (reads ``message``) — each service picks the
field it recognises and ignores the rest. For any other service, the same
body is also in ``text`` and plain-JSON parsers can use ``title``.

Usage:
    from app.alerts import send_alert
    await send_alert(
        title="Dhan self-heal failing",
        message="reason=circuit_breaker_open, 3 consecutive cycles",
        severity="critical",
    )
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger("gods_eye.alerts")


_SEVERITY_PREFIX = {
    "info": "[INFO]",
    "warning": "[WARN]",
    "critical": "[CRIT]",
}


async def send_alert(
    title: str,
    message: str,
    severity: str = "warning",
) -> bool:
    """Send a production alert to the configured webhook.

    Args:
        title: Short headline, used as the notification title.
        message: Full context (reason, counter, etc.) — multi-line OK.
        severity: ``info`` | ``warning`` | ``critical``. Only affects the
            visual prefix; delivery is identical.

    Returns:
        True on success or when no webhook is configured (not an error —
        alerting is opt-in). False on network/HTTP failure.
    """
    url = os.getenv("GODS_EYE_ALERT_WEBHOOK", "").strip()
    if not url:
        logger.debug("No GODS_EYE_ALERT_WEBHOOK set, skipping alert: %s", title)
        return True

    prefix = _SEVERITY_PREFIX.get(severity, "[WARN]")
    body = f"{prefix} {title}\n{message}"

    # Send a single payload with all the common field names — Slack picks
    # ``text``, Discord picks ``content``, ntfy picks ``message``, and any
    # JSON-aware logger gets the structured ``title`` + ``severity``.
    payload = {
        "text": body,
        "content": body,
        "message": body,
        "title": title,
        "severity": severity,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code < 300:
                logger.info("Alert sent: [%s] %s", severity, title)
                return True
            logger.error(
                "Alert webhook returned HTTP %d: %s",
                resp.status_code,
                resp.text[:200],
            )
            return False
    except Exception as e:
        logger.error("Alert webhook failed: %s (title=%s)", e, title)
        return False
