"""Lens tagging (ADR-0007): a lens organizes the same projections by qualitative
tags. On first open, one cheap-model call (temperature 0) tags every untagged
projection; the strategist overrides any tag. Both are `retag` ops, so tags are
cached, replayable, attributed, and undoable.

A tag is `{"value": str, ...extras}`. Each lens declares its allowed values, what
the model should judge, any tags fixed by construction (the baseline is
"projected" in the Cone), and a deterministic fixture stand-in for offline mode.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from ..config import futures_model
from ..llm import call_model, extract_json
from ..tracing import get_tracer, model_span, record_usage


@dataclass(frozen=True)
class LensSpec:
    key: str
    values: tuple[str, ...]
    instructions: str
    fixed: Callable[[dict], dict | None] = lambda p: None
    fixture: Callable[[dict], dict] = lambda p: {}
    extras: dict[str, str] = field(default_factory=dict)  # extra field -> its description
    clean_extras: Callable[[dict], dict] = lambda t: {}
    context: Callable[[dict], str] = lambda state: ""  # state-dependent instructions
    ready: Callable[[dict], str | None] = lambda state: None  # why it can't classify yet


def _cone_fixed(p: dict) -> dict | None:
    if p.get("baseline"):
        return {"value": "projected", "preferable": False}
    if p.get("origin") == "wildcard":
        return {"value": "preposterous", "preferable": False}
    return None


def _cone_fixture(p: dict) -> dict:
    return {"value": "possible" if p.get("discontinuity") else "plausible", "preferable": False}


CONE = LensSpec(
    key="cone",
    values=("projected", "plausible", "possible", "preposterous"),
    instructions=(
        "Classify each projection with the Futures Cone (Voros), as its innermost class: "
        "'projected' = the business-as-usual continuation; 'plausible' = could happen given "
        "current knowledge and how things work; 'possible' = could happen but needs knowledge "
        "or conditions we lack; 'preposterous' = we would currently judge it impossible. "
        "Separately, 'preferable' = true if it moves toward what the exploration's goal would "
        "want. These are qualitative judgements, not probabilities."
    ),
    fixed=_cone_fixed,
    fixture=_cone_fixture,
    extras={"preferable": "true/false: does it serve the exploration's goal"},
    clean_extras=lambda t: {"preferable": bool(t.get("preferable", False))},
)

def _matrix_context(state: dict) -> str:
    a, b = state["axes"]
    return (
        f"Axis A: {a['name']} (low = {a['low']}, high = {a['high']}). "
        f"Axis B: {b['name']} (low = {b['low']}, high = {b['high']}). "
        "Place each projection in the quadrant of the world it belongs to: q1 = A high & B high, "
        "q2 = A low & B high, q3 = A low & B low, q4 = A high & B low; 'none' if it says nothing "
        "about either axis."
    )


def _matrix_fixture(p: dict) -> dict:
    return {"value": ("q1", "q2", "q3", "q4")[sum(map(ord, p["id"])) % 4]}


MATRIX = LensSpec(
    key="matrix",
    values=("q1", "q2", "q3", "q4", "none"),
    instructions="Organize the projections with a 2x2 scenario matrix (intuitive logics).",
    fixture=_matrix_fixture,
    context=_matrix_context,
    ready=lambda state: None if state.get("axes") else "pick two axes for the matrix first",
)

LENSES: dict[str, LensSpec] = {CONE.key: CONE, MATRIX.key: MATRIX}

CLASSIFY_SYSTEM = (
    "You organize speculative projections with a futures-thinking framework. You give "
    "qualitative tags only, never probabilities. Return a single JSON object only."
)


def lens(key: str) -> LensSpec:
    if key not in LENSES:
        raise KeyError(f"unknown lens: {key}")
    return LENSES[key]


def clean_tag(spec: LensSpec, tag: dict) -> dict:
    value = tag.get("value")
    if value not in spec.values:
        raise ValueError(f"{spec.key} tag must be one of {', '.join(spec.values)}; got {value!r}")
    return {"value": value, **spec.clean_extras(tag)}


def build_prompt(spec: LensSpec, state: dict, projections: list[dict]) -> str:
    lines = [
        f"Exploration goal: {state['exploration']['goal']}",
        "",
        spec.instructions,
        spec.context(state),
        f"Allowed values: {', '.join(spec.values)}.",
        "",
        "Projections (id, years, statement):",
    ]
    for p in projections:
        lines.append(f"- {p['id']} ({p['window'][0]}-{p['window'][1]}): {p['statement']}")
    fields = ", ".join(['"value"', *(f'"{k}" ({d})' for k, d in spec.extras.items())])
    lines += ["", f'Return JSON: {{"tags": {{"<projection id>": {{{fields}}}}}}} for every projection above.']
    return "\n".join(lines)


def classify(spec: LensSpec, state: dict, projections: list[dict], live: bool) -> dict:
    """Tag `projections` for one lens. Returns the op payload: tags (+ model I/O)."""
    why_not = spec.ready(state)
    if why_not:
        raise ValueError(why_not)
    tags: dict[str, dict] = {}
    to_ask = []
    for p in projections:
        fixed = spec.fixed(p)
        if fixed is not None:
            tags[p["id"]] = {**fixed, "fixed": True}
        else:
            to_ask.append(p)
    payload: dict = {"model": None}
    if to_ask and not live:
        for p in to_ask:
            tags[p["id"]] = clean_tag(spec, {"value": spec.values[0], **spec.fixture(p)})
        payload["model"] = "fixture"
    elif to_ask:
        prompt = build_prompt(spec, state, to_ask)
        model, temperature = futures_model("classify")
        with get_tracer().start_as_current_span(f"futures_classify_{spec.key}") as span:
            span.set_attribute("futures.projections", len(to_ask))
            with model_span() as model_call:
                text, usage = call_model(model, CLASSIFY_SYSTEM, prompt, max_tokens=4000, temperature=temperature)
                record_usage(model_call, usage)
        data = json.loads(extract_json(text)).get("tags", {})
        for p in to_ask:
            try:
                tags[p["id"]] = clean_tag(spec, data.get(p["id"], {}))
            except ValueError:
                pass  # left untagged: shown as such, and a later open asks again
        payload.update(
            model=model,
            temperature=temperature,
            input={"system": CLASSIFY_SYSTEM, "prompt": prompt},
            output=text,
            usage={"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
        )
    payload["tags"] = tags
    return payload
