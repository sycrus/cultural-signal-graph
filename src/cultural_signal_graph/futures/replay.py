"""Replay: an exploration's state is a pure function of its active ops (ADR-0008).

State is JSON-native (dicts), like the forecast pipeline's checkpointed state:

    exploration   goal, horizon, orders, start_year, run_id, ...
    anchors       anchor id -> the anchor as snapshotted at create time
    projections   projection id -> {id, statement, order, window, parents, anchors,
                                    origin, baseline, discontinuity, op, ...}
    orders_generated   how many orders the generator has completed
    changed       node id -> seq of the last op that edited or removed it
    removed       projection id -> its statement, once deleted (for display)

A projection's `parents` are projection ids; its `anchors` are anchor ids it grows
from directly. Order is causal depth, `window` is [start_year, end_year] — separate.
`op` is the seq of the op that generated it; staleness compares it against `changed`.
"""

from __future__ import annotations

import copy
import math


def replay(ops: list[dict]) -> dict:
    state: dict = {}
    for op in ops:
        apply(state, op)
    return state


def derive(state: dict, rejected: frozenset = frozenset()) -> dict[str, dict]:
    """Per-projection flags computed from the DAG, not stored in any op:
    `timing_conflict` — it starts before something it grows from;
    `stale` — something it grows from (transitively) was edited or removed after
    it was generated, or rests on a cross-domain edge the gate `rejected`."""
    projections = state["projections"]
    changed = {**state.get("changed", {}), **{r: math.inf for r in rejected}}
    latest: dict[str, int] = {}

    def last_change(node_id: str, seen: frozenset = frozenset()) -> int:
        """The latest change to this node or anything upstream of it."""
        if node_id in latest:
            return latest[node_id]
        value = changed.get(node_id, -1)
        p = projections.get(node_id)
        if p is not None and node_id not in seen:
            for src in p["parents"] + p["anchors"]:
                value = max(value, last_change(src, seen | {node_id}))
        latest[node_id] = value
        return value

    human: dict[str, str | None] = {}

    def human_root(node_id: str, seen: frozenset = frozenset()) -> str | None:
        """The nearest strategist-written origin upstream: 'assumption' or 'wildcard'."""
        if node_id in human:
            return human[node_id]
        p = projections.get(node_id)
        found = None
        if p is not None and node_id not in seen:
            if p.get("origin") in ("assumption", "wildcard"):
                found = p["origin"]
            else:
                for src in p["parents"]:
                    found = found or human_root(src, seen | {node_id})
        human[node_id] = found
        return found

    out = {}
    for pid, p in projections.items():
        parents = [projections[q] for q in p["parents"] if q in projections]
        upstream = max((last_change(s) for s in p["parents"] + p["anchors"]), default=-1)
        out[pid] = {
            "timing_conflict": any(p["window"][0] < q["window"][0] for q in parents),
            "stale": upstream > p["op"],
            "human_root": human_root(pid),
        }
    return out


def descendants(state: dict, root: str) -> list[str]:
    """Every projection downstream of `root`, nearest first."""
    children: dict[str, list[str]] = {}
    for p in state["projections"].values():
        for src in p["parents"] + p["anchors"]:
            children.setdefault(src, []).append(p["id"])
    out, queue = [], [root]
    while queue:
        for c in children.get(queue.pop(0), []):
            if c not in out:
                out.append(c)
                queue.append(c)
    return out


def apply(state: dict, op: dict) -> None:
    handler = _HANDLERS.get(op["op"])
    if handler is None:
        raise ValueError(f"unknown operation: {op['op']!r}")
    handler(state, op)


def _create(state: dict, op: dict) -> None:
    state["exploration"] = copy.deepcopy(op["exploration"])
    state["anchors"] = {a["id"]: copy.deepcopy(a) for a in op["anchors"]}
    state["projections"] = {}
    state["orders_generated"] = 0
    state["changed"] = {}
    state["removed"] = {}
    state["tags"] = {}  # lens -> projection id -> {value, ..., source, op}
    state["axes"] = None  # the Matrix's two chosen axes
    state["axis_candidates"] = []
    state["annotations"] = {}  # "lens:key" -> {lens, key, text, based_on, op}


