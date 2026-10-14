"""The futures generator: one call per order, each appended as a `generate_order` op.

A generator function takes `(state, order)` and returns the op payload: the model,
its full input, its raw output, and the parsed projections. `fixture_generator`
replays the recorded fixture outputs (no model); `live_generator` calls the model.

Model output format (one JSON object per order):

    {"projections": [{"id", "statement", "from": [ids], "window": [start, end],
                      "baseline": bool, "discontinuity": bool}]}

`from` mixes anchor ids and projection ids from earlier orders; the parser splits
them into `anchors` and `parents`. Several ids = convergence.
"""

from __future__ import annotations

import json
import logging

from ..config import futures_cap, futures_model
from ..llm import call_model, extract_json
from ..tracing import get_tracer, model_span, record_usage
from .fixtures import FIXTURE_BRANCH_LINES, RECORDED_ORDER_OUTPUTS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a futures-thinking generator using the Futures Wheel method: you grow "
    "consequences from evidence, one order (causal depth) at a time. You never give "
    "probabilities. Return a single JSON object only, no prose, no markdown fences."
)


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


def caps() -> tuple[int, int]:
    """(max projections per order, max children per source), env-tunable."""
    return futures_cap("max_per_order", 6), futures_cap("max_children", 3)


def finalize_order(projections: list[dict], state: dict, order: int, branch: dict | None = None) -> list[dict]:
    """Enforce the invariants a model can't be trusted with: windows inside the
    horizon, the caps, and exactly one baseline continuing the previous one.

    For a `branch` (regenerate / fork), every projection must grow from the branch
    frontier, and the baseline continues only if the branch carries it."""
    e = state["exploration"]
    first, last = e["start_year"], e["start_year"] + e["horizon"]
    out = []
    if branch is not None:
        frontier = set(branch["frontier"])
        projections = [p for p in projections if set(p["parents"] + p["anchors"]) & frontier]
    for p in projections:
        start, end = p["window"]
        if start > last:
            continue  # beyond the horizon: the time limit stops it
        out.append({**p, "window": [max(start, first), min(max(end, start), last)]})

    # caps: baseline first, then discontinuities, so the invariants survive truncation
    out.sort(key=lambda p: (not p["baseline"], not p["discontinuity"]))
    max_per_order, max_children = caps()
    used: dict[str, int] = {}
    kept = []
    for p in out:
        sources = p["parents"] + p["anchors"]
        if len(kept) >= max_per_order or min(used.get(s, 0) for s in sources) >= max_children:
            continue
        for s in sources:
            used[s] = used.get(s, 0) + 1
        kept.append(p)

    # exactly one baseline: order 1 opens it; later orders continue the previous one
    if branch is not None:
        prev = {f for f in branch["frontier"] if state["projections"].get(f, {}).get("baseline")} if branch["baseline"] else set()
        eligible = [p for p in kept if set(p["parents"]) & prev]
    else:
        prev = {q["id"] for q in state["projections"].values() if q["baseline"] and q["order"] == order - 1}
        eligible = [p for p in kept if order == 1 or set(p["parents"]) & prev]
    chosen = next((p for p in eligible if p["baseline"]), eligible[0] if eligible else None)
    for p in kept:
        p["baseline"] = p is chosen
    return kept


