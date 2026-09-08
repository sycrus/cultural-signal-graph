"""HITL flag + gate logic (issue #2).

Single-domain signals are *flagged*, never silently averaged away: a signal is
flagged if it conflicts with another signal about the same entity (opposite
polarity, with the minority stance losing) or if its confidence is too low.
Cross-domain equivalence edges are *gated*: every proposed edge stays
"proposed" and none is promoted to "real" without sign-off.
"""

from collections import Counter

from .models import EquivalenceEdge, Extraction, Flag, GatedEdge, Signal

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


def apply_gate(extraction: Extraction) -> list[GatedEdge]:
    """Hold every proposed cross-domain edge as "proposed" (no promotion)."""
    entity_by_id = {e.id: e for e in extraction.entities}
    gated: list[GatedEdge] = []
    for edge in extraction.proposed_edges:
        gated.append(
            GatedEdge(
                id=edge.id,
                left_entity=entity_by_id[edge.left_entity_id].name,
                right_entity=entity_by_id[edge.right_entity_id].name,
                confidence=edge.confidence,
                status="proposed",
            )
        )
    return gated
