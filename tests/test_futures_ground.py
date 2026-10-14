"""Ground this (#45): a bounded agent loop — queries, search, judge (support /
contradict), one optional refinement round — whose proposals are accepted one by one
as futures-scoped references. Search and model seams are scripted; no network."""

import json

import pytest
from fastapi.testclient import TestClient

from cultural_signal_graph import discovery
from cultural_signal_graph.futures import generator as gen
from cultural_signal_graph.futures import ground
from cultural_signal_graph.futures.fixtures import FIXTURE_GOAL
from cultural_signal_graph.futures.store import ExplorationStore
from cultural_signal_graph.models import Usage
from cultural_signal_graph.runstore import RunStore, fixture_stage_fns
from cultural_signal_graph.server import create_app

ANCHORS = ["sig-release-note", "sig-search-spike", "sig-viral-fad", "sig-gaming-chatter"]


@pytest.fixture()
def runs(tmp_path):
    return RunStore(tmp_path, stage_fns=fixture_stage_fns())


@pytest.fixture()
def run_id(runs):
    rid = runs.create("tech", "AI wearables adoption", "2026-01-01", "2026-06-30")["id"]
    runs.start(rid)
    return rid


def _explore(store, run_id):
    x = store.create(run_id, FIXTURE_GOAL, ANCHORS, start_year=2026)["exploration"]["id"]
    store.generate(run_id, x)
    return x


def script(monkeypatch, model_outputs, search_results):
    calls, searches = [], []

    def fake_model(model, system, prompt, max_tokens, temperature=None):
        calls.append(prompt)
        return json.dumps(model_outputs.pop(0)), Usage(model, 5, 5, 10)

    def fake_search(query, limit):
        searches.append(query)
        return search_results.pop(0) if search_results else []

    monkeypatch.setattr(ground, "call_model", fake_model)
    monkeypatch.setattr(discovery, "_fetch_search_results", fake_search)
    return calls, searches


R1 = [{"title": "EU AI Act", "url": "https://en.wikipedia.org/wiki/AI_Act", "snippet": "rules on biometric capture in public"}]
R2 = [{"title": "Smartglasses", "url": "https://en.wikipedia.org/wiki/Smartglasses", "snippet": "sales grew sharply"}]


def test_finds_support_and_contradiction_with_a_full_trail(monkeypatch, runs, run_id):
    store = ExplorationStore(runs.root, mode="live", generator=gen.fixture_generator)
    x = _explore(store, run_id)
    calls, searches = script(monkeypatch, [
        {"queries": ["AI Act biometric", "smart glasses sales"]},
        {"judgments": [
            {"index": 0, "stance": "support", "excerpt": "rules on biometric capture in public spaces from next year", "why": "regulation"},
            {"index": 1, "stance": "contradict", "excerpt": "sales grew sharply through the holiday quarter in every region", "why": "no stall"},
            {"index": 9, "stance": "support", "excerpt": "out of range"},
        ]},
    ], [R1, R2])
    snap = store.ground(run_id, x, "o1-privacy-rules")
    g = snap["grounding"]["o1-privacy-rules"]
    assert [p["stance"] for p in g["proposals"]] == ["support", "contradict"]
    assert g["queries"] == ["AI Act biometric", "smart glasses sales"] and g["examined"] == 2
    assert searches == ["AI Act biometric", "smart glasses sales"]
    assert "for it AND against it" in calls[0]
    op = store.ops(run_id, x)[-1]
    assert op["op"] == "ground" and [s["step"] for s in op["steps"]] == ["queries", "judge"]
    assert op["results"][0]["query"] == "AI Act biometric"  # each result attributed to its query
    # nothing was added on its own
    assert not [a for a in snap["anchors"] if a["kind"] == "reference"]


def test_refines_once_when_nothing_is_usable_then_stops(monkeypatch, runs, run_id):
    store = ExplorationStore(runs.root, mode="live", generator=gen.fixture_generator)
    x = _explore(store, run_id)
    calls, searches = script(monkeypatch, [
        {"queries": ["vague"]},
        {"judgments": [], "more_queries": ["sharper"]},
        {"judgments": [], "more_queries": ["even sharper"]},  # last round: ignored
    ], [R1, R2, R1])
    snap = store.ground(run_id, x, "o1-backlash")
    assert searches == ["vague", "sharper"]  # bounded: at most two search rounds
    assert len(calls) == 3
    assert snap["grounding"]["o1-backlash"]["proposals"] == []


