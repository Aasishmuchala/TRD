"""Persist runtime config changes back to the .env file.

The Settings page lets users update LLM provider / API key / model from the UI.
For that to survive a backend restart, we patch the running ``config`` object
*and* rewrite the relevant keys in ``backend/.env``. This is a small,
single-user tool — we don't need a secret manager here, but we DO need to make
sure secrets never round-trip back through the API in plaintext.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict

# .env lives next to run.py (one level above app/)
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# Keys we're willing to write through the API. Everything else stays manual.
_ALLOWED_KEYS = {
    "GODS_EYE_LLM_PROVIDER",
    "LLM_API_KEY",
    "GODS_EYE_MODEL",
    "GODS_EYE_MOCK",
    "LLM_INFERENCE_URL",
    # Dhan credentials — once set, the TOTP secret enables permanent
    # auto-renewal so the user never has to paste an access token again.
    "DHAN_CLIENT_ID",
    "DHAN_PIN",
    "DHAN_TOTP_SECRET",
    "DHAN_ACCESS_TOKEN",
}


def mask_api_key(key: str) -> str:
    """Return a masked preview of an API key — last 4 chars only."""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}…{key[-4:]}"


def _read_env() -> list[str]:
    if not _ENV_PATH.exists():
        return []
    return _ENV_PATH.read_text(encoding="utf-8").splitlines()


def write_env_updates(updates: Dict[str, str]) -> None:
    """Atomically update a set of KEY=value pairs inside ``backend/.env``.

    Keys already present are replaced in place. Missing keys are appended at
    the bottom. Unknown keys are silently ignored — this is the allow-list
    that keeps the settings endpoint from being a generic env writer.
    """
    filtered = {k: v for k, v in updates.items() if k in _ALLOWED_KEYS}
    if not filtered:
        return

    lines = _read_env()
    seen: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        m = re.match(r"^\s*([A-Z0-9_]+)\s*=", line)
        if m and m.group(1) in filtered:
            key = m.group(1)
            new_lines.append(f"{key}={filtered[key]}")
            seen.add(key)
        else:
            new_lines.append(line)

    for key, value in filtered.items():
        if key not in seen:
            new_lines.append(f"{key}={value}")

    _ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    _ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # Also update the live process environment so the running backend picks
    # up the new values immediately (config object is mutated by the caller).
    for key, value in filtered.items():
        os.environ[key] = value
