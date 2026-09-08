"""HITL flag + gate logic (issues #2, #5).

Single-domain signals are *flagged*, never silently averaged away: a signal is
flagged if it conflicts with another signal about the same entity (opposite
polarity, minority stance loses) or if its confidence is too low. Cross-domain
equivalence edges are *gated*: an approved edge becomes "real", a rejected one is
dropped, and an undecided one stays "proposed" (the batch path).
"""

from collections import Counter

from .models import Entity, EquivalenceEdge, Flag, GatedEdge, Signal

LOW_CONFIDENCE = 0.5


def detect_flags(signals: list[Signal]) -> list[Flag]:
    """Return a flag per non-confident signal (conflict or low confidence)."""
    by_entity: dict[str, list[Signal]] = {}
    for signal in signals:
        by_entity.setdefault(signal.about_entity_id, []).append(signal)

    flags: list[Flag] = []
    for entity_signals in by_entity.values():
        counts = Counter(s.polarity for s in entity_signals)
        dominant = {p for p, c in counts.items() if c == max(counts.values())}
        # A tie (every stance equally represented) or a minority stance -> conflict.
        for signal in entity_signals:
            if len(dominant) > 1 or signal.polarity not in dominant:
                reason = "conflict"
            elif signal.confidence < LOW_CONFIDENCE:
                reason = "low-confidence"
            else:
                continue
            flags.append(
                Flag(
                    signal_id=signal.id,
                    statement=signal.text,
                    reason=reason,
                    confidence=signal.confidence,
                    source_uri=signal.source_uri,
                )
            )
    return flags


def resolve_edges(
    edges: list[EquivalenceEdge],
    decisions: dict[str, bool],
    entities: list[Entity],
) -> list[GatedEdge]:
    """Resolve proposed edges to their gate status, resolved to display names."""
    entity_by_id = {e.id: e for e in entities}
    resolved: list[GatedEdge] = []
    for edge in edges:
        decision = decisions.get(edge.id)
        if decision is True:
            status = "real"
        elif decision is False:
            status = "rejected"
        else:
            status = "proposed"
        resolved.append(
            GatedEdge(
                id=edge.id,
                left_entity=entity_by_id[edge.left_entity_id].name,
                right_entity=entity_by_id[edge.right_entity_id].name,
                confidence=edge.confidence,
                status=status,
            )
        )
    return resolved
