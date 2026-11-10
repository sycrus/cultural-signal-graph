# The operation log is stored in SQLite; JSONL stays the export format

ADR-0008 made the per-exploration operation log the source of truth. It was stored as
`log.jsonl` plus `cursor.json`, and each append read the whole file and rewrote it. With one
strategist that was fine. The workshop surface (ADR-0012) has phones submitting ideas while the
facilitator edits, against one host, and the server handles requests on a thread pool. Two
appends at once can both read the same log and one of them is lost, silently.

So the log moves into **SQLite**, with one table per run and rows keyed by exploration and
sequence, plus the cursor. Appends, undo and redo are transactions, so concurrent writers are
serialised by the database rather than by our code, and an append no longer rewrites the log.
Everything ADR-0008 specifies is unchanged: state is replay up to the cursor, undo/redo move
it, redo of a generation replays stored output, and an append after undo drops the redo tail.
`log.jsonl` remains the **export and import format**, so exploration exports, promotion's log
carry-over and fixtures keep working.

This covers level 1 of the concurrency roadmap in `PRD-workshop.md`: never lose a write. Live
broadcast (level 2) builds on it. Per-person undo with a CRDT (level 3) would replace the cursor
model and needs its own ADR.

**Considered options:** keeping JSONL behind `filelock` with true append-mode writes (rejected:
no less code, and the cursor and redo-tail truncation still need careful hand-rolled
atomicity); a CRDT now (rejected: it changes the source-of-truth model for a need, per-person
undo, that is explicitly future); a separate database server (rejected: breaks the one-command,
file-backed local setup). SQLite is already in the project's dependencies through
`langgraph-checkpoint-sqlite`.
