"""Alignment stage — premium model proposes cross-domain equivalence edges (issue #5).

Calls DeepSeek's premium model (`deepseek-v4-pro`) to propose cross-domain
equivalence edges between entities from different sub-ontologies, each with a
confidence. Parses and validates the model's JSON, and logs token usage.

The model call is a thin seam (`_call_alignment_model`) so tests inject a fixture.
"""

from __future__ import annotations

import json
import logging

from .llm import call_model, extract_json
from .models import EquivalenceEdge, Extraction, Usage
from .tracing import get_tracer, model_span, record_usage

logger = logging.getLogger(__name__)

ALIGNMENT_MODEL = "deepseek-v4-pro"

_SYSTEM_PROMPT = (
    "You propose cross-domain equivalence edges between entities from different "
    "sub-ontologies. Return a single JSON array only — no prose, no markdown fences."
)


def _build_prompt(extraction: Extraction) -> str:
    lines = [
        "Given these entities and their signals, propose cross-domain equivalence edges — "
        "pairs of entities from *different* categories that likely mean the same thing — "
        "each with a confidence.",
        "",
        "Entities:",
    ]
    for entity in extraction.entities:
        lines.append(
            f"- {entity.id} (category {entity.category}, {entity.entity_type}): {entity.name}"
        )
    lines += ["", "Signals (context):"]
    for signal in extraction.signals:
        lines.append(f"- {signal.id} about {signal.about_entity_id}: {signal.text}")
    lines += [
        "",
        'Return a JSON array: [{"id", "left_entity_id", "right_entity_id", "confidence"}]',
        "  — only cross-domain pairs (left category != right category); confidence is a number in 0..1.",
    ]
    return "\n".join(lines)


def _call_alignment_model(extraction: Extraction) -> tuple[str, Usage]:
    """The seam. Returns (raw model text, usage); monkeypatched in tests."""
    return call_model(ALIGNMENT_MODEL, _SYSTEM_PROMPT, _build_prompt(extraction), max_tokens=16000)


def _require(obj: dict, key: str):
    if key not in obj:
        raise ValueError(f"missing required field {key!r}")
    return obj[key]


def parse_alignment(raw_json: str) -> list[EquivalenceEdge]:
    """Parse + validate a model's JSON array into typed equivalence edges."""
    data = json.loads(extract_json(raw_json))
    if not isinstance(data, list):
        raise ValueError("alignment JSON must be a top-level array")
    edges = []
    for e in data:
        edge_id = _require(e, "id")
        confidence = float(_require(e, "confidence"))
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"edge {edge_id} confidence out of range: {confidence}")
        edges.append(
            EquivalenceEdge(
                id=edge_id,
                left_entity_id=_require(e, "left_entity_id"),
                right_entity_id=_require(e, "right_entity_id"),
                confidence=confidence,
            )
        )
    return edges


def align(extraction: Extraction) -> list[EquivalenceEdge]:
    """Run the premium-model alignment, retrying once on parse/validation failure."""
    with get_tracer().start_as_current_span("align") as span:
        span.set_attribute("input.entities", len(extraction.entities))
        last_error: Exception | None = None
        for attempt in range(2):
            with model_span() as model:
                text, usage = _call_alignment_model(extraction)
                record_usage(model, usage)
            logger.info(
                "alignment model call: model=%s input_tokens=%d output_tokens=%d total_tokens=%d",
                usage.model,
                usage.input_tokens,
                usage.output_tokens,
                usage.total_tokens,
            )
            try:
                result = parse_alignment(text)
            except ValueError as exc:
                last_error = exc
                logger.warning("alignment parse failed (attempt %d): %s", attempt + 1, exc)
            else:
                span.set_attribute("output.edges", len(result))
                return result
        raise ValueError(f"alignment failed after 2 attempts: {last_error}") from last_error
