"""The strategist's own additions (#36): wild cards, grounded assumptions, and
futures-scoped references — which never touch the forecast's evidence."""

import pytest
from fastapi.testclient import TestClient

from cultural_signal_graph.futures import generator as gen
from cultural_signal_graph.futures.fixtures import FIXTURE_GOAL
from cultural_signal_graph.futures.store import ExplorationStore
from cultural_signal_graph.models import Usage
from cultural_signal_graph.runstore import RunStore, fixture_stage_fns
from cultural_signal_graph.server import create_app

SEED_ANCHORS = ["sig-release-note", "sig-search-spike", "sig-viral-fad", "sig-gaming-chatter"]
REF = {
    "url": "https://example.gov/ai-wearables-plan",
    "excerpt": "The ministry plans to subsidize AI wearables for elderly care from 2028. Pilots start in three cities.",
}


@pytest.fixture()
def runs(tmp_path):
    return RunStore(tmp_path, stage_fns=fixture_stage_fns())


@pytest.fixture()
def run_id(runs):
    rid = runs.create("tech", "AI wearables adoption", "2026-01-01", "2026-06-30")["id"]
    runs.start(rid)
    runs.signoff(rid, {"edge-ai-headset-wearables": True})
    return rid


@pytest.fixture()
def store(runs):
    return ExplorationStore(runs.root)


@pytest.fixture()
def exp_id(store, run_id):
    x = store.create(run_id, FIXTURE_GOAL, SEED_ANCHORS, start_year=2026)["exploration"]["id"]
    store.generate(run_id, x)
    return x


def by_id(snap):
    return {p["id"]: p for p in snap["projections"]}


def test_wild_card_is_unanchored_and_tagged(store, run_id, exp_id):
    snap = store.add_projection(run_id, exp_id, "wildcard", "A solar storm wipes out satellite positioning", [2031, 2031])
    w = by_id(snap)["wildcard-1"]
    assert w["origin"] == "wildcard" and w["order"] == 1
    assert w["parents"] == [] and w["anchors"] == []
    assert w["human_root"] == "wildcard"


def test_wild_card_after_a_projection_takes_the_next_order(store, run_id, exp_id):
    snap = store.add_projection(run_id, exp_id, "wildcard", "x", [2030, 2031], parent_id="o2-audio-only")
    assert by_id(snap)["wildcard-1"]["order"] == 3
    assert by_id(snap)["wildcard-1"]["parents"] == ["o2-audio-only"]


def test_grounded_assumption_needs_a_reference(store, run_id, exp_id):
    with pytest.raises(ValueError):
        store.add_projection(run_id, exp_id, "assumption", "Subsidies arrive", [2028, 2030])


def test_grounded_assumption_brings_its_reference_into_the_present(store, run_id, exp_id):
    snap = store.add_projection(run_id, exp_id, "assumption", "Elder-care subsidies seed a second market", [2028, 2030], reference=REF)
    refs = [a for a in snap["anchors"] if a["kind"] == "reference"]
    assert len(refs) == 1
    ref = refs[0]
    assert ref["scope"] == "futures" and ref["source_uri"] == REF["url"]
    assert ref["text"] == "The ministry plans to subsidize AI wearables for elderly care from 2028"  # one line
    a = by_id(snap)["assumption-1"]
    assert a["anchors"] == [ref["id"]] and a["origin"] == "assumption"
    # a second assumption can reuse the reference
    snap = store.add_projection(run_id, exp_id, "assumption", "Insurers follow", [2030, 2032], reference_id=ref["id"])
    assert by_id(snap)["assumption-2"]["anchors"] == [ref["id"]]
    # one op: undo removes the assumption and the reference it brought
    store.undo(run_id, exp_id)
    snap = store.undo(run_id, exp_id)
    assert not [a for a in snap["anchors"] if a["kind"] == "reference"]


def test_references_never_touch_the_forecast(store, runs, run_id, exp_id):
    brief = (runs.root / run_id / "brief.json").read_bytes()
    anchors = store.anchors(run_id)
    store.add_reference(run_id, exp_id, REF["url"], REF["excerpt"])
    store.add_projection(run_id, exp_id, "assumption", "x", [2028, 2029], reference=REF)
    assert (runs.root / run_id / "brief.json").read_bytes() == brief
    assert store.anchors(run_id) == anchors


def test_forks_from_human_roots_trace_back_to_them(store, run_id, exp_id):
    store.add_projection(run_id, exp_id, "wildcard", "A solar storm wipes out satellite positioning", [2031, 2031])
    snap = store.fork(run_id, exp_id, "wildcard-1")
    descendants = [p for p in snap["projections"] if p["origin"] == "forked"]
    assert descendants and all(p["human_root"] == "wildcard" for p in descendants)
    store.add_projection(run_id, exp_id, "assumption", "Subsidies arrive", [2028, 2029], reference=REF)
    snap = store.fork(run_id, exp_id, "assumption-1")
    assert any(p["human_root"] == "assumption" for p in snap["projections"] if p["origin"] == "forked")
    # generated projections keep no human root
    assert by_id(snap)["o1-backlash"]["human_root"] is None


def test_live_summary_is_a_traced_model_call(monkeypatch, runs, run_id, exp_id):
    def fake_call(model, system, prompt, max_tokens, temperature=None):
        assert REF["excerpt"] in prompt
        return "The ministry will subsidize AI wearables for elder care.", Usage(model, 5, 5, 10)

    monkeypatch.setattr(gen, "call_model", fake_call)
    store = ExplorationStore(runs.root, mode="live")
    snap = store.add_reference(run_id, exp_id, REF["url"], REF["excerpt"])
    ref = next(a for a in snap["anchors"] if a["kind"] == "reference")
    assert ref["text"] == "The ministry will subsidize AI wearables for elder care."
    op = store.ops(run_id, exp_id)[-1]
    assert op["summary"]["model"] == "deepseek-v4-flash" and op["summary"]["temperature"] == 0.0
    assert op["summary"]["output"] == ref["text"]


def test_http_seam(runs, run_id, exp_id):
    client = TestClient(create_app(runs))
    base = f"/api/runs/{run_id}/explorations/{exp_id}"
    assert client.post(f"{base}/references", json={"url": "not a url", "excerpt": "x"}).status_code == 409
    assert client.post(f"{base}/references", json=REF).status_code == 200
    res = client.post(f"{base}/projections", json={
        "kind": "assumption", "statement": "Subsidies arrive", "window": [2028, 2029], "reference": REF,
    })
    assert res.status_code == 200
    assert client.post(f"{base}/projections", json={"kind": "wildcard", "statement": "x", "window": [2029, 2028]}).status_code == 409
    assert client.post(f"{base}/projections", json={"kind": "other", "statement": "x", "window": [2028, 2029]}).status_code == 409
