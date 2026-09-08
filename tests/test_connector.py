"""Issue #13 acceptance tests for live connectors."""

from dataclasses import replace

from cultural_signal_graph.connector import merge_new_signals, new_signals, poll, recompute_flags
from cultural_signal_graph.fixtures import ALIGNED_EDGES, EXTRACTED, SEED_CORPUS
from cultural_signal_graph.flags import detect_flags
from cultural_signal_graph.graph import build_graph
from cultural_signal_graph.models import Extraction, Signal


def _extraction_with_extra_signal() -> Extraction:
    extra = Signal(
        id="sig-new",
        text="A brand new signal",
        about_entity_id="ai_wearables",
        source_uri=SEED_CORPUS[0].uri,
        confidence=0.75,
        timestamp="2026-03-01T00:00:00Z",
        valid_from="2026-03-01T00:00:00Z",
        valid_until="2026-09-01T00:00:00Z",
        polarity="support",
    )
    return Extraction(entities=EXTRACTED.entities, signals=EXTRACTED.signals + [extra])


def test_new_signals_detects_only_new():
    known = {s.id for s in EXTRACTED.signals}
    extraction = _extraction_with_extra_signal()
    assert [s.id for s in new_signals(extraction, known)] == ["sig-new"]


def test_poll_returns_new_signals():
    known = {s.id for s in EXTRACTED.signals}
    fresh, _ = poll(SEED_CORPUS, lambda _: _extraction_with_extra_signal(), known)
    assert [s.id for s in fresh] == ["sig-new"]


def test_merge_is_incremental():
    known = {s.id for s in EXTRACTED.signals}
    extraction = _extraction_with_extra_signal()
    graph = build_graph(EXTRACTED, ALIGNED_EDGES, {}, SEED_CORPUS)
    before = len(graph)
    added = merge_new_signals(graph, extraction, known, SEED_CORPUS)
    assert added == 1
    assert len(graph) > before


def test_changed_signal_retriggers_flags():
    original = detect_flags(EXTRACTED.signals)
    assert {f.signal_id for f in original} == {"sig-viral-fad"}

    # the refuting signal now supports -> the conflict disappears
    changed = [replace(s, polarity="support") for s in EXTRACTED.signals]
    assert recompute_flags(changed) == []
