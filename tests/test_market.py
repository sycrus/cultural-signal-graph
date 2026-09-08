"""Issue #18 acceptance tests for SEA multi-market support."""

from cultural_signal_graph import seed as sd
from cultural_signal_graph.discovery import _web_backfill
from cultural_signal_graph.fixtures import RECORDED_SEED_OUTPUT
from cultural_signal_graph.models import Ask, TimeWindow, Usage

WINDOW = TimeWindow(start="2026-01-01", end="2026-06-30")


def test_market_is_a_runtime_input():
    ask = Ask(category="fashion", question="sustainable fashion", window=WINDOW, market="SEA")
    assert ask.market == "SEA"
    assert Ask(category="fashion", question="sustainable fashion", window=WINDOW).market is None


def test_backfill_query_includes_market(monkeypatch):
    captured = {}

    def fake_fetch(query, limit):
        captured["query"] = query
        return []

    monkeypatch.setattr("cultural_signal_graph.discovery._fetch_search_results", fake_fetch)
    _web_backfill(Ask(category="fashion", question="sustainable fashion", window=WINDOW, market="SEA"))
    assert "SEA" in captured["query"]


def test_seed_prompt_includes_market(monkeypatch):
    captured = {}

    def fake_call(category, market=None):
        captured["market"] = market
        return RECORDED_SEED_OUTPUT, Usage(model=sd.SEEDING_MODEL, input_tokens=1, output_tokens=1, total_tokens=2)

    monkeypatch.setattr(sd, "_call_seed_model", fake_call)
    sd.seed_ontology("fashion", market="SEA")
    assert captured["market"] == "SEA"
