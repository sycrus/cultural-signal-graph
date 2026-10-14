"""Forks (#35): a strategist-initiated sibling branch from any projection."""

import json

import pytest
from fastapi.testclient import TestClient

from cultural_signal_graph.config import futures_model
from cultural_signal_graph.futures import generator as gen
from cultural_signal_graph.futures.fixtures import FIXTURE_GOAL
from cultural_signal_graph.futures.store import ExplorationStore
from cultural_signal_graph.models import Usage
from cultural_signal_graph.runstore import RunStore, fixture_stage_fns
from cultural_signal_graph.server import create_app

SEED_ANCHORS = ["sig-release-note", "sig-search-spike", "sig-viral-fad", "sig-gaming-chatter"]


@pytest.fixture()
def runs(tmp_path):
    return RunStore(tmp_path, stage_fns=fixture_stage_fns())


@pytest.fixture()
def run_id(runs):
    rid = runs.create("tech", "AI wearables adoption", "2026-01-01", "2026-06-30")["id"]
    runs.start(rid)
    return rid


def _explore(store, run_id):
    x = store.create(run_id, FIXTURE_GOAL, SEED_ANCHORS, start_year=2026)["exploration"]["id"]
    store.generate(run_id, x)
    return x


def test_fork_adds_a_sibling_branch_and_keeps_the_original(runs, run_id):
    store = ExplorationStore(runs.root)
    x = _explore(store, run_id)
    before = {p["id"]: p for p in store.snapshot(run_id, x)["projections"]}
    snap = store.fork(run_id, x, "o2-audio-only", hint="the EU bans always-on cameras")
    after = {p["id"]: p for p in snap["projections"]}
    assert set(before) < set(after)  # nothing removed or replaced
    assert all(after[k] == before[k] for k in before)
    forked = sorted((p for p in after.values() if p["origin"] == "forked"), key=lambda p: p["order"])
    assert [p["order"] for p in forked] == [3, 4, 5]  # down to the depth limit
    assert "o2-audio-only" in forked[0]["parents"]
    assert not any(p["baseline"] for p in forked)
    assert all(p["hint"] == "the EU bans always-on cameras" for p in forked)
    assert all(p["parents"] for p in forked)  # the structural check
    # one op: undo removes the whole fork
    store.undo(run_id, x)
    assert {p["id"] for p in store.snapshot(run_id, x)["projections"]} == set(before)


def test_fork_at_the_depth_limit_is_refused(runs, run_id):
    store = ExplorationStore(runs.root)
    x = _explore(store, run_id)
    with pytest.raises(ValueError):
        store.fork(run_id, x, "o5-two-tier-society")


def test_live_fork_records_the_hint_and_may_converge(monkeypatch, runs, run_id):
    prompts = []
    outputs = [
        json.dumps({"projections": [{
            "id": "o3-ban", "statement": "Camera bans push audio-only wearables mainstream",
            "from": ["o2-audio-only", "o2-headset-merge"], "window": [2030, 2031],
            "baseline": True, "discontinuity": True,
        }]}),
        json.dumps({"projections": []}),
    ]

    def fake(prompt, call_type="generate"):
        prompts.append((prompt, call_type))
        model, temperature = futures_model(call_type)
        return outputs.pop(0), Usage(model, 10, 10, 20), model, temperature

    monkeypatch.setattr(gen, "_call_generation_model", fake)
    store = ExplorationStore(runs.root, mode="live", generator=gen.fixture_generator)
    x = _explore(store, run_id)
    snap = store.fork(run_id, x, "o2-audio-only", hint="the EU bans always-on cameras")
    prompt, call_type = prompts[0]
    assert call_type == "fork"
    assert "what if the EU bans always-on cameras" in prompt
    assert "o2-audio-only" in prompt
    ban = next(p for p in snap["projections"] if p["id"] == "o3-ban")
    assert ban["parents"] == ["o2-audio-only", "o2-headset-merge"]  # converges with the original branch
    assert ban["baseline"] is False  # a fork never takes the baseline
    op = store.ops(run_id, x)[-1]
    assert op["op"] == "fork" and op["hint"] == "the EU bans always-on cameras"
    assert op["orders"][0]["input"]["prompt"] == prompt


def test_fork_route(runs, run_id):
    client = TestClient(create_app(runs))
    store = ExplorationStore(runs.root)
    x = _explore(store, run_id)
    res = client.post(f"/api/runs/{run_id}/explorations/{x}/projections/o1-backlash/fork", json={"hint": "", "author": "jo"})
    assert res.status_code == 200
    assert store.ops(run_id, x)[-1]["author"] == "jo"
    assert client.post(f"/api/runs/{run_id}/explorations/{x}/projections/nope/fork", json={}).status_code == 404
