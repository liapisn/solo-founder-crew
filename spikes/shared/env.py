"""Minimal .env loader for the spike runners.

Reads KEY=VALUE pairs from a file (default: ./.env) into os.environ.
Existing environment variables take precedence — we never clobber a
real export. Silently no-ops if the file does not exist, so the default
mock path keeps working with no setup.

No python-dotenv dependency: a .env file is simple enough that 15 lines
of stdlib handle it. Adding a dep just for this would be ceremony.
"""
from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path | str = ".env") -> bool:
    """Load KEY=VALUE pairs from *path* into os.environ.

    Returns True if the file was read (whether or not it had any keys),
    False if it didn't exist. Existing env vars are not overwritten.
    """
    p = Path(path)
    if not p.is_file():
        return False
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
    return True
