"""Brief assembly: confident signals -> claims, flagged -> flags, gated -> gated.

Produces the auditable forecast brief (Markdown + JSON). A claim is a confident
signal about an entity in the asked category; it carries its source(s),
confidence, and temporal validity. Out-of-category signals (the gaming chatter
in the cross-domain demo) stay in the graph but are not claims of a tech brief.
"""

from .models import (
    Brief,
    Claim,
    Extraction,
    Flag,
    GatedEdge,
    SourceDoc,
    SourceRef,
    TemporalValidity,
)


def assemble(
    extraction: Extraction,
    sources: list[SourceDoc],
    flags: list[Flag],
    gated_edges: list[GatedEdge],
    category: str,
    as_of: str,
) -> Brief:
    source_by_uri = {s.uri: s for s in sources}
    entity_by_id = {e.id: e for e in extraction.entities}
    flagged_ids = {flag.signal_id for flag in flags}

    claims: list[Claim] = []
    for signal in extraction.signals:
        if signal.id in flagged_ids:
            continue
        if entity_by_id[signal.about_entity_id].category != category:
            continue
        source = source_by_uri[signal.source_uri]
        claims.append(
            Claim(
                statement=signal.text,
                confidence=signal.confidence,
                temporal_validity=TemporalValidity(
                    valid_from=signal.valid_from, valid_until=signal.valid_until
                ),
                sources=[SourceRef(source.uri, source.source_type, source.credibility)],
            )
        )

    return Brief(
        category=category,
        as_of=as_of,
        claims=claims,
        flags=flags,
        gated_edges=gated_edges,
    )
