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
from rdflib.namespace import RDFS

from ..models import extraction_from_dict
from .generator import suggest_anchors as generator_suggest
from .generator import (
    summarize_reference,
    fixture_branch_generator,
    fixture_generator,
    live_branch_generator,
    live_generator,
)
from . import lenses as lens_registry
from . import matrix
from .export import to_json, to_markdown
from .rdf import exploration_graph, run_dataset
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

    # --- run-level helpers for the anchor picker -----------------------------------

    def anchor_pestle(self, run_id: str) -> dict[str, dict]:
        """PESTLE tags for the run's anchors, before any exploration exists — one
        cheap call, cached in the run directory so reopening the picker is free."""
        cache = self.root / run_id / "futures-pestle.json"
        anchors = {a["id"]: a for a in self.anchors(run_id)}
        cached = json.loads(cache.read_text(encoding="utf-8")) if cache.is_file() else {}
        missing = [a for aid, a in anchors.items() if aid not in cached]
        if missing:
            run = self._run(run_id)
            pseudo = {"exploration": {"goal": run["ask"]["question"], "start_year": 0}, "anchors": {a["id"]: a for a in missing}, "projections": {}}
            payload = lens_registry.classify(lens_registry.PESTLE, pseudo, lens_registry.taggable(lens_registry.PESTLE, pseudo), live=self.mode == "live")
            cached.update({k: {kk: vv for kk, vv in v.items() if kk != "fixed"} for k, v in payload["tags"].items()})
            cache.write_text(json.dumps(cached, indent=2), encoding="utf-8")
        return {aid: cached[aid] for aid in anchors if aid in cached}

    def suggest_anchors(self, run_id: str, goal: str) -> dict:
        """Anchors relevant to a goal, with a reason each (one cheap call; advisory —
        the strategist confirms in the picker)."""
        if not goal.strip():
            raise ValueError("give the exploration a goal first")
        anchors = self.anchors(run_id)
        if self.mode != "live":
            words = {w for w in goal.lower().split() if len(w) > 3}
            ids = [a["id"] for a in anchors if words & set(a["text"].lower().split()) or a["kind"] in ("claim", "signal")]
            return {"anchor_ids": ids or [a["id"] for a in anchors], "reasons": {}, "model": "fixture"}
        return generator_suggest(goal, anchors)

    def _values(self, run_id: str) -> tuple[dict, dict, bool]:
        """(run record, pipeline state, finalized?) — ValueError before extraction."""
        run = self._run(run_id)
        run_dir = self.root / run_id
        state_path = next(
            (p for p in (run_dir / "state-final.json", run_dir / "state-pause.json") if p.is_file()),
            None,
        )
        if state_path is None:
            raise ValueError(f"run {run_id} has not passed extraction yet")
        values = json.loads(state_path.read_text(encoding="utf-8"))
        return run, values, state_path.name == "state-final.json"

    def _cached_pestle(self, run_id: str, anchor_ids: list[str]) -> dict:
        cache = self.root / run_id / "futures-pestle.json"
        if not cache.is_file():
            return {}
        cached = json.loads(cache.read_text(encoding="utf-8"))
        return {a: cached[a] for a in anchor_ids if a in cached}

    def gate(self, run_id: str) -> dict[str, str]:
        """Each proposed cross-domain edge's current gate status, read live from the
        run: proposed (pending sign-off), real (approved), or rejected."""
        try:
            run, values, _ = self._values(run_id)
        except ValueError:
            return {}
        decisions = run.get("decisions", {}) if run["status"] == "completed" else {}
        status = {True: "real", False: "rejected"}
        return {e["id"]: status.get(decisions.get(e["id"]), "proposed") for e in values.get("edges", [])}

    def anchors(self, run_id: str) -> list[dict]:
        """The evidence an exploration can grow from: every extracted signal, marked
        as a claim (made it into the brief), flagged (with its reason), or a plain
        signal; plus each cross-domain edge the gate has not rejected (tagged
        pending until signed off). Raises ValueError before extraction."""
        run, values, finalized = self._values(run_id)
        extraction = extraction_from_dict(values["extraction"])
        flags = {f.signal_id: f.reason for f in detect_flags(extraction.signals)}
        entity = {e.id: e for e in extraction.entities}
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
        gate = self.gate(run_id)
        for e in values.get("edges", []):
            if gate.get(e["id"]) == "rejected":
                continue  # dropped at the gate: not evidence anything can grow from
            left, right = entity.get(e["left_entity_id"]), entity.get(e["right_entity_id"])
            anchors.append(
                {
                    "id": e["id"],
                    "kind": "edge",
                    "text": f"{left.name if left else e['left_entity_id']} ≈ {right.name if right else e['right_entity_id']}",
                    "flag": None,
                    "entity": " ⇄ ".join(c for c in (left and left.category, right and right.category) if c),
                    "category": None,
                    "confidence": e["confidence"],
                    "status": gate.get(e["id"], "proposed"),
                    "pending": gate.get(e["id"], "proposed") == "proposed",
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
        """A new exploration. Anchor PESTLE tags already computed for the picker are
        carried into the create op, so the lens does not ask again."""
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
                "anchor_tags": {"pestle": self._cached_pestle(run_id, anchor_ids)},
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
        flags = self._derive(run_id, state)
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

    # --- lens tags ---------------------------------------------------------------

    def classify(self, run_id: str, exp_id: str, lens_key: str) -> dict:
        """Tag every projection the lens has no tag for yet — one cheap-model call,
        cached as a `retag` op. Nothing untagged: no call, no op."""
        spec = lens_registry.lens(lens_key)
        log, state = self._mutable(run_id, exp_id)
        have = state["tags"].get(lens_key, {})
        untagged = [p for p in lens_registry.taggable(spec, state) if p["id"] not in have]
        if untagged:
            payload = lens_registry.classify(spec, state, untagged, live=self.mode == "live")
            if payload["tags"]:
                log.append({"op": "retag", "lens": lens_key, "source": "model", **payload})
        return self.snapshot(run_id, exp_id)

    def set_tag(self, run_id: str, exp_id: str, pid: str, lens_key: str, tag: dict, author: str = "strategist") -> dict:
        """The strategist's override (a drag in the lens view), attributed."""
        spec = lens_registry.lens(lens_key)
        log, state = self._mutable(run_id, exp_id)
        if not (spec.include_anchors and pid in state["anchors"]):
            self._projection(state, pid)
        clean = lens_registry.clean_tag(spec, tag)
        before = state["tags"].get(lens_key, {}).get(pid)
        log.append({"op": "retag", "lens": lens_key, "source": "human", "tags": {pid: clean}, "before": before}, author=author)
        return self.snapshot(run_id, exp_id)

    # --- the Matrix: axes first, then seeded worlds and narratives ------------------

    def propose_axes(self, run_id: str, exp_id: str, author: str = "strategist") -> dict:
        log, state = self._mutable(run_id, exp_id)
        payload = matrix.propose_axes(state, live=self.mode == "live")
        log.append({"op": "propose_axes", **payload}, author=author)
        return self.snapshot(run_id, exp_id)

    def set_axes(self, run_id: str, exp_id: str, axes: list[dict], author: str = "strategist") -> dict:
        log, state = self._mutable(run_id, exp_id)
        if len(axes) != 2:
            raise ValueError("a matrix needs exactly two axes")
        clean = [matrix._clean_axis(a, state["anchors"]) for a in axes]
        log.append({"op": "set_axes", "axes": clean, "before": state["axes"]}, author=author)
        return self.snapshot(run_id, exp_id)

    def seed_quadrant(self, run_id: str, exp_id: str, quadrant: str, author: str = "strategist") -> dict:
        """Generate a branch from the present for one quadrant's world, down to the
        depth limit, conditioned on that quadrant's axis values."""
        log, state = self._mutable(run_id, exp_id)
        axes = self._axes(state, quadrant)
        constraint = {a["name"]: a[pole] for a, pole in zip(axes, matrix.POLES[quadrant])}
        payloads = self._seed(state, matrix.world(axes, quadrant))
        log.append({"op": "seed_fork", "lens": "matrix", "quadrant": quadrant, "constraint": constraint, "orders": payloads}, author=author)
        return self.snapshot(run_id, exp_id)

    def seed_dimension(self, run_id: str, exp_id: str, dimension: str, author: str = "strategist") -> dict:
        """Fill a PESTLE gap: a branch from the present that follows one dimension."""
        if dimension not in lens_registry.PESTLE_VALUES:
            raise KeyError(f"unknown PESTLE dimension: {dimension}")
        log, state = self._mutable(run_id, exp_id)
        world = f"the {dimension} dimension of {state['exploration']['goal']}: follow {dimension} forces and consequences"
        payloads = self._seed(state, world)
        log.append({"op": "seed_fork", "lens": "pestle", "quadrant": dimension, "constraint": {"pestle": dimension}, "orders": payloads}, author=author)
        return self.snapshot(run_id, exp_id)

    def _seed(self, state: dict, world: str) -> list[dict]:
        working = {**state}
        frontier = list(state["anchors"])
        payloads = []
        for order in range(1, state["exploration"]["orders"] + 1):
            branch = {"kind": "seeded", "frontier": frontier, "baseline": False, "world": world}
            payload = self._branch(working, order, branch)
            if not payload["projections"]:
                break
            payloads.append(payload)
            working["projections"] = {**working["projections"], **{p["id"]: {**p, "op": -1} for p in payload["projections"]}}
            frontier = [p["id"] for p in payload["projections"]]
        if not payloads:
            raise ValueError("the seeded branch produced nothing")
        return payloads

    def write_narrative(self, run_id: str, exp_id: str, quadrant: str, author: str = "strategist") -> dict:
        log, state = self._mutable(run_id, exp_id)
        axes = self._axes(state, quadrant)
        members = self._members(state, quadrant)
        payload = matrix.narrative(state, axes, quadrant, members, live=self.mode == "live")
        log.append(
            {"op": "annotate", "lens": "matrix", "key": quadrant, "based_on": [p["id"] for p in members], **payload},
            author=author,
        )
        return self.snapshot(run_id, exp_id)

    @staticmethod
    def _axes(state: dict, quadrant: str) -> list[dict]:
        if quadrant not in matrix.QUADRANTS:
            raise KeyError(f"unknown quadrant: {quadrant}")
        if not state["axes"]:
            raise ValueError("pick two axes for the matrix first")
        return state["axes"]

    @staticmethod
    def _members(state: dict, quadrant: str) -> list[dict]:
        tags = state["tags"].get("matrix", {})
        return [p for p in state["projections"].values() if tags.get(p["id"], {}).get("value") == quadrant]

    def _annotations(self, state: dict) -> list[dict]:
        """Annotations, each stale once its quadrant's projections changed after it
        was written (membership, statements, or removals)."""
        out = []
        for a in state["annotations"].values():
            members = {p["id"] for p in self._members(state, a["key"])}
            changed = state["changed"]
            stale = members != set(a["based_on"]) or any(changed.get(pid, -1) > a["op"] for pid in a["based_on"])
            out.append({**a, "stale": stale})
        return out

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
        flags = self._derive(run_id, state)
        def tags(pid: str) -> dict:
            return {k: v[pid] for k, v in state["tags"].items() if pid in v}

        projections = sorted(
            ({**p, **flags[p["id"]], "tags": tags(p["id"])} for p in state["projections"].values()),
            key=lambda p: (p["order"], p["window"][0], p["id"]),
        )
        return {
            "exploration": state["exploration"],
            "anchors": self._live_anchors(run_id, state),
            "projections": projections,
            "orders_generated": state["orders_generated"],
            "can_continue": self._can_continue(state),
            "generating": self.is_generating(exp_id),
            "stopped_at": state.get("stopped_at"),
            "removed": state["removed"],
            "axes": state["axes"],
            "axis_candidates": state["axis_candidates"],
            "annotations": self._annotations(state),
            "lenses": {
                key: {
                    "untagged": sum(1 for p in lens_registry.taggable(spec, state) if p["id"] not in state["tags"].get(key, {})),
                    "ready": spec.ready(state) is None,
                }
                for key, spec in lens_registry.LENSES.items()
            },
            "cursor": log.cursor(),
            "can_undo": log.can_undo(),
            "can_redo": log.can_redo(),
            "mode": self.mode,
        }

    def _derive(self, run_id: str, state: dict) -> dict[str, dict]:
        """Derived flags, with the gate's current rejections making their dependents stale."""
        gate = self.gate(run_id)
        rejected = frozenset(a for a in state["anchors"] if gate.get(a) == "rejected")
        return derive(state, rejected)

    def _live_anchors(self, run_id: str, state: dict) -> list[dict]:
        """Anchors as snapshotted at create time, with edge anchors following the gate."""
        gate = self.gate(run_id)
        out = []
        for a in state["anchors"].values():
            if a.get("kind") == "edge" and a["id"] in gate:
                a = {**a, "status": gate[a["id"]], "pending": gate[a["id"]] == "proposed"}
            tags = {k: v[a["id"]] for k, v in state["tags"].items() if a["id"] in v}
            out.append({**a, "tags": tags})
        return out

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

    # --- export / import ----------------------------------------------------------

    EXPORTS = ("exploration.json", "exploration.md", "log.jsonl", "exploration.trig")

    def export(self, run_id: str, exp_id: str, name: str) -> str:
        if name not in self.EXPORTS:
            raise KeyError(f"unknown export: {name}")
        if name == "log.jsonl":
            return "".join(json.dumps(o, ensure_ascii=False) + "\n" for o in self.ops(run_id, exp_id))
        snap = self.snapshot(run_id, exp_id)
        if name == "exploration.json":
            return to_json(snap)
        if name == "exploration.md":
            return to_markdown(snap)
        state = replay(self.ops(run_id, exp_id))
        return run_dataset(None, [state]).serialize(format="trig")

    def import_log(self, run_id: str, text: str, author: str = "strategist") -> dict:
        """Re-open an exported log as a new exploration on this run: same ops, same
        state, a fresh id."""
        self._run(run_id)
        try:
            ops = [json.loads(line) for line in text.splitlines() if line.strip()]
        except json.JSONDecodeError as exc:
            raise ValueError(f"not an exploration log: {exc}") from exc
        if not ops or ops[0].get("op") != "create":
            raise ValueError("not an exploration log: it must start with a create op")
        replay(ops)  # refuse a log that does not replay
        exp_id = "x-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        ops[0] = {
            **ops[0],
            "exploration": {**ops[0]["exploration"], "id": exp_id, "run_id": run_id, "imported_from": ops[0]["exploration"]["id"]},
        }
        log = OperationLog(self._dir(run_id, exp_id))
        log.dir.mkdir(parents=True, exist_ok=True)
        (log.dir / "log.jsonl").write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in ops), encoding="utf-8")
        return self.snapshot(run_id, exp_id)

    def futures_trig(self, run_id: str, evidence=None) -> str:
        """The run's RDF with every exploration as a named graph beside the evidence."""
        states = [replay(self._log(run_id, e["id"]).active()) for e in self.list(run_id)]
        return run_dataset(evidence, states).serialize(format="trig")

    def graph_layer(self, run_id: str) -> dict:
        """Cytoscape elements for the forecast Graph tab's futures layer: every
        exploration's projections and references, linked to the evidence they grow
        from (signal nodes share their ids with the evidence graph)."""
        from rdflib.namespace import RDF

        from .rdf import CSGF

        nodes, edges = [], []
        for e in self.list(run_id):
            state = replay(self._log(run_id, e["id"]).active())
            g = exploration_graph(state)
            for node in g.subjects(RDF.type, CSGF.Projection):
                p = state["projections"][str(node).rsplit("#", 1)[-1]]
                nodes.append({"data": {
                    "id": str(node), "label": p["statement"][:40] + ("…" if len(p["statement"]) > 40 else ""),
                    "statement": p["statement"], "kind": "projection", "exploration": e["goal"],
                    "valid": f"{p['window'][0]} -> {p['window'][1]}", "origin": p["origin"],
                }})
            for node in g.subjects(RDF.type, CSGF.Reference):
                nodes.append({"data": {"id": str(node), "label": str(g.value(node, RDFS.label))[:40], "kind": "reference"}})
            for s, o in g.subject_objects(CSGF.growsFrom):
                edges.append({"data": {"id": f"grows:{s}:{o}", "source": str(o), "target": str(s), "kind": "growsFrom"}})
        return {"nodes": nodes, "edges": edges}

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
