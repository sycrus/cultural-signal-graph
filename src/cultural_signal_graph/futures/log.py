"""The per-exploration operation log (ADR-0008).

`log.jsonl` holds every operation in order; `cursor.json` says how many of them are
in effect. State is the replay of the first `cursor` ops, so undo/redo only move the
cursor. Appending after an undo drops the redo tail first, like an editor.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class OperationLog:
    def __init__(self, directory: Path):
        self.dir = Path(directory)
        self._log = self.dir / "log.jsonl"
        self._cursor = self.dir / "cursor.json"

    def exists(self) -> bool:
        return self._log.is_file()

    def ops(self) -> list[dict]:
        """Every op in the file, including any redo tail past the cursor."""
        if not self._log.is_file():
            return []
        lines = self._log.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def cursor(self) -> int:
        if self._cursor.is_file():
            return json.loads(self._cursor.read_text(encoding="utf-8"))["cursor"]
        return len(self.ops())

    def active(self) -> list[dict]:
        """The ops in effect: the prefix up to the cursor."""
        return self.ops()[: self.cursor()]

    def append(self, op: dict, author: str = "system") -> dict:
        """Record an op (dropping any redo tail) and advance the cursor past it."""
        ops = self.active()
        op = {
            "seq": len(ops),
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "author": author,
            **op,
        }
        ops.append(op)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._log.write_text(
            "".join(json.dumps(o, ensure_ascii=False) + "\n" for o in ops), encoding="utf-8"
        )
        self._set_cursor(len(ops))
        return op

    def can_undo(self) -> bool:
        # the create op is the exploration itself; it is never undone
        return self.cursor() > 1

    def can_redo(self) -> bool:
        return self.cursor() < len(self.ops())

    def undo(self) -> None:
        if not self.can_undo():
            raise ValueError("nothing to undo")
        self._set_cursor(self.cursor() - 1)

    def redo(self) -> None:
        if not self.can_redo():
            raise ValueError("nothing to redo")
        self._set_cursor(self.cursor() + 1)

    def _set_cursor(self, cursor: int) -> None:
        self._cursor.write_text(json.dumps({"cursor": cursor}), encoding="utf-8")
