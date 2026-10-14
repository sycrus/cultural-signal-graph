"""Issue #4/#28 acceptance tests for source discovery (index + model-guided web)."""

from cultural_signal_graph.discovery import (
    MAX_QUERIES,
    MAX_SOURCES,
    MAX_WEB_BACKFILL,
    MAX_WEB_SOURCES,
    SOURCE_INDEX,
    _fallback_queries,
    _fetch_brave_results,
    _fetch_search_results,
    _parse_queries,
    _search_records,
    _web_backfill,
    discover_sources,
    discover_with_trace,
    search_queries,
)
from cultural_signal_graph.models import Ask, TimeWindow, Usage

WINDOW = TimeWindow(start="2026-01-01", end="2026-06-30")


def _ask(category: str, question: str, market: str | None = None) -> Ask:
    return Ask(category=category, question=question, window=WINDOW, market=market)


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


# --- model-guided queries (#28) ------------------------------------------------


def test_parse_queries_validates_and_caps():
    assert _parse_queries('["quiet luxury", "stealth wealth brands", "  ", 42, "quiet luxury"]') == [
        "quiet luxury",
        "stealth wealth brands",
    ]
    assert _parse_queries('["a", "b", "c", "d"]') == ["a", "b", "c"]  # capped at MAX_QUERIES
    assert len(_parse_queries('["a", "b", "c", "d"]')) <= MAX_QUERIES


def test_search_queries_uses_the_model_seam(monkeypatch):
    calls = []

    def fake_model(ask):
        calls.append(ask)
        return '["quiet luxury fashion 2026", "stealth wealth brands"]', Usage("m", 10, 5, 15)

    monkeypatch.setattr("cultural_signal_graph.discovery._call_query_model", fake_model)
    assert search_queries(_ask("fashion", "quiet luxury adoption")) == [
        "quiet luxury fashion 2026",
        "stealth wealth brands",
    ]
    assert calls == [_ask("fashion", "quiet luxury adoption")]


def test_search_queries_falls_back_to_the_ask(monkeypatch):
    def broken(ask):
        raise RuntimeError("no key")

    monkeypatch.setattr("cultural_signal_graph.discovery._call_query_model", broken)
    assert search_queries(_ask("fashion", "quiet luxury adoption")) == _fallback_queries(
        _ask("fashion", "quiet luxury adoption")
    )
    assert search_queries(_ask("fashion", "quiet luxury", market="SEA")) == [
        "quiet luxury SEA"
    ]


# --- discovery with a trace ------------------------------------------------------


def _stub_fetch(monkeypatch, results):
    monkeypatch.setattr(
        "cultural_signal_graph.discovery._fetch_search_results", lambda query, limit: results
    )


def test_discover_with_trace_unions_index_and_web(monkeypatch):
    _stub_fetch(
        monkeypatch,
        [
            {"title": "Web hit", "url": "https://en.wikipedia.org/wiki/Web_hit", "snippet": "fresh"},
            # a URL the index already covers: selected as index, never duplicated
            {"title": "Index dup", "url": "https://example.com/release-notes/ai-wearables", "snippet": "dup"},
        ],
    )
    found = discover_with_trace(_ask("tech", "AI wearables adoption"), queries=["ai wearables news"])

    origins = {s["uri"]: s["origin"] for s in found["selected"]}
    assert found["mode"] == "index+web"
    assert origins["https://example.com/release-notes/ai-wearables"] == "index"
    assert origins["https://en.wikipedia.org/wiki/Web_hit"] == "web"
    assert found["query_source"] == "given"
    assert found["results"][0]["query"] == "ai wearables news"  # attribution kept
    assert len({r["url"] for r in found["results"]}) == len(found["results"])  # deduped


def test_discover_with_trace_web_only_for_unindexed_categories(monkeypatch):
    results = [{"title": f"T{i}", "url": f"https://en.wikipedia.org/wiki/T{i}", "snippet": "x"} for i in range(10)]
    monkeypatch.setattr(
        "cultural_signal_graph.discovery._fetch_search_results", lambda query, limit: results[:limit]
    )
    found = discover_with_trace(_ask("fashion", "quiet luxury"), queries=["quiet luxury"])
    assert found["mode"] == "web"
    assert len(found["sources"]) <= MAX_WEB_SOURCES
    assert len(found["results"]) <= MAX_WEB_BACKFILL
    assert all(s["origin"] == "web" for s in found["selected"])


def test_discover_with_trace_survives_a_failing_query(monkeypatch):
    def flaky(query, limit):
        if query == "broken":
            raise OSError("network down")
        return [{"title": "OK", "url": "https://en.wikipedia.org/wiki/OK", "snippet": "x"}]

    monkeypatch.setattr("cultural_signal_graph.discovery._fetch_search_results", flaky)
    found = discover_with_trace(_ask("fashion", "x"), queries=["broken", "works"])
    assert found["mode"] == "web"
    assert [r["query"] for r in found["results"]] == ["works"]


def test_web_backfill_accepts_queries_arg(monkeypatch):
    seen = []

    def fetch(query, limit):
        seen.append(query)
        return [{"title": "T", "url": "https://en.wikipedia.org/wiki/T", "snippet": "x"}]

    monkeypatch.setattr("cultural_signal_graph.discovery._fetch_search_results", fetch)
    sources = _web_backfill(_ask("fashion", "q"), queries=["one", "two"])
    assert seen == ["one", "two"]
    assert sources


# --- search backends: Brave when keyed, Wikipedia fallback (#48) -----------------


def test_fetch_dispatches_on_brave_key(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "cultural_signal_graph.discovery._fetch_brave_results",
        lambda query, limit: calls.append("brave") or [],
    )
    monkeypatch.setattr(
        "cultural_signal_graph.discovery._fetch_wikipedia_results",
        lambda query, limit: calls.append("wiki") or [],
    )
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    _fetch_search_results("q", 5)
    monkeypatch.setenv("BRAVE_API_KEY", "test-key")
    _fetch_search_results("q", 5)
    assert calls == ["wiki", "brave"]


def test_brave_fetch_merges_web_and_news(monkeypatch):
    payload = {
        "web": {"results": [
            {"title": "FTC bans fake AI reviews", "url": "https://ftc.example/1",
             "description": "<strong>FTC</strong> bans fake AI-generated reviews"},
            {"title": "Dup", "url": "https://ftc.example/1", "description": "same story"},
        ]},
        "news": {"results": [
            {"title": "Dup", "url": "https://ftc.example/1", "description": "same story, news bucket"},
            {"title": "Regulator probes ad claims", "url": "https://gov.example/2", "description": "probe opened"},
        ]},
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            import json
            return json.dumps(payload).encode()

    monkeypatch.setenv("BRAVE_API_KEY", "test-key")
    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout=10: FakeResponse())
    records = _fetch_brave_results("ai advertising fake reviews regulation", 5)
    assert [r["url"] for r in records] == ["https://ftc.example/1", "https://gov.example/2"]
    assert all(r["backend"] == "brave" for r in records)
    assert "<strong>" not in records[0]["snippet"]


def test_search_records_records_per_query_errors(monkeypatch):
    def flaky(query, limit):
        if "bad" in query:
            raise RuntimeError("boom")
        return [{"title": "T", "url": "https://example.com/t", "snippet": "s", "backend": "brave"}]

    monkeypatch.setattr("cultural_signal_graph.discovery._fetch_search_results", flaky)
    errors: list[dict] = []
    records = _search_records(["good", "bad one"], errors=errors)
    assert [r["query"] for r in records] == ["good"]
    assert errors == [{"query": "bad one", "error": "boom"}]
