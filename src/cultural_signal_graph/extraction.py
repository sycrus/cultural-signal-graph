"""Extraction stage — real cheap-model call (issue #3).

Turns a source corpus into typed Signal/Entity JSON with source + confidence by
calling DeepSeek's cheap model (`deepseek-v4-flash`). Parses and validates the
model's JSON into an `Extraction`, and logs token usage per run.

The model call is a thin seam (`_call_model`) so tests inject a recorded fixture.
Cross-domain edge proposal lives in `alignment.py`, not here (issue #5).
"""

from __future__ import annotations

import json
import logging

from .llm import call_model, expand_curie, extract_json
from .models import Entity, Extraction, Signal, SourceDoc, Usage
from .tracing import get_tracer, model_span, record_usage

logger = logging.getLogger(__name__)

EXTRACTION_MODEL = "deepseek-v4-flash"

_ENTITY_TYPES = ["tech:Product", "tech:Brand", "tech:Launch", "gaming:Peripheral"]

_SYSTEM_PROMPT = (
    "You extract structured signals from a small source corpus for a trend forecast. "
    "Return a single JSON object only — no prose, no markdown fences."
)


def _build_prompt(corpus: list[SourceDoc]) -> str:
    lines = [
        "Given this source corpus, extract the entities and the signals that mention them.",
        "",
        "Available entity_type values: " + ", ".join(_ENTITY_TYPES),
        "",
        "Corpus:",
    ]
    for source in corpus:
        lines.append(f"- {source.uri} (category: {source.category}): {source.text}")
    lines += [
        "",
        "Return JSON with exactly these keys:",
        '  "entities": [{"id", "name", "category", "entity_type"}] — entity_type is one of the available values above;',
        '  "signals": [{"id", "text", "about_entity_id", "source_uri", "confidence", "timestamp", "valid_from", "valid_until", "polarity"}]',
        '    — source_uri must be one of the corpus URIs; polarity is "support" or "refute"; confidence is a number in 0..1; timestamps are ISO-8601.',
    ]
    return "\n".join(lines)


def _call_model(corpus: list[SourceDoc]) -> tuple[str, Usage]:
    """The seam. Returns (raw model text, usage); monkeypatched in tests."""
    return call_model(EXTRACTION_MODEL, _SYSTEM_PROMPT, _build_prompt(corpus), max_tokens=16000)


def _require(obj: dict, key: str):
    if key not in obj:
        raise ValueError(f"missing required field {key!r}")
    return obj[key]


def parse_extraction(raw_json: str) -> Extraction:
    """Parse + validate a model's JSON response into a typed Extraction."""
    data = json.loads(extract_json(raw_json))
    if not isinstance(data, dict):
        raise ValueError("extraction JSON must be a top-level object")

    entities = [
        Entity(
            id=_require(e, "id"),
            name=_require(e, "name"),
            category=_require(e, "category"),
            entity_type=expand_curie(_require(e, "entity_type")),
        )
        for e in _require(data, "entities")
    ]

    signals = []
    for s in _require(data, "signals"):
        sid = _require(s, "id")
        confidence = float(_require(s, "confidence"))
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"signal {sid} confidence out of range: {confidence}")
        polarity = _require(s, "polarity")
        if polarity not in ("support", "refute"):
            raise ValueError(f"signal {sid} invalid polarity: {polarity!r}")
        signals.append(
            Signal(
                id=sid,
                text=_require(s, "text"),
                about_entity_id=_require(s, "about_entity_id"),
                source_uri=_require(s, "source_uri"),
                confidence=confidence,
                timestamp=_require(s, "timestamp"),
                valid_from=_require(s, "valid_from"),
                valid_until=_require(s, "valid_until"),
                polarity=polarity,
            )
        )

    return Extraction(entities=entities, signals=signals)


def extract(corpus: list[SourceDoc]) -> Extraction:
    """Run the cheap-model extraction, retrying once on parse/validation failure."""
    with get_tracer().start_as_current_span("extract") as span:
        span.set_attribute("input.sources", len(corpus))
        last_error: Exception | None = None
        for attempt in range(2):
            with model_span() as model:
                text, usage = _call_model(corpus)
                record_usage(model, usage)
            logger.info(
                "extraction model call: model=%s input_tokens=%d output_tokens=%d total_tokens=%d",
                usage.model,
                usage.input_tokens,
                usage.output_tokens,
                usage.total_tokens,
            )
            try:
                result = parse_extraction(text)
            except ValueError as exc:
                last_error = exc
                logger.warning("extraction parse failed (attempt %d): %s", attempt + 1, exc)
            else:
                span.set_attribute("output.entities", len(result.entities))
                span.set_attribute("output.signals", len(result.signals))
                return result
        raise ValueError(f"extraction failed after 2 attempts: {last_error}") from last_error
