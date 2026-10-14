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


# --- futures mode model routing (PRD-futures.md, Model routing) --------------
#
# Every futures call type defaults to the cheap model. Override one call type with
# `CSG_FUTURES_MODEL_<TYPE>` / `CSG_FUTURES_TEMP_<TYPE>` (e.g. CSG_FUTURES_MODEL_GENERATE=
# deepseek-v4-pro) to compare tiers on the same exploration.

CHEAP_MODEL = "deepseek-v4-flash"

FUTURES_CALLS: dict[str, tuple[str, float]] = {
    "generate": (CHEAP_MODEL, 0.9),  # an order of projections; siblings should diverge
    "fork": (CHEAP_MODEL, 0.9),
    "axes": (CHEAP_MODEL, 0.5),  # Matrix axis proposals
    "narrative": (CHEAP_MODEL, 0.5),  # Matrix scenario narratives
    "classify": (CHEAP_MODEL, 0.0),  # lens tags
    "summarize": (CHEAP_MODEL, 0.0),  # a reference into one line
    "suggest": (CHEAP_MODEL, 0.0),  # anchor suggestions for a goal
    "ground": (CHEAP_MODEL, 0.3),  # Ground this
}


def futures_model(call_type: str) -> tuple[str, float]:
    """The (model, temperature) for one futures call type, env-overridable."""
    model, temperature = FUTURES_CALLS[call_type]
    key = call_type.upper()
    model = os.environ.get(f"CSG_FUTURES_MODEL_{key}") or model
    temp = os.environ.get(f"CSG_FUTURES_TEMP_{key}")
    return model, float(temp) if temp else temperature


def futures_cap(name: str, default: int) -> int:
    """A generation cap (`CSG_FUTURES_<NAME>`), tunable once the system runs."""
    value = os.environ.get(f"CSG_FUTURES_{name.upper()}")
    return int(value) if value else default


def brave_api_key() -> str | None:
    """The Brave Search API key (BRAVE_API_KEY in .env), or None when unset —
    discovery then searches Wikipedia full-text only."""
    return os.environ.get("BRAVE_API_KEY") or None
