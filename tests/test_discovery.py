"""Issue #4 acceptance tests for source discovery."""

from cultural_signal_graph.discovery import (
    MAX_SOURCES,
    MAX_WEB_BACKFILL,
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


def test_known_category_uses_index_not_backfill():
    # A known category is served from the index; backfill only fires on a miss.
    selected = discover_sources(_ask("tech", "AI wearables"))
    assert selected
    assert all(s in SOURCE_INDEX for s in selected)


def test_web_backfill_returns_typed_sources(monkeypatch):
    monkeypatch.setattr(
        "cultural_signal_graph.discovery._fetch_search_results",
        lambda query, limit: [
            {"title": "Foo", "url": "https://en.wikipedia.org/wiki/Foo", "snippet": "Foo is a thing."},
            {"title": "Bar", "url": "https://en.wikipedia.org/wiki/Bar", "snippet": "Bar is another."},
        ],
    )
    sources = _web_backfill(_ask("fashion", "Foo Bar"))
    assert sources, "expected backfilled sources"
    assert all(s.category == "fashion" for s in sources)
    assert all(s.uri.startswith("https://en.wikipedia.org/wiki/") for s in sources)
    assert all(s.source_type.endswith("Source") for s in sources)


def test_backfill_is_bounded(monkeypatch):
    monkeypatch.setattr(
        "cultural_signal_graph.discovery._fetch_search_results",
        lambda query, limit: [
            {"title": f"T{i}", "url": f"https://example.com/{i}", "snippet": "x"}
            for i in range(100)
        ],
    )
    sources = _web_backfill(_ask("fashion", "query"))
    assert len(sources) <= MAX_WEB_BACKFILL


def test_discover_sources_backfills_when_index_empty(monkeypatch):
    monkeypatch.setattr(
        "cultural_signal_graph.discovery._fetch_search_results",
        lambda query, limit: [
            {"title": "Foo", "url": "https://en.wikipedia.org/wiki/Foo", "snippet": "x"}
        ],
    )
    selected = discover_sources(_ask("fashion", "Foo"))  # fashion not in SOURCE_INDEX
    assert selected
    assert selected[0].category == "fashion"
