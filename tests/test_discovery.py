"""Issue #4 acceptance tests for source discovery."""

from cultural_signal_graph.discovery import (
    MAX_SOURCES,
    SOURCE_INDEX,
    _web_backfill,
    discover_sources,
)
from cultural_signal_graph.models import Ask, TimeWindow

WINDOW = TimeWindow(start="2026-01-01", end="2026-06-30")


def _ask(category: str, question: str) -> Ask:
    return Ask(category=category, question=question, window=WINDOW)


def test_selection_is_proper_subset():
    selected = discover_sources(_ask("tech", "AI wearables adoption"))
    tech = {s for s in SOURCE_INDEX if s.category == "tech"}
    assert selected, "expected at least one source"
    assert len(selected) < len(tech), "expected a proper subset, not all tech sources"
    assert len(selected) <= MAX_SOURCES
    assert all(s.category == "tech" for s in selected)


def test_selection_is_ask_dependent():
    tech = discover_sources(_ask("tech", "AI wearables adoption"))
    gaming = discover_sources(_ask("gaming", "gaming headset demand"))
    tech_uris = {s.uri for s in tech}
    gaming_uris = {s.uri for s in gaming}
    assert tech_uris and gaming_uris
    assert tech_uris != gaming_uris
    assert tech_uris.isdisjoint(gaming_uris)


def test_selection_ranks_relevance_first():
    # An "AI wearables" tech ask prefers AI-wearables sources over cloud/edge ones.
    selected = discover_sources(_ask("tech", "AI wearables adoption"))
    uris = {s.uri for s in selected}
    assert "https://example.com/release-notes/ai-wearables" in uris
    assert "https://example.com/release-notes/cloud-infra" not in uris


def test_no_live_web_search():
    # Live backfill is stubbed: it returns nothing, and discovery only ever
    # returns sources that are already in the index (no network in v1).
    assert _web_backfill(_ask("tech", "AI wearables")) == []
    selected = discover_sources(_ask("tech", "AI wearables"))
    assert all(s in SOURCE_INDEX for s in selected)
