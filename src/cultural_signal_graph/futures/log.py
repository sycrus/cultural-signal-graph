"""The per-exploration operation log (ADR-0008), stored in SQLite (ADR-0013).

Every operation is kept in order; the cursor says how many of them are in effect. State
is the replay of the first `cursor` ops, so undo/redo only move the cursor. Appending
after an undo drops the redo tail first, like an editor.

Storage: one SQLite database per run (`runs/<run>/oplog.sqlite`) with the ops keyed by
exploration and sequence, plus each exploration's cursor. Append, undo and redo are each
one write transaction, so concurrent writers (phones and a facilitator on the server's
thread pool) are serialised by the database and no write is lost. `log.jsonl` stays the
export / import format; an exploration still stored the old way (`log.jsonl` +
`cursor.json` in its directory) is imported into the database the first time it is
opened, and its old files are left in place, untouched.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_NAME = "oplog.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ops (
    exploration TEXT NOT NULL,
    seq INTEGER NOT NULL,
    op TEXT NOT NULL,
    PRIMARY KEY (exploration, seq)
);
CREATE TABLE IF NOT EXISTS cursors (
    exploration TEXT PRIMARY KEY,
    cursor INTEGER NOT NULL
);
"""


def _who(author: str | dict) -> tuple[str, str | None]:
    """Normalise an author to (name, role). Blank names fall back to 'strategist'."""
    if isinstance(author, dict):
        name, role = author.get("author"), author.get("role")
    else:
        name, role = author, None
    name = (name or "").strip() or "strategist"
    role = (role or "").strip() or None
    return name, role


class OperationLog:
    def __init__(self, directory: Path):
        # `directory` is runs/<run>/explorations/<id>; the database is per run
        self.dir = Path(directory)
        self.exploration = self.dir.name
        self._db = self.dir.parent.parent / DB_NAME

    # --- reads ----------------------------------------------------------------

    def exists(self) -> bool:
        with self._tx(write=False) as db:
            return self._cursor_in(db) is not None

    def ops(self) -> list[dict]:
        """Every op, including any redo tail past the cursor."""
        with self._tx(write=False) as db:
            return self._ops_in(db)

    def cursor(self) -> int:
        with self._tx(write=False) as db:
            return self._cursor_in(db) or 0

    def active(self) -> list[dict]:
        """The ops in effect: the prefix up to the cursor."""
        with self._tx(write=False) as db:
            return self._ops_in(db, limit=self._cursor_in(db) or 0)

    def can_undo(self) -> bool:
        # the create op is the exploration itself; it is never undone
        return self.cursor() > 1

    def can_redo(self) -> bool:
        with self._tx(write=False) as db:
            return (self._cursor_in(db) or 0) < self._count_in(db)

    # --- writes (one transaction each) -----------------------------------------

    def append(self, op: dict, author: str | dict = "system") -> dict:
        """Record an op (dropping any redo tail) and advance the cursor past it.

        `author` is a name, or {"author": name, "role": role}: who made the op, or for
        a model op, who triggered it (the model call itself is on the op)."""
        name, role = _who(author)
        self.dir.mkdir(parents=True, exist_ok=True)  # exports and uploads live beside it
        with self._tx() as db:
            cursor = self._cursor_in(db) or 0
            db.execute("DELETE FROM ops WHERE exploration = ? AND seq >= ?", (self.exploration, cursor))
            op = {
                "seq": cursor,
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "author": name,
                **({"author_role": role} if role else {}),
                **op,
            }
            db.execute(
                "INSERT INTO ops (exploration, seq, op) VALUES (?, ?, ?)",
                (self.exploration, cursor, json.dumps(op, ensure_ascii=False)),
            )
            self._set_cursor_in(db, cursor + 1)
        return op

    def undo(self) -> None:
        with self._tx() as db:
            cursor = self._cursor_in(db) or 0
            if cursor <= 1:
                raise ValueError("nothing to undo")
            self._set_cursor_in(db, cursor - 1)

    def redo(self) -> None:
        with self._tx() as db:
            cursor = self._cursor_in(db) or 0
            if cursor >= self._count_in(db):
                raise ValueError("nothing to redo")
            self._set_cursor_in(db, cursor + 1)

    def import_ops(self, ops: list[dict]) -> None:
        """Write a whole log (an import), all ops in effect. Never overwrites."""
        self.dir.mkdir(parents=True, exist_ok=True)
        with self._tx() as db:
            if self._cursor_in(db) is not None:
                raise ValueError(f"exploration {self.exploration} already has a log")
            self._insert_all(db, ops, len(ops))

    # --- internals ---------------------------------------------------------------

    @contextmanager
    def _tx(self, write: bool = True):
        self._db.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self._db, timeout=30, isolation_level=None)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(_SCHEMA)
            if (self.dir / "log.jsonl").is_file():
                self._migrate_legacy(db)
            # IMMEDIATE takes the write lock up front, so read-modify-write is atomic
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield db
            except BaseException:
                db.execute("ROLLBACK")
                raise
            db.execute("COMMIT")
        finally:
            db.close()

    def _migrate_legacy(self, db: sqlite3.Connection) -> None:
        """Import an exploration stored the old way (log.jsonl + cursor.json), once."""
        db.execute("BEGIN IMMEDIATE")
        try:
            if self._cursor_in(db) is None:
                lines = (self.dir / "log.jsonl").read_text(encoding="utf-8").splitlines()
                ops = [json.loads(line) for line in lines if line.strip()]
                cursor_file = self.dir / "cursor.json"
                cursor = (
                    json.loads(cursor_file.read_text(encoding="utf-8"))["cursor"]
                    if cursor_file.is_file()
                    else len(ops)
                )
                self._insert_all(db, ops, cursor)
        except BaseException:
            db.execute("ROLLBACK")
            raise
        db.execute("COMMIT")

    def _insert_all(self, db: sqlite3.Connection, ops: list[dict], cursor: int) -> None:
        db.executemany(
            "INSERT INTO ops (exploration, seq, op) VALUES (?, ?, ?)",
            [(self.exploration, i, json.dumps(o, ensure_ascii=False)) for i, o in enumerate(ops)],
        )
        self._set_cursor_in(db, cursor)

    def _ops_in(self, db: sqlite3.Connection, limit: int | None = None) -> list[dict]:
        sql = "SELECT op FROM ops WHERE exploration = ? ORDER BY seq"
        params: tuple = (self.exploration,)
        if limit is not None:
            sql += " LIMIT ?"
            params += (limit,)
        return [json.loads(row[0]) for row in db.execute(sql, params)]

    def _count_in(self, db: sqlite3.Connection) -> int:
        return db.execute("SELECT COUNT(*) FROM ops WHERE exploration = ?", (self.exploration,)).fetchone()[0]

    def _cursor_in(self, db: sqlite3.Connection) -> int | None:
        row = db.execute("SELECT cursor FROM cursors WHERE exploration = ?", (self.exploration,)).fetchone()
        return row[0] if row else None

    def _set_cursor_in(self, db: sqlite3.Connection, cursor: int) -> None:
        db.execute(
            "INSERT INTO cursors (exploration, cursor) VALUES (?, ?) "
            "ON CONFLICT(exploration) DO UPDATE SET cursor = excluded.cursor",
            (self.exploration, cursor),
        )
