"""Promotion (PRD-futures.md §7): the one deliberate crossing from futures back into
the forecast. Forecast sources lock once a run starts, so promoting a futures-scoped
reference creates a NEW forecast run — same ask, the original sources plus the
reference — and leaves the original run and its explorations untouched. The
exploration carries over to the new run, where a branch grows from the promoted
anchor (it may converge with what is already there).
"""

from __future__ import annotations

import json

from ..models import CSG_NS, SourceDoc, source_doc_from_dict
from .log import OperationLog
from .replay import replay

PROMOTED_CREDIBILITY = 0.6  # a strategist-supplied source, like one added by hand in Sources


def promote(runs, futures, run_id: str, exp_id: str, ref_id: str, author: str = "strategist") -> dict:
    state = replay(futures.ops(run_id, exp_id))
    ref = state["anchors"].get(ref_id)
    if ref is None or ref.get("scope") != "futures":
        raise KeyError(f"unknown futures-scoped reference: {ref_id}")
    original = runs.snapshot(run_id)
    ask = original["ask"]
    sources = [source_doc_from_dict(s) for s in original["sources"]]
    if any(s.uri == ref["source_uri"] for s in sources):
        raise ValueError("this reference is already one of the forecast's sources")
    sources.append(
        SourceDoc(
            uri=ref["source_uri"],
            source_type=CSG_NS + "Source",
            credibility=PROMOTED_CREDIBILITY,
            category=ask["category"],
            text=ref.get("excerpt") or ref["text"],
        )
    )
    origin = {"promoted_from": {"run": run_id, "exploration": exp_id, "reference": ref_id, "url": ref["source_uri"]}}
    new_run = runs.create(
        category=ask["category"],
        question=ask["question"],
        window_start=ask["window"]["start"],
        window_end=ask["window"]["end"],
        market=ask["market"],
        sources=sources,
        origin=origin,
    )

    # carry the exploration over: same ops, a fresh id on the new run ...
    log_text = "".join(json.dumps(o, ensure_ascii=False) + "\n" for o in futures.ops(run_id, exp_id))
    carried = futures.import_log(new_run["id"], log_text, author=author)
    new_exp = carried["exploration"]["id"]
    # ... then grow a branch from the promoted anchor, recorded as one op
    carried_state = replay(futures.ops(new_run["id"], new_exp))
    root = {"id": ref_id, "order": 0, "baseline": False}
    orders = futures._grow(carried_state, root, carried_state["exploration"]["orders"], kind="fork")
    log = OperationLog(futures._dir(new_run["id"], new_exp))
    log.append(
        {"op": "promote", "reference": ref_id, "promoted_from": origin["promoted_from"], "orders": orders},
        author=author,
    )
    return {"run": new_run, "exploration": futures.snapshot(new_run["id"], new_exp)}
