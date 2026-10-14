"""The 2×2 Matrix lens (intuitive-logics scenario planning), axis-first.

1. The model proposes 3-4 critical uncertainties as candidate axes, drawn from the
   forecast's flagged / conflicting signals and from where branches diverge most;
   each cites the anchors it came from. The strategist picks two (or edits them).
2. Projections are placed into the four quadrants (lens tags, like any lens).
3. The strategist can seed a branch per quadrant, conditioned on that quadrant's
   axis values, so all four worlds get explored — not just where trends point.
4. The lens writes a short scenario narrative per quadrant: an annotation (a
   synthesis with provenance), never a projection.

Quadrants: q1 = A high, B high · q2 = A low, B high · q3 = A low, B low ·
q4 = A high, B low.
"""

from __future__ import annotations

import json

from ..config import futures_model
from ..llm import call_model, extract_json
from ..tracing import get_tracer, model_span, record_usage

QUADRANTS = ("q1", "q2", "q3", "q4")
POLES = {"q1": ("high", "high"), "q2": ("low", "high"), "q3": ("low", "low"), "q4": ("high", "low")}

SYSTEM = (
    "You are a scenario planner using the 2x2 matrix (intuitive logics). You reason about "
    "critical uncertainties: high impact and genuinely unresolved. You never give "
    "probabilities. Return a single JSON object only."
)


def world(axes: list[dict], quadrant: str) -> str:
    """A quadrant as words: 'regulation is restrictive and appetite is eager'."""
    a, b = POLES[quadrant]
    return f"{axes[0]['name']} is {axes[0][a]} and {axes[1]['name']} is {axes[1][b]}"


def _call(prompt: str, call_type: str, span: str, max_tokens: int = 3000) -> dict:
    model, temperature = futures_model(call_type)
    with get_tracer().start_as_current_span(span):
        with model_span() as model_call:
            text, usage = call_model(model, SYSTEM, prompt, max_tokens=max_tokens, temperature=temperature)
            record_usage(model_call, usage)
    return {
        "model": model,
        "temperature": temperature,
        "input": {"system": SYSTEM, "prompt": prompt},
        "output": text,
        "usage": {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
    }


def _clean_axis(a: dict, anchors: dict) -> dict:
    for key in ("name", "low", "high"):
        if not str(a.get(key, "")).strip():
            raise ValueError(f"an axis needs a {key}")
    return {
        "name": str(a["name"]).strip(),
        "low": str(a["low"]).strip(),
        "high": str(a["high"]).strip(),
        "from": [i for i in a.get("from", []) if i in anchors],
        "why": str(a.get("why", "")).strip(),
    }


def propose_axes(state: dict, live: bool) -> dict:
    anchors = state["anchors"]
    flagged = [a for a in anchors.values() if a.get("flag") or a.get("pending")]
    if not live:
        candidates = [
            {"name": "Privacy regulation of always-on devices", "low": "permissive", "high": "restrictive",
             "from": [a["id"] for a in flagged][:2], "why": "flagged evidence disagrees on whether always-on capture will be tolerated"},
            {"name": "Consumer appetite for AI devices", "low": "indifferent", "high": "eager",
             "from": [a["id"] for a in anchors.values() if a.get("flag") == "conflict"][:2],
             "why": "a conflict between rising search interest and 'solutions looking for a problem'"},
            {"name": "Who controls the platform", "low": "open ecosystems", "high": "closed incumbents",
             "from": [], "why": "branches diverge on whether glasses become their own platform"},
        ]
        return {"model": "fixture", "candidates": [_clean_axis(c, anchors) for c in candidates]}
    lines = [
        f"Exploration goal: {state['exploration']['goal']}",
        "",
        "Evidence (anchors) — flagged and pending ones are contested:",
    ]
    for a in anchors.values():
        marks = ", ".join(m for m in (a.get("flag"), "pending" if a.get("pending") else None) if m)
        lines.append(f"- {a['id']}{f' [{marks}]' if marks else ''}: {a['text']}")
    if state["projections"]:
        lines += ["", "Projections so far (where branches diverge is informative):"]
        for p in sorted(state["projections"].values(), key=lambda p: (p["order"], p["id"])):
            lines.append(f"- {p['id']} (order {p['order']}): {p['statement']}")
    lines += [
        "",
        "Propose 3 or 4 candidate axes for a 2x2 scenario matrix: critical uncertainties with "
        "high impact on the goal and no settled answer. Prefer the uncertainties the contested "
        "evidence points at. Each axis has two poles, each a short label of 1-4 words "
        "(e.g. 'permissive' / 'restrictive'); put the reasoning in `why`.",
        'Return JSON: {"axes": [{"name", "low", "high", "from": [anchor ids it comes from], "why"}]}',
    ]
    payload = _call("\n".join(lines), "axes", "futures_matrix_axes")
    data = json.loads(extract_json(payload["output"]))
    payload["candidates"] = [_clean_axis(a, anchors) for a in data.get("axes", [])][:4]
    if len(payload["candidates"]) < 2:
        raise ValueError("the model proposed fewer than two axes; try again")
    return payload


def narrative(state: dict, axes: list[dict], quadrant: str, projections: list[dict], live: bool) -> dict:
    words = world(axes, quadrant)
    if not live:
        lead = "; ".join(p["statement"].rstrip(".") for p in projections[:3])
        text = f"In a world where {words}: {lead}." if lead else f"In a world where {words}, nothing has been explored yet."
        return {"model": "fixture", "text": text}
    lines = [
        f"Exploration goal: {state['exploration']['goal']}",
        f"Scenario world: {words}.",
        "",
        "Projections placed in this world:",
        *[f"- ({p['window'][0]}-{p['window'][1]}) {p['statement']}" for p in projections],
        "",
        "Write the scenario narrative for this world in at most 90 words: what daily life and the "
        "market look like, and the key tension. Synthesize only from the projections above.",
        'Return JSON: {"narrative": "..."}',
    ]
    payload = _call("\n".join(lines), "narrative", "futures_matrix_narrative", max_tokens=800)
    payload["text"] = str(json.loads(extract_json(payload["output"])).get("narrative", "")).strip()
    if not payload["text"]:
        raise ValueError("the model wrote no narrative; try again")
    return payload
