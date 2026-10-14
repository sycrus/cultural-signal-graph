"""The futures generator: one call per order, each appended as a `generate_order` op.

A generator function takes `(state, order)` and returns the op payload: the model,
its full input, its raw output, and the parsed projections. `fixture_generator`
replays the recorded fixture outputs (no model); the live generator calls the model.

Model output format (one JSON object per order):

    {"projections": [{"id", "statement", "from": [ids], "window": [start, end],
                      "baseline": bool, "discontinuity": bool}]}

`from` mixes anchor ids and projection ids from earlier orders; the parser splits
them into `anchors` and `parents`.
"""

from __future__ import annotations

import json

from ..llm import extract_json
from .fixtures import RECORDED_ORDER_OUTPUTS


def parse_order(raw: str, order: int, state: dict) -> list[dict]:
    """Parse one order's raw output into projections, resolving `from` ids against
    the exploration's anchors and earlier projections. Unknown ids are dropped; a
    projection left with no anchor or parent is dropped too (never unanchored)."""
    data = json.loads(extract_json(raw))
    items = data.get("projections") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("order output must be an object with a 'projections' array")
    anchors = state["anchors"]
    earlier = state["projections"]
    taken = set(earlier) | set(anchors)
    out = []
    for item in items:
        frm = [str(i) for i in item.get("from", [])]
        parent_ids = [i for i in frm if i in earlier]
        anchor_ids = [i for i in frm if i in anchors]
        if not parent_ids and not anchor_ids:
            continue
        pid = _unique(str(item.get("id") or f"o{order}-{len(out) + 1}"), taken)
        taken.add(pid)
        window = item.get("window") or []
        if len(window) != 2:
            raise ValueError(f"projection {pid} needs a [start, end] window")
        start, end = int(window[0]), int(window[1])
        out.append(
            {
                "id": pid,
                "statement": str(item["statement"]),
                "order": order,
                "window": [min(start, end), max(start, end)],
                "parents": parent_ids,
                "anchors": anchor_ids,
                "origin": "generated",
                "baseline": bool(item.get("baseline", False)),
                "discontinuity": bool(item.get("discontinuity", False)),
            }
        )
    return out


def _unique(pid: str, taken: set[str]) -> str:
    if pid not in taken:
        return pid
    n = 2
    while f"{pid}-{n}" in taken:
        n += 1
    return f"{pid}-{n}"


def fixture_generator(state: dict, order: int) -> dict:
    """Replay the recorded output for this order. Projections whose sources were not
    selected are dropped by the parser, so the fixture follows the anchor picker."""
    if order > len(RECORDED_ORDER_OUTPUTS):
        return {"order": order, "model": "fixture", "input": None, "output": '{"projections": []}', "projections": []}
    raw = RECORDED_ORDER_OUTPUTS[order - 1]
    return {
        "order": order,
        "model": "fixture",
        "input": {"fixture": True, "order": order},
        "output": raw,
        "projections": parse_order(raw, order, state),
    }
