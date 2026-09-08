"""File-backed checkpoints (issue #14) — resumable forecast runs across restarts.

A file-backed LangGraph checkpointer (SQLite) persists the JSON-native state to disk,
so a run interrupted mid-gate can be resumed in a fresh process. `dump_state` also
writes the checkpoint state to a plain JSON file as an audit artifact.
"""

from __future__ import annotations

import json
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver


def file_checkpointer(path: str) -> SqliteSaver:
    """A file-backed checkpointer (SQLite) for a compiled graph."""
    conn = sqlite3.connect(path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()
    return checkpointer


def dump_state(state: dict, path) -> None:
    """Write the JSON-native graph state to a .json file."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, default=str)
