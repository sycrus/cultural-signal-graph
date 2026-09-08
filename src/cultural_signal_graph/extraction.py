"""Extraction stage — real cheap-model call (issue #3).

Turns a source corpus into typed Signal/Entity JSON with source + confidence by
calling DeepSeek's cheap model (`deepseek-v4-flash`) behind its
Anthropic-compatible endpoint. Parses and validates the model's JSON into an
`Extraction`, and logs token usage per run to feed the cost metric.

The model call is a thin seam (`_call_model`) so tests inject a recorded fixture
rather than hitting the network; `parse_extraction` is the pure, fixture-tested
parse + validate step.
"""

from __future__ import annotations

import json
import logging
import os

import anthropic

from .models import (
    CSG_NS,
    EX_NS,
    GAMING_NS,
    TECH_NS,
    Entity,
    EquivalenceEdge,
    Extraction,
    Signal,
    SourceDoc,
    Usage,
)

logger = logging.getLogger(__name__)

# Model routing (PRD "two tiers"). Pinned at build time.
EXTRACTION_MODEL = "deepseek-v4-flash"
PREMIUM_MODEL = "deepseek-v4-pro"  # reserved for alignment + drafting (#5/#6)

_BASE_URL = "https://api.deepseek.com/anthropic"
_PREFIXES = {"csg": CSG_NS, "tech": TECH_NS, "gaming": GAMING_NS, "ex": EX_NS}

_ENTITY_TYPES = ["tech:Product", "tech:Brand", "tech:Launch", "gaming:Peripheral"]

_SYSTEM_PROMPT = (
    "You extract structured signals from a small source corpus for a trend forecast. "
    "Return a single JSON object only — no prose, no markdown fences."
)


def _client() -> anthropic.Anthropic:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set; cannot call the extraction model")
    return anthropic.Anthropic(base_url=_BASE_URL, auth_token=key)


def _build_prompt(corpus: list[SourceDoc]) -> str:
    lines = [
        "Given this source corpus, extract the entities and signals, and propose any "
        "cross-domain equivalence edges.",
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
        '    — source_uri must be one of the corpus URIs; polarity is "support" or "refute"; confidence is a number in 0..1; timestamps are ISO-8601;',
        '  "proposed_edges": [{"id", "left_entity_id", "right_entity_id", "confidence"}] — only cross-domain equivalence edges.',
    ]
    return "\n".join(lines)


def _call_model(corpus: list[SourceDoc]) -> tuple[str, Usage]:
    """The seam. Returns (raw model text, usage); monkeypatched in tests."""
    response = _client().messages.create(
        model=EXTRACTION_MODEL,
        max_tokens=16000,
        # Cheap extraction wants the answer, not reasoning: deepseek-v4-flash
        # emits a thinking block by default that otherwise eats the token budget.
        thinking={"type": "disabled"},
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_prompt(corpus)}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    input_tokens = response.usage.input_tokens or 0
    output_tokens = response.usage.output_tokens or 0
    usage = Usage(
        model=EXTRACTION_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
    )
    return text, usage


def _expand(curie: str) -> str:
    if ":" in curie:
        prefix, local = curie.split(":", 1)
        if prefix in _PREFIXES:
            return _PREFIXES[prefix] + local
    return curie


def _require(obj: dict, key: str):
    if key not in obj:
        raise ValueError(f"missing required field {key!r}")
    return obj[key]


def parse_extraction(raw_json: str) -> Extraction:
    """Parse + validate a model's JSON response into a typed Extraction."""
    data = json.loads(raw_json)
    if not isinstance(data, dict):
        raise ValueError("extraction JSON must be a top-level object")

    entities = [
        Entity(
            id=_require(e, "id"),
            name=_require(e, "name"),
            category=_require(e, "category"),
            entity_type=_expand(_require(e, "entity_type")),
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

    proposed_edges = [
        EquivalenceEdge(
            id=_require(e, "id"),
            left_entity_id=_require(e, "left_entity_id"),
            right_entity_id=_require(e, "right_entity_id"),
            confidence=float(_require(e, "confidence")),
        )
        for e in _require(data, "proposed_edges")
    ]

    return Extraction(entities=entities, signals=signals, proposed_edges=proposed_edges)


def extract(corpus: list[SourceDoc]) -> Extraction:
    """Run the cheap-model extraction, retrying once on parse/validation failure."""
    last_error: Exception | None = None
    for attempt in range(2):
        text, usage = _call_model(corpus)
        logger.info(
            "extraction model call: model=%s input_tokens=%d output_tokens=%d total_tokens=%d",
            usage.model,
            usage.input_tokens,
            usage.output_tokens,
            usage.total_tokens,
        )
        try:
            return parse_extraction(text)
        except ValueError as exc:
            last_error = exc
            logger.warning("extraction parse failed (attempt %d): %s", attempt + 1, exc)
    raise ValueError(f"extraction failed after 2 attempts: {last_error}") from last_error
