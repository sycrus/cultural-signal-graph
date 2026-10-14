"""Drafting stage — premium model writes the reasoning chain per claim (issue #6).

Given the confident signals of an extraction (in the asked category, not flagged),
calls DeepSeek's premium model (`deepseek-v4-pro`) to write a concise reasoning
chain for each, grounded in the given source, confidence, and temporal validity.
Provenance stays structural — the model reasons about evidence, it doesn't invent it.

The model call is a thin seam (`_call_draft_model`) so tests inject a fixture.
"""

from __future__ import annotations

import json
import logging

from .flags import detect_flags
from .llm import call_model, extract_json
from .models import Extraction, Signal, Usage
from .tracing import get_tracer, model_span, record_usage

logger = logging.getLogger(__name__)

DRAFTING_MODEL = "deepseek-v4-pro"

_SYSTEM_PROMPT = (
    "You write a concise reasoning chain for each claim in a trend forecast brief. "
    "Return a single JSON array only — no prose, no markdown fences. "
    "Reason only from the evidence given; never invent sources or facts."
)


def _confident_signals(extraction: Extraction, category: str) -> list[Signal]:
    """Signals that become claims: in-category and not flagged."""
    flagged = {f.signal_id for f in detect_flags(extraction.signals)}
    entity_by_id = {e.id: e for e in extraction.entities}
    return [
        s
        for s in extraction.signals
        if s.id not in flagged and entity_by_id[s.about_entity_id].category == category
    ]


def _build_prompt(signals: list[Signal], category: str) -> str:
    lines = [
        f"For each claim below, write a 1-2 sentence reasoning chain explaining how it "
        f"supports a {category} trend forecast. Ground each chain in the given source, "
        f"confidence, and temporal validity.",
        "",
        "Claims:",
    ]
    for s in signals:
        lines.append(
            f'- {s.id}: "{s.text}" (confidence {s.confidence}, '
            f"valid {s.valid_from} -> {s.valid_until}, source {s.source_uri})"
        )
    lines += [
        "",
        'Return a JSON array: [{"signal_id", "reasoning"}].',
    ]
    return "\n".join(lines)


def _call_draft_model(signals: list[Signal], category: str) -> tuple[str, Usage]:
    """The seam. Returns (raw model text, usage); monkeypatched in tests."""
    return call_model(DRAFTING_MODEL, _SYSTEM_PROMPT, _build_prompt(signals, category), max_tokens=16000)


def _require(obj: dict, key: str):
    if key not in obj:
        raise ValueError(f"missing required field {key!r}")
    return obj[key]


def parse_draft(raw_json: str) -> dict[str, str]:
    """Parse + validate a model's JSON array into a signal_id -> reasoning map."""
    data = json.loads(extract_json(raw_json))
    if not isinstance(data, list):
        raise ValueError("draft JSON must be a top-level array")
    reasoning: dict[str, str] = {}
    for item in data:
        signal_id = _require(item, "signal_id")
        reasoning[signal_id] = _require(item, "reasoning")
    return reasoning


def draft(extraction: Extraction, category: str) -> dict[str, str]:
    """Draft a reasoning chain per confident signal, retrying once on failure."""
    with get_tracer().start_as_current_span("draft") as span:
        signals = _confident_signals(extraction, category)
        span.set_attribute("input.claims", len(signals))
        if not signals:
            return {}
        last_error: Exception | None = None
        for attempt in range(2):
            with model_span() as model:
                text, usage = _call_draft_model(signals, category)
                record_usage(model, usage)
            logger.info(
                "drafting model call: model=%s input_tokens=%d output_tokens=%d total_tokens=%d",
                usage.model,
                usage.input_tokens,
                usage.output_tokens,
                usage.total_tokens,
            )
            try:
                result = parse_draft(text)
            except ValueError as exc:
                last_error = exc
                logger.warning("draft parse failed (attempt %d): %s", attempt + 1, exc)
            else:
                span.set_attribute("output.reasoning", len(result))
                return result
        raise ValueError(f"drafting failed after 2 attempts: {last_error}") from last_error
