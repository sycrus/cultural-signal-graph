"""Replay: an exploration's state is a pure function of its active ops (ADR-0008).

State is JSON-native (dicts), like the forecast pipeline's checkpointed state:

    exploration   goal, horizon, orders, start_year, run_id, ...
    anchors       anchor id -> the anchor as snapshotted at create time
    projections   projection id -> {id, statement, order, window, parents, anchors,
                                    origin, baseline, discontinuity, op}
    orders_generated   how many orders the generator has completed

A projection's `parents` are projection ids; its `anchors` are anchor ids it grows
from directly. Order is causal depth, `window` is [start_year, end_year] — separate.
"""

from __future__ import annotations

import copy


def replay(ops: list[dict]) -> dict:
    state: dict = {}
    for op in ops:
        apply(state, op)
    return state


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


def _generate_order(state: dict, op: dict) -> None:
    for p in op["projections"]:
        state["projections"][p["id"]] = {**copy.deepcopy(p), "op": op["seq"]}
    state["orders_generated"] = max(state["orders_generated"], op["order"])


_HANDLERS = {
    "create": _create,
    "generate_order": _generate_order,
}
