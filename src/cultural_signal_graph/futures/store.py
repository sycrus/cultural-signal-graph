"""File-backed exploration store: `runs/<run>/explorations/<id>/` (ADR-0008).

An exploration belongs to a forecast run that has passed extraction. Its anchors are
snapshotted into the `create` op, so replay never depends on the run's files again.
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..flags import detect_flags
from ..models import extraction_from_dict
from .generator import (
    summarize_reference,
    fixture_branch_generator,
    fixture_generator,
    live_branch_generator,
    live_generator,
)
from .log import OperationLog
from .replay import derive, descendants, replay

_EXPLORATION_ID = re.compile(r"^x-\d{8}-\d{6}-[0-9a-f]{6}$")
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class ExplorationStore:
    def __init__(
        self,
        runs_root: str | Path = "runs",
        generator=None,
        mode: str = "fixture",
        branch_generator=None,
    ):
        self.root = Path(runs_root)
        live = mode == "live"
        self._generate = generator or (live_generator if live else fixture_generator)
        self._branch = branch_generator or (live_branch_generator if live else fixture_branch_generator)
        self.mode = mode
        self._lock = threading.Lock()
        self._running: dict[str, threading.Event] = {}  # exploration -> stop flag

    # --- anchors -------------------------------------------------------------

    def anchors(self, run_id: str) -> list[dict]:
        """The evidence an exploration can grow from: every extracted signal, marked
        as a claim (made it into the brief), flagged (with its reason), or a plain
        signal. Raises ValueError if the run has not passed extraction."""
        run = self._run(run_id)
        run_dir = self.root / run_id
        state_path = next(
            (p for p in (run_dir / "state-final.json", run_dir / "state-pause.json") if p.is_file()),
            None,
        )
        if state_path is None:
            raise ValueError(f"run {run_id} has not passed extraction yet")
        values = json.loads(state_path.read_text(encoding="utf-8"))
        extraction = extraction_from_dict(values["extraction"])
        flags = {f.signal_id: f.reason for f in detect_flags(extraction.signals)}
        entity = {e.id: e for e in extraction.entities}
        finalized = state_path.name == "state-final.json"
        category = run["ask"]["category"]
        anchors = []
        for s in extraction.signals:
            about = entity.get(s.about_entity_id)
            if s.id in flags:
                kind = "flagged"
            elif finalized and about is not None and about.category == category:
                kind = "claim"
            else:
                kind = "signal"
            anchors.append(
                {
                    "id": s.id,
                    "kind": kind,
                    "text": s.text,
                    "flag": flags.get(s.id),
                    "entity": about.name if about else s.about_entity_id,
                    "category": about.category if about else None,
                    "source_uri": s.source_uri,
                    "confidence": s.confidence,
                }
            )
        return anchors

    # --- lifecycle -----------------------------------------------------------

    def create(
        self,
        run_id: str,
        goal: str,
        anchor_ids: list[str],
        horizon: int = 10,
        orders: int = 5,
        author: str = "strategist",
        start_year: int | None = None,
    ) -> dict:
        if not goal.strip():
            raise ValueError("an exploration needs a goal")
        if horizon < 1 or orders < 1:
            raise ValueError("horizon and orders must be at least 1")
        available = {a["id"]: a for a in self.anchors(run_id)}
        unknown = [a for a in anchor_ids if a not in available]
        if unknown:
            raise ValueError(f"unknown anchors: {', '.join(unknown)}")
        if not anchor_ids:
            raise ValueError("pick at least one anchor")
        exp_id = "x-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        log = OperationLog(self._dir(run_id, exp_id))
        log.append(
            {
                "op": "create",
                "exploration": {
                    "id": exp_id,
                    "run_id": run_id,
                    "goal": goal.strip(),
                    "horizon": int(horizon),
                    "orders": int(orders),
                    "start_year": int(start_year or datetime.now(timezone.utc).year),
                    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                },
                "anchors": [available[a] for a in anchor_ids],
            },
            author=author,
        )
        return self.snapshot(run_id, exp_id)

    def generate(self, run_id: str, exp_id: str) -> dict:
        """Run the remaining orders, one generator call (and one op) each."""
        for _ in self.generate_iter(run_id, exp_id):
            pass
        return self.snapshot(run_id, exp_id)

    def generate_iter(self, run_id: str, exp_id: str):
        """Generate order by order, yielding the snapshot after each one. Stops at the
        depth or time limit, or after the current order once `stop` is requested
        (recording a `stop` op). One generation per exploration at a time."""
        log = self._log(run_id, exp_id)
        stop = threading.Event()
        with self._lock:
            if exp_id in self._running:
                raise ValueError(f"exploration {exp_id} is already generating")
            self._running[exp_id] = stop
        try:
            state = replay(log.active())
            for order in range(state["orders_generated"] + 1, state["exploration"]["orders"] + 1):
                if stop.is_set():
                    log.append({"op": "stop", "order": order})
                    yield self.snapshot(run_id, exp_id)
                    return
                payload = self._generate(state, order)
                log.append({"op": "generate_order", **payload})
                state = replay(log.active())
                yield self.snapshot(run_id, exp_id)
                if not payload["projections"]:
                    return  # nothing grew from the previous order; deeper orders can't either
                e = state["exploration"]
                if min(p["window"][0] for p in payload["projections"]) >= e["start_year"] + e["horizon"]:
                    return  # the time limit: no years left for a deeper order
        finally:
            with self._lock:
                self._running.pop(exp_id, None)

    # --- edits & history (each one an op; undo/redo move the cursor) -----------

    def edit(
        self,
        run_id: str,
        exp_id: str,
        pid: str,
        statement: str | None = None,
        window: list[int] | None = None,
        author: str = "strategist",
    ) -> dict:
        """Change a projection's statement and/or time window. A new statement makes
        its descendants stale; a new window only shows up as timing conflicts."""
        log, state = self._mutable(run_id, exp_id)
        p = self._projection(state, pid)
        op: dict = {"op": "edit", "id": pid, "before": {"statement": p["statement"], "window": p["window"]}}
        if statement is not None:
            if not statement.strip():
                raise ValueError("a projection needs a statement")
            op["statement"] = statement.strip()
        if window is not None:
            if len(window) != 2 or int(window[0]) > int(window[1]):
                raise ValueError("window must be [start_year, end_year] with start <= end")
            op["window"] = [int(window[0]), int(window[1])]
        if "statement" not in op and "window" not in op:
            raise ValueError("nothing to change")
        log.append(op, author=author)
        return self.snapshot(run_id, exp_id)

    def delete(self, run_id: str, exp_id: str, pid: str, author: str = "strategist") -> dict:
        """Remove a projection; what grew from it is marked stale, never removed."""
        log, state = self._mutable(run_id, exp_id)
        p = self._projection(state, pid)
        log.append({"op": "delete", "id": pid, "before": p}, author=author)
        return self.snapshot(run_id, exp_id)

    def regenerate(self, run_id: str, exp_id: str, pid: str, author: str = "strategist") -> dict:
        """Replace the stale projections downstream of `pid` with a fresh branch grown
        from it, as deep as the ones it replaces. One op, so one undo."""
        log, state = self._mutable(run_id, exp_id)
        root = self._projection(state, pid)
        flags = derive(state)
        removed = [d for d in descendants(state, pid) if flags[d]["stale"]]
        if not removed:
            raise ValueError("nothing downstream of this projection is stale")
        depth = max(state["projections"][d]["order"] for d in removed) - root["order"]
        orders = self._grow(state, root, max(depth, 1), kind="regenerated", removed=removed)
        log.append({"op": "regenerate", "root": pid, "removed": removed, "orders": orders}, author=author)
        return self.snapshot(run_id, exp_id)

    def fork(self, run_id: str, exp_id: str, pid: str, hint: str | None = None, author: str = "strategist") -> dict:
        """A sibling branch from `pid` down to the depth limit, optionally steered by a
        "what if" hint. The original branch is kept; a fork never carries the baseline."""
        log, state = self._mutable(run_id, exp_id)
        root = self._projection(state, pid)
        depth = state["exploration"]["orders"] - root["order"]
        if depth < 1:
            raise ValueError("this projection is at the depth limit; there is no order left to fork into")
        hint = (hint or "").strip() or None
        orders = self._grow(state, {**root, "baseline": False}, depth, kind="fork", hint=hint)
        if not orders:
            raise ValueError("the fork produced nothing")
        log.append({"op": "fork", "root": pid, "hint": hint, "orders": orders}, author=author)
        return self.snapshot(run_id, exp_id)

    # --- the strategist's own additions --------------------------------------

    def add_reference(self, run_id: str, exp_id: str, url: str, excerpt: str, author: str = "strategist") -> dict:
        """A futures-scoped anchor in the Present column: never forecast evidence."""
        log, state = self._mutable(run_id, exp_id)
        ref, summary = self._reference(state, url, excerpt)
        log.append({"op": "add_reference", "reference": ref, "summary": summary}, author=author)
        return self.snapshot(run_id, exp_id)

    def add_projection(
        self,
        run_id: str,
        exp_id: str,
        kind: str,
        statement: str,
        window: list[int],
        parent_id: str | None = None,
        reference: dict | None = None,
        reference_id: str | None = None,
        author: str = "strategist",
    ) -> dict:
        """A grounded assumption (needs a reference: a new one or an existing one) or a
        wild card (no reference). Its order follows from its parent, or 1."""
        if kind not in ("assumption", "wildcard"):
            raise ValueError("kind must be 'assumption' or 'wildcard'")
        log, state = self._mutable(run_id, exp_id)
        if not statement.strip():
            raise ValueError("a projection needs a statement")
        if len(window) != 2 or int(window[0]) > int(window[1]):
            raise ValueError("window must be [start_year, end_year] with start <= end")
        parent = self._projection(state, parent_id) if parent_id else None
        op: dict = {"op": "add_wildcard" if kind == "wildcard" else "add_assumption"}
        anchors: list[str] = []
        if kind == "assumption":
            if reference:
                ref, summary = self._reference(state, reference.get("url", ""), reference.get("excerpt", ""))
                op["reference"], op["summary"] = ref, summary
                anchors = [ref["id"]]
            elif reference_id:
                if state["anchors"].get(reference_id, {}).get("kind") != "reference":
                    raise ValueError(f"unknown reference: {reference_id}")
                anchors = [reference_id]
            else:
                raise ValueError("a grounded assumption needs a reference; without one it is a wild card")
        taken = set(state["projections"]) | set(state["anchors"]) | set(state["removed"])
        n = 1
        while f"{kind}-{n}" in taken:
            n += 1
        op["projection"] = {
            "id": f"{kind}-{n}",
            "statement": statement.strip(),
            "order": parent["order"] + 1 if parent else 1,
            "window": [int(window[0]), int(window[1])],
            "parents": [parent["id"]] if parent else [],
            "anchors": anchors,
            "origin": kind,
            "baseline": False,
            "discontinuity": False,
        }
        log.append(op, author=author)
        return self.snapshot(run_id, exp_id)

    def _reference(self, state: dict, url: str, excerpt: str) -> tuple[dict, dict]:
        url, excerpt = url.strip(), excerpt.strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("a reference needs an http(s) URL")
        if not excerpt:
            raise ValueError("a reference needs an excerpt: what the source says")
        summary = summarize_reference(url, excerpt, live=self.mode == "live")
        n = 1
        while f"ref-{n}" in state["anchors"]:
            n += 1
        ref = {
            "id": f"ref-{n}",
            "kind": "reference",
            "scope": "futures",
            "text": summary["text"],
            "excerpt": excerpt,
            "source_uri": url,
            "flag": None,
        }
        return ref, summary

    def _grow(self, state: dict, root: dict, depth: int, kind: str, removed=(), hint=None) -> list[dict]:
        """Grow a branch from `root`, one branch-generator call per order."""
        working = {**state, "projections": {k: v for k, v in state["projections"].items() if k not in set(removed)}}
        frontier = [root["id"]]
        payloads = []
        for order in range(root["order"] + 1, root["order"] + depth + 1):
            branch = {"kind": kind, "frontier": frontier, "baseline": root["baseline"], "hint": hint}
            payload = self._branch(working, order, branch)
            if not payload["projections"]:
                break
            payloads.append(payload)
            working["projections"] = {**working["projections"], **{p["id"]: {**p, "op": -1} for p in payload["projections"]}}
            frontier = [p["id"] for p in payload["projections"]]
        return payloads

    def undo(self, run_id: str, exp_id: str) -> dict:
        log, _ = self._mutable(run_id, exp_id)
        log.undo()
        return self.snapshot(run_id, exp_id)

    def redo(self, run_id: str, exp_id: str) -> dict:
        """Redo replays the stored op — a generation's recorded output, no model call."""
        log, _ = self._mutable(run_id, exp_id)
        log.redo()
        return self.snapshot(run_id, exp_id)

    def _mutable(self, run_id: str, exp_id: str):
        log = self._log(run_id, exp_id)
        if self.is_generating(exp_id):
            raise ValueError(f"exploration {exp_id} is generating; stop it first")
        return log, replay(log.active())

    @staticmethod
    def _projection(state: dict, pid: str) -> dict:
        if pid not in state["projections"]:
            raise KeyError(f"unknown projection: {pid}")
        return state["projections"][pid]

    def stop(self, run_id: str, exp_id: str) -> dict:
        """Ask a running generation to halt after its current order."""
        self._log(run_id, exp_id)
        with self._lock:
            flag = self._running.get(exp_id)
        if flag is None:
            raise ValueError(f"exploration {exp_id} is not generating")
        flag.set()
        return {"stopping": True}

    def is_generating(self, exp_id: str) -> bool:
        with self._lock:
            return exp_id in self._running

    # --- reads ---------------------------------------------------------------

    def list(self, run_id: str) -> list[dict]:
        self._run(run_id)
        base = self.root / run_id / "explorations"
        if not base.is_dir():
            return []
        out = []
        for d in sorted(base.iterdir()):
            log = OperationLog(d)
            if not log.exists():
                continue
            state = replay(log.active())
            out.append(
                {
                    **state["exploration"],
                    "projections": len(state["projections"]),
                    "anchor_ids": list(state["anchors"]),
                }
            )
        out.sort(key=lambda e: e["created_at"], reverse=True)
        return out

    def snapshot(self, run_id: str, exp_id: str) -> dict:
        log = self._log(run_id, exp_id)
        state = replay(log.active())
        flags = derive(state)
        projections = sorted(
            ({**p, **flags[p["id"]]} for p in state["projections"].values()),
            key=lambda p: (p["order"], p["window"][0], p["id"]),
        )
        return {
            "exploration": state["exploration"],
            "anchors": list(state["anchors"].values()),
            "projections": projections,
            "orders_generated": state["orders_generated"],
            "can_continue": self._can_continue(state),
            "generating": self.is_generating(exp_id),
            "stopped_at": state.get("stopped_at"),
            "removed": state["removed"],
            "cursor": log.cursor(),
            "can_undo": log.can_undo(),
            "can_redo": log.can_redo(),
            "mode": self.mode,
        }

    @staticmethod
    def _can_continue(state: dict) -> bool:
        """More orders to generate: under the depth limit, and the last order both
        grew something and left years before the time limit."""
        e = state["exploration"]
        done = state["orders_generated"]
        if done >= e["orders"]:
            return False
        if done == 0:
            return True
        last = [p for p in state["projections"].values() if p["order"] == done]
        return bool(last) and min(p["window"][0] for p in last) < e["start_year"] + e["horizon"]

    def ops(self, run_id: str, exp_id: str) -> list[dict]:
        return self._log(run_id, exp_id).active()

    def op(self, run_id: str, exp_id: str, seq: int) -> dict:
        """One op in effect — the provenance behind a projection (full model I/O)."""
        ops = self.ops(run_id, exp_id)
        if not 0 <= seq < len(ops):
            raise KeyError(f"unknown op: {seq}")
        return ops[seq]

    # --- internals -----------------------------------------------------------

    def _run(self, run_id: str) -> dict:
        if not _RUN_ID.match(run_id):
            raise KeyError(f"unknown run: {run_id}")
        path = self.root / run_id / "run.json"
        if not path.is_file():
            raise KeyError(f"unknown run: {run_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _log(self, run_id: str, exp_id: str) -> OperationLog:
        self._run(run_id)
        log = OperationLog(self._dir(run_id, exp_id))
        if not log.exists():
            raise KeyError(f"unknown exploration: {exp_id}")
        return log

    def _dir(self, run_id: str, exp_id: str) -> Path:
        # exploration ids arrive in URLs: validate before joining a path
        if not _EXPLORATION_ID.match(exp_id):
            raise KeyError(f"unknown exploration: {exp_id}")
        return self.root / run_id / "explorations" / exp_id
