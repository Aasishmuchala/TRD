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

    Values containing newlines, carriage returns, or NUL bytes are rejected
    (raises ValueError). Without this check a request with
    ``llm_api_key="abc\\nDHAN_PIN=1234"`` would inject an arbitrary KEY=value
    line on the next line of the .env file and bypass _ALLOWED_KEYS entirely.

    The file is written via tmp + os.replace() so a crash mid-write cannot
    truncate the existing .env and destroy stored secrets.
    """
    filtered: Dict[str, str] = {}
    for k, v in updates.items():
        if k not in _ALLOWED_KEYS:
            continue
        if v is None:
            continue
        s = str(v)
        if "\n" in s or "\r" in s or "\x00" in s:
            raise ValueError(
                f"Refusing to write {k}: value contains newline / NUL byte "
                f"(possible .env injection attempt)"
            )
        filtered[k] = s
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
    # Atomic write: tmp file in same directory, then os.replace().
    # Same-directory tmp guarantees os.replace is a rename (atomic on POSIX
    # and on NTFS since Python 3.3 via ReplaceFileW).
    tmp_path = _ENV_PATH.with_suffix(_ENV_PATH.suffix + ".tmp")
    tmp_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    os.replace(tmp_path, _ENV_PATH)

    # Also update the live process environment so the running backend picks
    # up the new values immediately (config object is mutated by the caller).
    for key, value in filtered.items():
        os.environ[key] = value
