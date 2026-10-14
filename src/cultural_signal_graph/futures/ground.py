"""Ground this (PRD-futures.md §6): the one agent in futures mode.

A bounded search loop for evidence that supports OR contradicts a projection:

    1. the model writes search queries aimed at both stances;
    2. the discovery search tool runs them (the same free search the forecast uses);
    3. the model judges each result — supports / contradicts / irrelevant — with a
       short excerpt and why; if nothing usable came back it may ask for one more
       round of refined queries (at most MAX_ROUNDS searches in total).

Nothing is added on its own: the result is a set of proposals (with the whole
trail: queries, results examined, judgments) that the strategist accepts one by
one as futures-scoped references.
"""

from __future__ import annotations

import json

from .. import discovery
from ..config import futures_model
from ..llm import call_model, extract_json
from ..tracing import get_tracer, model_span, record_usage

MAX_ROUNDS = 2
MAX_RESULTS = 5
MAX_PROPOSALS = 4

SYSTEM = (
    "You ground speculative projections in evidence: news, government forecasts and plans, "
    "research. You look for evidence on BOTH sides. Return a single JSON object only."
)


def _call(prompt: str, step: str) -> tuple[dict, dict]:
    model, temperature = futures_model("ground")
    with get_tracer().start_as_current_span(f"futures_ground_{step}"):
        with model_span() as model_call:
            text, usage = call_model(model, SYSTEM, prompt, max_tokens=2500, temperature=temperature)
            record_usage(model_call, usage)
    data = json.loads(extract_json(text))
    return data, {
        "step": step,
        "model": model,
        "temperature": temperature,
        "input": {"system": SYSTEM, "prompt": prompt},
        "output": text,
        "usage": {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
    }


def _queries_prompt(goal: str, statement: str, tried: list[str]) -> str:
    lines = [
        f"Exploration goal: {goal}",
        f"Projection to ground: {statement}",
        "",
        "Write 2-3 short web search queries that would find evidence for it AND against it "
        "(news, government forecasts or plans, studies).",
    ]
    if tried:
        lines.append("Already tried (found nothing usable): " + "; ".join(tried))
    lines.append('Return JSON: {"queries": ["...", "..."]}')
    return "\n".join(lines)


def _judge_prompt(statement: str, results: list[dict], can_retry: bool) -> str:
    lines = [f"Projection: {statement}", "", "Search results:"]
    for i, r in enumerate(results):
        lines.append(f"[{i}] {r['title']} ({r['url']}): {r['snippet']}")
    lines += [
        "",
        "For each result that genuinely bears on the projection, say whether it supports or "
        "contradicts it, quote or paraphrase ONE COMPLETE sentence or clause as the excerpt — "
        "never a fragment — and say why in one line. Skip irrelevant results: returning no "
        "judgments is better than stretching a keyword match.",
        'Return JSON: {"judgments": [{"index", "stance": "support"|"contradict", "excerpt", "why"}]'
        + (', "more_queries": [...] only if nothing above is usable}' if can_retry else "}"),
    ]
    return "\n".join(lines)


def ground(state: dict, target: dict, live: bool) -> dict:
    """Run the bounded loop for one projection (or assumption). Returns the op payload:
    proposals + the trail (queries, results, every model step's I/O)."""
    statement = target["statement"]
    if not live:
        slug = target["id"]
        return {
            "model": "fixture",
            "queries": [statement[:60]],
            "results": [],
            "steps": [],
            "errors": [],
            "proposals": [
                {"url": f"https://example.org/evidence/{slug}/for", "title": "Fixture: supporting evidence",
                 "excerpt": f"A recent plan points toward this: {statement[:80]}", "stance": "support",
                 "why": "fixture stand-in (no search offline)", "query": statement[:60]},
                {"url": f"https://example.org/evidence/{slug}/against", "title": "Fixture: contradicting evidence",
                 "excerpt": "Analysts expect the opposite within the decade.", "stance": "contradict",
                 "why": "fixture stand-in (no search offline)", "query": statement[:60]},
            ],
        }

    goal = state["exploration"]["goal"]
    steps: list[dict] = []
    tried: list[str] = []
    examined: list[dict] = []
    proposals: list[dict] = []
    errors: list[dict] = []  # per-query search failures — an empty round explains itself
    data, step = _call(_queries_prompt(goal, statement, tried), "queries")
    steps.append(step)
    queries = [str(q) for q in data.get("queries", [])][:3] or [statement[:80]]
    for round_no in range(MAX_ROUNDS):
        tried += queries
        results = discovery._search_records(queries, limit=MAX_RESULTS, errors=errors)
        seen = {r["url"] for r in examined}
        results = [r for r in results if r["url"] not in seen][: MAX_RESULTS * 2]
        examined += results
        if not results:
            break
        can_retry = round_no < MAX_ROUNDS - 1
        data, step = _call(_judge_prompt(statement, results, can_retry), "judge")
        steps.append(step)
        for j in data.get("judgments", []):
            try:
                r = results[int(j["index"])]
            except (KeyError, ValueError, IndexError, TypeError):
                continue
            excerpt = str(j.get("excerpt", "")).strip()
            # a fragment like "the government antitrust action, which" is keyword
            # noise, not evidence — demand a complete clause (the judge is told too)
            if j.get("stance") not in ("support", "contradict") or len(excerpt.split()) < 8:
                continue
            proposals.append({
                "url": r["url"], "title": r["title"], "excerpt": excerpt,
                "stance": j["stance"], "why": str(j.get("why", "")).strip(),
                "query": r.get("query"), "backend": r.get("backend"),
            })
        if proposals or not can_retry or not data.get("more_queries"):
            break
        queries = [str(q) for q in data["more_queries"]][:3]
    return {
        "model": steps[0]["model"],
        "queries": tried,
        "results": examined,
        "steps": steps,
        "proposals": proposals[:MAX_PROPOSALS],
        "errors": errors,
    }