def build_prompt(state: dict, order: int, branch: dict | None = None) -> str:
    e = state["exploration"]
    first, last = e["start_year"], e["start_year"] + e["horizon"]
    max_per_order, max_children = caps()
    lines = [
        f"Goal of this exploration: {e['goal']}",
        f"Time horizon: {first} to {last}. Generate order {order} of {e['orders']}.",
        "",
        "Anchors (the evidence, as of the present):",
    ]
    for a in state["anchors"].values():
        flag = f" [flagged: {a['flag']}]" if a.get("flag") else ""
        lines.append(f"- {a['id']} ({a['kind']}{flag}): {a['text']}")
    earlier = sorted(state["projections"].values(), key=lambda p: (p["order"], p["id"]))
    if earlier:
        lines += ["", "Projections so far (id, order, years, statement):"]
        for p in earlier:
            marks = (" [baseline]" if p["baseline"] else "") + (" [discontinuity]" if p["discontinuity"] else "")
            lines.append(
                f"- {p['id']} (order {p['order']}, {p['window'][0]}-{p['window'][1]}){marks}: {p['statement']}"
            )
    if branch is None:
        source = "anchor ids" if order == 1 else f"ids of order-{order - 1} projections (anchor ids may be added)"
        baseline = "of the trend" if order == 1 else "continuing the current baseline projection"
        rules = [
            f"Write the order-{order} consequences. Decide how many: at most {max_per_order} in total and "
            f"at most {max_children} growing from any one source.",
            f"- `from` lists the {source} each projection grows from. Several ids = convergence: use it when "
            "different paths arrive at the same outcome instead of writing near-duplicates.",
            f"- Exactly one projection is the baseline (`baseline: true`): the business-as-usual extrapolation {baseline}.",
            "- At least one projection is a discontinuity (`discontinuity: true`): a break from trend, still "
            "grounded in the evidence above.",
        ]
    else:
        frontier = ", ".join(branch["frontier"])
        rules = [
            f"Grow a {branch['kind']} branch: write the order-{order} consequences of ONLY these: "
            f"{frontier}. At most {max_children} from each, {max_per_order} in total.",
            "- `from` must include at least one of those ids; add any other existing id where the branch "
            "converges with it.",
            "- Exactly one projection is the baseline (`baseline: true`), continuing the baseline projection above."
            if branch["baseline"]
            else "- None of these is the baseline (`baseline: false`).",
            "- Mark a break from trend as a discontinuity (`discontinuity: true`).",
        ]
        if branch.get("hint"):
            rules.insert(
                1,
                f"- The strategist asks: what if {branch['hint']}? Treat it as the premise of this whole "
                "branch: every projection plays out in a world where it happened.",
            )
        if branch.get("world"):
            rules.insert(
                1,
                f"- This branch explores one scenario world: {branch['world']}. Every projection must be "
                "consistent with that world, even where today's trends point elsewhere.",
            )
    lines += [
        "",
        *rules,
        "- `window` is [start_year, end_year] within the horizon: when it would happen. Order is causal "
        "depth, not time: set the years on their own merits, but never before what it grows from.",
        "",
        'Return JSON: {"projections": [{"id", "statement", "from", "window", "baseline", "discontinuity"}]} '
        f'with short ids like "o{order}-<slug>" and one-sentence statements.',
    ]
    return "\n".join(lines)


def _call_generation_model(prompt: str, call_type: str = "generate"):
    """The seam: (raw text, usage, model, temperature); monkeypatched in tests."""
    model, temperature = futures_model(call_type)
    text, usage = call_model(model, SYSTEM_PROMPT, prompt, max_tokens=8000, temperature=temperature)
    return text, usage, model, temperature


def run_generation(
    prompt: str,
    parse,
    call_type: str = "generate",
    span_name: str = "futures_generate",
    require_discontinuity: bool = True,
):
    """One generation call, retried once on a parse failure or a missing
    discontinuity. `parse(text)` returns finalized projections. Returns the op
    payload fields: model, temperature, full input, raw output, warnings, projections."""
    with get_tracer().start_as_current_span(span_name) as span:
        warnings: list[str] = []
        projections: list[dict] = []
        attempts = []
        for attempt in range(2):
            with model_span() as model_call:
                text, usage, model, temperature = _call_generation_model(prompt, call_type)
                record_usage(model_call, usage)
            attempts.append(text)
            try:
                projections = parse(text)
            except (ValueError, KeyError, TypeError) as exc:
                logger.warning("generation parse failed (attempt %d): %s", attempt + 1, exc)
                if attempt == 1:
                    raise ValueError(f"generation failed: {exc}") from exc
                continue
            if not require_discontinuity or not projections or any(p["discontinuity"] for p in projections):
                break
            if attempt == 1:
                warnings.append("no discontinuity in this generation")
        span.set_attribute("futures.projections", len(projections))
    return {
        "model": model,
        "temperature": temperature,
        "input": {"system": SYSTEM_PROMPT, "prompt": prompt},
        "output": attempts[-1],
        "attempts": len(attempts),
        "usage": {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
        "warnings": warnings,
        "projections": projections,
    }


def live_generator(state: dict, order: int) -> dict:
    """One model call for one order, parsed and finalized."""
    payload = run_generation(
        build_prompt(state, order),
        lambda text: finalize_order(parse_order(text, order, state), state, order),
        span_name="futures_generate_order",
    )
    return {"order": order, **payload}


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
        "projections": finalize_order(parse_order(raw, order, state), state, order),
    }