def _add(state: dict, projections: list[dict], seq: int) -> None:
    for p in projections:
        state["projections"][p["id"]] = {**copy.deepcopy(p), "op": seq}


def _generate_order(state: dict, op: dict) -> None:
    _add(state, op["projections"], op["seq"])
    state["orders_generated"] = max(state["orders_generated"], op["order"])
    state.pop("stopped_at", None)


def _stop(state: dict, op: dict) -> None:
    state["stopped_at"] = op["order"]


def _edit(state: dict, op: dict) -> None:
    p = state["projections"][op["id"]]
    if "statement" in op:
        p["statement"] = op["statement"]
    if "window" in op:
        p["window"] = list(op["window"])
    p["edited_op"] = op["seq"]
    if "statement" in op:
        # what grew from it was generated from the old statement; a new window
        # alone only surfaces as timing conflicts
        state["changed"][op["id"]] = op["seq"]


def _delete(state: dict, op: dict) -> None:
    p = state["projections"].pop(op["id"])
    state["removed"][op["id"]] = p["statement"]
    state["changed"][op["id"]] = op["seq"]


def _branch(state: dict, op: dict) -> None:
    """regenerate / fork: drop the replaced projections, add the branch."""
    for pid in op.get("removed", []):
        p = state["projections"].pop(pid, None)
        if p is not None:
            state["removed"][pid] = p["statement"]
    for payload in op["orders"]:
        _add(state, payload["projections"], op["seq"])


def _add_reference(state: dict, op: dict) -> None:
    ref = op["reference"]
    state["anchors"][ref["id"]] = copy.deepcopy(ref)


def _add_human_projection(state: dict, op: dict) -> None:
    """add_assumption / add_wildcard: a strategist-written projection (plus, for an
    assumption, the new reference it rests on)."""
    if op.get("reference"):
        _add_reference(state, op)
    _add(state, [op["projection"]], op["seq"])


def _retag(state: dict, op: dict) -> None:
    """Lens tags: from the model (first open) or the strategist (an override)."""
    tags = state["tags"].setdefault(op["lens"], {})
    for pid, tag in op["tags"].items():
        prev = tags.get(pid)
        new = {**copy.deepcopy(tag), "source": op["source"], "op": op["seq"]}
        if op["source"] == "human" and prev:
            # keep what the model said, so both judgements stay visible
            new["model_value"] = prev["value"] if prev["source"] == "model" else prev.get("model_value")
        tags[pid] = new


def _propose_axes(state: dict, op: dict) -> None:
    state["axis_candidates"] = copy.deepcopy(op["candidates"])


def _set_axes(state: dict, op: dict) -> None:
    """New axes are a new matrix: placements and narratives start over."""
    state["axes"] = copy.deepcopy(op["axes"])
    state["tags"]["matrix"] = {}
    state["annotations"] = {k: v for k, v in state["annotations"].items() if v["lens"] != "matrix"}


def _seed_fork(state: dict, op: dict) -> None:
    """A branch generated for one quadrant's world: placed in that quadrant."""
    _branch(state, op)
    tags = state["tags"].setdefault("matrix", {})
    for payload in op["orders"]:
        for p in payload["projections"]:
            tags[p["id"]] = {"value": op["quadrant"], "source": "seeded", "op": op["seq"]}


def _annotate(state: dict, op: dict) -> None:
    state["annotations"][f"{op['lens']}:{op['key']}"] = {
        "lens": op["lens"],
        "key": op["key"],
        "text": op["text"],
        "based_on": list(op["based_on"]),
        "op": op["seq"],
    }


_HANDLERS = {
    "create": _create,
    "propose_axes": _propose_axes,
    "set_axes": _set_axes,
    "seed_fork": _seed_fork,
    "annotate": _annotate,
    "retag": _retag,
    "add_reference": _add_reference,
    "add_assumption": _add_human_projection,
    "add_wildcard": _add_human_projection,
    "generate_order": _generate_order,
    "stop": _stop,
    "edit": _edit,
    "delete": _delete,
    "regenerate": _branch,
    "fork": _branch,
}
