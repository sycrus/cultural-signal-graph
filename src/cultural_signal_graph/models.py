"""Shared dataclasses for the forecast pipeline's JSON seams.

These are the vocabulary the pipeline stages pass between each other
(corpus -> extraction -> graph -> flags -> brief). Keep them dependency-free:
stdlib dataclasses only, so the slice stays light and deterministic.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

# Ontology namespaces — shared by fixtures and graph construction.
CSG_NS = "https://cultural-signal-graph.dev/ontology#"
TECH_NS = "https://cultural-signal-graph.dev/ontology/tech#"
GAMING_NS = "https://cultural-signal-graph.dev/ontology/gaming#"
EX_NS = "https://cultural-signal-graph.dev/example#"


@dataclass(frozen=True)
class SourceDoc:
    """A document in the input corpus — the raw material extraction reads."""

    uri: str
    source_type: str
    credibility: float
    category: str
    text: str
    topics: tuple[str, ...] = ()


@dataclass(frozen=True)
class TimeWindow:
    """The time window an ask is scoped to."""

    start: str
    end: str


@dataclass(frozen=True)
class Ask:
    """The runtime input to a forecast: category + question + time window (+ market)."""

    category: str
    question: str
    window: TimeWindow
    market: str | None = None


@dataclass(frozen=True)
class Entity:
    id: str
    name: str
    category: str
    entity_type: str


@dataclass(frozen=True)
class Signal:
    id: str
    text: str
    about_entity_id: str
    source_uri: str
    confidence: float
    timestamp: str
    valid_from: str
    valid_until: str
    polarity: str  # "support" | "refute" — lets flag logic detect conflict without a model


@dataclass(frozen=True)
class EquivalenceEdge:
    """A *proposed* cross-domain equivalence assertion (not yet real)."""

    id: str
    left_entity_id: str
    right_entity_id: str
    confidence: float


@dataclass(frozen=True)
class Extraction:
    """The extraction stage's output — the JSON seam into graph construction."""

    entities: list[Entity]
    signals: list[Signal]


@dataclass(frozen=True)
class Alignment:
    """The alignment stage's output — proposed cross-domain equivalence edges."""

    edges: list[EquivalenceEdge]


@dataclass(frozen=True)
class SeedClass:
    """One class in a seeded sub-ontology."""

    name: str  # e.g. "Apparel"
    kind: str  # "entity" | "signal" | "source"


@dataclass(frozen=True)
class SeedOntology:
    """A seeded sub-ontology for an unfamiliar category."""

    category: str
    classes: list[SeedClass]


@dataclass(frozen=True)
class SourceRef:
    uri: str
    source_type: str
    credibility: float


@dataclass(frozen=True)
class TemporalValidity:
    valid_from: str
    valid_until: str


@dataclass(frozen=True)
class Claim:
    """A confident trend assertion in the brief, with provenance and reasoning."""

    statement: str
    confidence: float
    temporal_validity: TemporalValidity
    sources: list[SourceRef]
    reasoning: str


@dataclass(frozen=True)
class Flag:
    signal_id: str
    statement: str
    reason: str  # "low-confidence" | "conflict"
    confidence: float
    source_uri: str


@dataclass(frozen=True)
class GatedEdge:
    id: str
    left_entity: str
    right_entity: str
    confidence: float
    status: str = "proposed"


@dataclass
class Brief:
    """The forecast brief — the output artifact (Markdown + JSON)."""

    category: str
    as_of: str
    claims: list[Claim]
    flags: list[Flag]
    gated_edges: list[GatedEdge]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        lines = [f"# Forecast brief — {self.category}", "", f"_as of {self.as_of}_", ""]

        lines.append("## Trends")
        if not self.claims:
            lines.append("\n_No confident trends._\n")
        for i, claim in enumerate(self.claims, 1):
            tv = claim.temporal_validity
            lines.append(f"\n### {i}. {claim.statement}")
            lines.append(f"- Confidence: {claim.confidence}")
            lines.append(f"- Reasoning: {claim.reasoning}")
            lines.append(f"- Temporal validity: {tv.valid_from} → {tv.valid_until}")
            lines.append("- Sources:")
            for src in claim.sources:
                lines.append(
                    f"  - [{src.uri}]({src.uri}) ({_short(src.source_type)}, credibility {src.credibility})"
                )

        lines.append("\n## Flagged signals")
        if not self.flags:
            lines.append("\n_None._\n")
        for i, flag in enumerate(self.flags, 1):
            lines.append(f"\n### {i}. {flag.statement}")
            lines.append(f"- Reason: {flag.reason}")
            lines.append(f"- Confidence: {flag.confidence}")
            lines.append(f"- Source: [{flag.source_uri}]({flag.source_uri})")

        lines.append("\n## Gated cross-domain edges (awaiting sign-off)")
        if not self.gated_edges:
            lines.append("\n_None._\n")
        for i, edge in enumerate(self.gated_edges, 1):
            lines.append(f"\n### {i}. {edge.left_entity} ≈ {edge.right_entity}")
            lines.append(f"- Confidence: {edge.confidence}")
            lines.append(f"- Status: {edge.status}")

        lines.append("")
        return "\n".join(lines)


@dataclass
class ForecastRun:
    """Everything one run produces: the graph, brief, and the stage outputs."""

    graph: Any  # rdflib.Graph
    brief: Brief
    flags: list[Flag]
    gated_edges: list[GatedEdge]
    extraction: Extraction
    edges: list[EquivalenceEdge]
    usage: list = field(default_factory=list)


@dataclass(frozen=True)
class Usage:
    """Token usage for one model call — feeds the cost metric."""

    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int


# --- JSON-native (de)serialization for the LangGraph state seam ---
# The checkpointed state is JSON-native dicts, not dataclasses, so custom types stay
# out of LangGraph's msgpack serializer (and its "unregistered type" path). These
# convert at the node boundary; the dataclasses remain the typed Python API.


def source_doc_to_dict(source: SourceDoc) -> dict:
    return asdict(source)


def source_doc_from_dict(data: dict) -> SourceDoc:
    data = dict(data)
    data["topics"] = tuple(data.get("topics", ()))  # msgpack turns tuples into lists
    return SourceDoc(**data)


def entity_from_dict(data: dict) -> Entity:
    return Entity(**data)


def signal_from_dict(data: dict) -> Signal:
    return Signal(**data)


def extraction_to_dict(extraction: Extraction) -> dict:
    return asdict(extraction)


def extraction_from_dict(data: dict) -> Extraction:
    return Extraction(
        entities=[entity_from_dict(e) for e in data["entities"]],
        signals=[signal_from_dict(s) for s in data["signals"]],
    )


def edge_to_dict(edge: EquivalenceEdge) -> dict:
    return asdict(edge)


def edge_from_dict(data: dict) -> EquivalenceEdge:
    return EquivalenceEdge(**data)


def _short(iri: str) -> str:
    """Abbreviate a full ontology IRI to a readable CURIE for display."""
    for prefix, ns in (("tech:", TECH_NS), ("gaming:", GAMING_NS), ("csg:", CSG_NS)):
        if iri.startswith(ns):
            return prefix + iri[len(ns):]
    return iri
