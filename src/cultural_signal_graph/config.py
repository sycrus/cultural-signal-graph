"""Environment config: load a `.env` file into `os.environ` (e.g. DEEPSEEK_API_KEY).

A minimal, dependency-free `.env` reader: `KEY=value` lines, `#` comments, and blank
lines. Existing environment variables are never overridden.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: str | Path | None = None) -> None:
    """Load KEY=value pairs from a .env file into os.environ (no override)."""
    dotenv_path = Path(path) if path is not None else Path.cwd() / ".env"
    if not dotenv_path.is_file():
        return
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value