def live_branch_generator(state: dict, order: int, branch: dict) -> dict:
    """One model call for one order of a branch grown from `branch["frontier"]`.
    `branch` = {kind: "regenerated"|"fork", frontier: [ids], baseline: bool, hint}."""
    call_type = "generate" if branch["kind"] == "regenerated" else "fork"

    def parse(text):
        return _mark(finalize_order(parse_order(text, order, state), state, order, branch), branch)

    payload = run_generation(
        build_prompt(state, order, branch),
        parse,
        call_type=call_type,
        span_name=f"futures_{branch['kind']}_order",
        require_discontinuity=False,
    )
    return {"order": order, **payload}


def fixture_branch_generator(state: dict, order: int, branch: dict) -> dict:
    """Offline stand-in for a branch: one deterministic consequence per frontier
    node, so fork and regenerate are explorable without a model."""
    e = state["exploration"]
    last = e["start_year"] + e["horizon"]
    items = []
    for i, fid in enumerate(branch["frontier"]):
        parent = state["projections"].get(fid, {"window": [e["start_year"], e["start_year"]], "baseline": False})
        start = min(parent["window"][1], last)
        line = FIXTURE_BRANCH_LINES[(order + i) % len(FIXTURE_BRANCH_LINES)]
        premise = branch.get("hint") or branch.get("world")
        statement = f"If {premise}: {line[0].lower()}{line[1:]}" if premise else line
        items.append(
            {
                "id": f"o{order}-{branch['kind']}-{fid}",
                "statement": statement,
                "from": [fid],
                "window": [start, min(start + 2, last)],
                "baseline": bool(branch["baseline"] and parent["baseline"]),
                "discontinuity": i == 0,
            }
        )
    raw = json.dumps({"projections": items}, indent=2)
    projections = _mark(finalize_order(parse_order(raw, order, state), state, order, branch), branch)
    return {"order": order, "model": "fixture", "input": {"fixture": True, "branch": branch}, "output": raw, "projections": projections}


_ORIGIN = {"fork": "forked", "seeded": "seeded", "regenerated": "generated"}


def _mark(projections: list[dict], branch: dict) -> list[dict]:
    """Stamp a branch's projections with their origin and the premise they grew under."""
    for p in projections:
        p["origin"] = _ORIGIN[branch["kind"]]
        if branch.get("hint"):
            p["hint"] = branch["hint"]
        if branch.get("world"):
            p["hint"] = branch["world"]
    return projections


SUMMARY_SYSTEM = (
    "You condense a source excerpt into one plain sentence (at most 25 words) stating "
    "what it says, for use as evidence. No opinions, no prose around it."
)


def summarize_reference(url: str, excerpt: str, live: bool) -> dict:
    """One line the generator can use, with the call's full input/output kept for the
    op. Fixture mode (no model) takes the excerpt's first sentence."""
    if not live:
        first = excerpt.strip().split(". ")[0].strip().rstrip(".")
        return {"text": (first[:157] + "...") if len(first) > 160 else first, "model": None}
    prompt = f"Source: {url}\nExcerpt:\n{excerpt.strip()}"
    model, temperature = futures_model("summarize")
    with get_tracer().start_as_current_span("futures_summarize_reference"):
        with model_span() as model_call:
            text, usage = call_model(model, SUMMARY_SYSTEM, prompt, max_tokens=200, temperature=temperature)
            record_usage(model_call, usage)
    return {
        "text": text.strip().strip('"'),
        "model": model,
        "temperature": temperature,
        "input": {"system": SUMMARY_SYSTEM, "prompt": prompt},
        "output": text,
    }
