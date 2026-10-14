"""PESTLE (#42): multi-label tags (one primary + secondaries) on anchors and
projections; anchor coverage and goal-based suggestions in the picker; gaps seeded."""

import json

import pytest
from fastapi.testclient import TestClient

from cultural_signal_graph.futures import generator as gen
from cultural_signal_graph.futures import lenses
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


@pytest.fixture()
def store(runs):
    return ExplorationStore(runs.root)


def _explore(store, run_id):
    x = store.create(run_id, FIXTURE_GOAL, ANCHORS, start_year=2026)["exploration"]["id"]
    store.generate(run_id, x)
    return x


def test_primary_plus_secondaries(store, run_id):
    x = _explore(store, run_id)
    snap = store.classify(run_id, x, "pestle")
    tags = {p["id"]: p["tags"]["pestle"] for p in snap["projections"]}
    assert all(t["value"] in lenses.PESTLE_VALUES for t in tags.values())
    leak = tags["o2-footage-leak"]
    assert leak["value"] == "economic" or leak["secondary"]  # touches more than one dimension
    assert all(t["value"] not in t["secondary"] for t in tags.values())
    assert all(a["tags"].get("pestle") for a in snap["anchors"])  # anchors too


def test_override_changes_primary_and_keeps_secondaries_clean(store, run_id):
    x = _explore(store, run_id)
    store.classify(run_id, x, "pestle")
    snap = store.set_tag(run_id, x, "o1-privacy-rules", "pestle",
                         {"value": "political", "secondary": ["legal", "political", "astrology"]}, author="jo")
    tag = next(p for p in snap["projections"] if p["id"] == "o1-privacy-rules")["tags"]["pestle"]
    assert tag["value"] == "political" and tag["secondary"] == ["legal"] and tag["source"] == "human"


def test_anchor_coverage_is_cached_and_carried_into_explorations(runs, run_id):
    calls = []
    store = ExplorationStore(runs.root)
    real = lenses.classify

    def counting(*a, **kw):
        calls.append(1)
        return real(*a, **kw)

    lenses.classify, saved = counting, lenses.classify
    try:
        cov = store.anchor_pestle(run_id)
        again = store.anchor_pestle(run_id)
    finally:
        lenses.classify = saved
    assert set(cov) >= set(ANCHORS) and cov == again
    assert len(calls) == 1  # cached in the run directory
    x = store.create(run_id, FIXTURE_GOAL, ANCHORS)["exploration"]["id"]
    snap = store.snapshot(run_id, x)
    assert all(a["tags"]["pestle"]["value"] == cov[a["id"]]["value"] for a in snap["anchors"])
    assert snap["lenses"]["pestle"]["untagged"] == 0  # nothing to ask until projections exist


def test_suggest_anchors_live(monkeypatch, runs, run_id):
    def fake(model, system, prompt, max_tokens, temperature=None):
        assert "Exploration goal: the direction of AR/VR wearables" in prompt
        return json.dumps({"picks": [{"id": "sig-release-note", "reason": "on-device AI"}, {"id": "bogus", "reason": "x"}]}), Usage(model, 1, 1, 2)

    monkeypatch.setattr(gen, "call_model", fake)
    store = ExplorationStore(runs.root, mode="live")
    out = store.suggest_anchors(run_id, "the direction of AR/VR wearables")
    assert out["anchor_ids"] == ["sig-release-note"] and out["reasons"]["sig-release-note"] == "on-device AI"


def test_gap_seeding_follows_one_dimension(store, run_id):
    x = _explore(store, run_id)
    before = {p["id"] for p in store.snapshot(run_id, x)["projections"]}
    snap = store.seed_dimension(run_id, x, "environmental")
    new = [p for p in snap["projections"] if p["id"] not in before]
    assert new and all(p["tags"]["pestle"]["value"] == "environmental" for p in new)
    assert store.ops(run_id, x)[-1]["constraint"] == {"pestle": "environmental"}
    with pytest.raises(KeyError):
        store.seed_dimension(run_id, x, "spiritual")


def test_http_seam(runs, run_id):
    client = TestClient(create_app(runs))
    assert client.post(f"/api/runs/{run_id}/futures/anchors/pestle").status_code == 200
    res = client.post(f"/api/runs/{run_id}/futures/suggest", json={"goal": "glasses everywhere"})
    assert res.status_code == 200 and res.json()["anchor_ids"]
    assert client.post(f"/api/runs/{run_id}/futures/suggest", json={"goal": " "}).status_code == 409