def test_fragment_excerpts_are_rejected(monkeypatch, runs, run_id):
    store = ExplorationStore(runs.root, mode="live", generator=gen.fixture_generator)
    x = _explore(store, run_id)
    script(monkeypatch, [
        {"queries": ["one query"]},
        {"judgments": [
            {"index": 0, "stance": "support", "excerpt": "the government antitrust action, which", "why": "keyword match"},
            {"index": 1, "stance": "support", "excerpt": "regulators now require third-party audits of ad-targeting models", "why": "on point"},
        ]},
    ], [R1 + R2])
    snap = store.ground(run_id, x, "o1-backlash")
    proposals = snap["grounding"]["o1-backlash"]["proposals"]
    assert [p["excerpt"] for p in proposals] == ["regulators now require third-party audits of ad-targeting models"]


def test_search_errors_explain_an_empty_round(monkeypatch, runs, run_id):
    store = ExplorationStore(runs.root, mode="live", generator=gen.fixture_generator)
    x = _explore(store, run_id)

    def broken(query, limit):
        raise RuntimeError("search timed out")

    monkeypatch.setattr(ground, "call_model", lambda *a, **k: ('{"queries": ["q1"]}', Usage("m", 1, 1, 2)))
    monkeypatch.setattr(discovery, "_fetch_search_results", broken)
    snap = store.ground(run_id, x, "o1-backlash")
    g = snap["grounding"]["o1-backlash"]
    assert g["proposals"] == [] and g["examined"] == 0
    assert g["errors"] == [{"query": "q1", "error": "search timed out"}]
    op = next(o for o in store.ops(run_id, x) if o.get("op") == "ground")
    assert op["errors"] == g["errors"]


def test_accepting_a_proposal_adds_a_grounding_reference(runs, run_id):
    store = ExplorationStore(runs.root)  # fixture mode
    x = _explore(store, run_id)
    snap = store.ground(run_id, x, "o2-audio-only")
    p = snap["grounding"]["o2-audio-only"]["proposals"][1]
    snap = store.add_reference(run_id, x, p["url"], p["excerpt"], stance=p["stance"], grounds="o2-audio-only")
    ref = next(a for a in snap["anchors"] if a["kind"] == "reference")
    assert ref["stance"] == "contradict" and ref["grounds"] == "o2-audio-only" and ref["scope"] == "futures"
    with pytest.raises(ValueError):
        store.add_reference(run_id, x, p["url"] + "2", p["excerpt"], stance="maybe", grounds="o2-audio-only")


def test_markdown_export_marks_grounding(runs, run_id):
    store = ExplorationStore(runs.root)  # fixture mode
    x = _explore(store, run_id)
    snap = store.ground(run_id, x, "o2-audio-only")
    p = snap["grounding"]["o2-audio-only"]["proposals"][0]
    snap = store.add_reference(run_id, x, p["url"], p["excerpt"], stance=p["stance"], grounds="o2-audio-only")
    md = store.export(run_id, x, "exploration.md")
    assert "supports: " in md and "Grounding search: " in md and "- query: " in md
    # the exported log re-imports to the same state, grounding included
    copy = store.import_log(run_id, store.export(run_id, x, "log.jsonl"))
    assert copy["grounding"]["o2-audio-only"]["proposals"] == snap["grounding"]["o2-audio-only"]["proposals"]
    assert copy["anchors"] == snap["anchors"]


def test_http_seam(runs, run_id):
    client = TestClient(create_app(runs))
    store = ExplorationStore(runs.root)
    x = _explore(store, run_id)
    base = f"/api/runs/{run_id}/explorations/{x}"
    res = client.post(f"{base}/projections/o1-backlash/ground")
    assert res.status_code == 200 and res.json()["grounding"]["o1-backlash"]["proposals"]
    assert client.post(f"{base}/projections/nope/ground").status_code == 404
