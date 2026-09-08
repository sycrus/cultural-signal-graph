"""Shared dataclasses for the forecast pipeline's JSON seams.

These are the vocabulary the pipeline stages pass between each other
(corpus -> extraction -> graph -> flags -> brief). Keep them dependency-free:
stdlib dataclasses only, so the slice stays light and deterministic.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
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
    proposed_edges: list[EquivalenceEdge]


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
    """A confident trend assertion in the brief, with its provenance."""

    statement: str
    confidence: float
    temporal_validity: TemporalValidity
    sources: list[SourceRef]


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
    """Everything one run produces: the graph plus the assembled brief."""

    graph: Any  # rdflib.Graph
    brief: Brief
    flags: list[Flag]
    gated_edges: list[GatedEdge]


def _short(iri: str) -> str:
    """Abbreviate a full ontology IRI to a readable CURIE for display."""
    for prefix, ns in (("tech:", TECH_NS), ("gaming:", GAMING_NS), ("csg:", CSG_NS)):
        if iri.startswith(ns):
            return prefix + iri[len(ns):]
    return iri
