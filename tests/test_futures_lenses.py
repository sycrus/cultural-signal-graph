"""Lens tagging + the Cone (#39): classify once per lens (cached as an op), override
by the strategist (attributed, replayable, undoable)."""

import json

import pytest
from fastapi.testclient import TestClient

from cultural_signal_graph.futures import lenses
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


@pytest.fixture()
def store(runs):
    return ExplorationStore(runs.root)


@pytest.fixture()
def exp_id(store, run_id):
    x = store.create(run_id, FIXTURE_GOAL, SEED_ANCHORS, start_year=2026)["exploration"]["id"]
    store.generate(run_id, x)
    return x


def cone(snap):
    return {p["id"]: p["tags"].get("cone") for p in snap["projections"]}


def retags(store, run_id, exp_id):
    return [o for o in store.ops(run_id, exp_id) if o["op"] == "retag"]


def test_first_open_tags_everything_once(store, run_id, exp_id):
    assert store.snapshot(run_id, exp_id)["lenses"]["cone"]["untagged"] == 15
    snap = store.classify(run_id, exp_id, "cone")
    tags = cone(snap)
    assert all(tags.values()) and snap["lenses"]["cone"]["untagged"] == 0
    assert tags["o1-glasses-default"]["value"] == "projected"  # the baseline, by construction
    assert tags["o2-footage-leak"]["value"] == "possible"
    assert all(t["source"] == "model" for t in tags.values())
    store.classify(run_id, exp_id, "cone")  # reopening: cached
    assert len(retags(store, run_id, exp_id)) == 1


def test_new_projections_are_tagged_on_the_next_open(store, run_id, exp_id):
    store.classify(run_id, exp_id, "cone")
    store.add_projection(run_id, exp_id, "wildcard", "A solar storm wipes out positioning", [2031, 2031])
    snap = store.classify(run_id, exp_id, "cone")
    assert cone(snap)["wildcard-1"]["value"] == "preposterous"
    last = retags(store, run_id, exp_id)[-1]
    assert list(last["tags"]) == ["wildcard-1"]  # only the new one


def test_override_is_attributed_survives_replay_and_undoes(runs, store, run_id, exp_id):
    store.classify(run_id, exp_id, "cone")
    snap = store.set_tag(run_id, exp_id, "o1-backlash", "cone", {"value": "possible", "preferable": True}, author="jo")
    tag = cone(snap)["o1-backlash"]
    assert tag == {"value": "possible", "preferable": True, "source": "human", "op": snap["cursor"] - 1, "model_value": "plausible"}
    op = store.ops(run_id, exp_id)[-1]
    assert op["author"] == "jo" and op["before"]["value"] == "plausible"
    reopened = ExplorationStore(runs.root).snapshot(run_id, exp_id)
    assert cone(reopened)["o1-backlash"]["source"] == "human"
    snap = store.undo(run_id, exp_id)
    assert cone(snap)["o1-backlash"]["source"] == "model"


def test_bad_tags_are_refused(store, run_id, exp_id):
    with pytest.raises(ValueError):
        store.set_tag(run_id, exp_id, "o1-backlash", "cone", {"value": "probable"})  # no probabilities
    with pytest.raises(KeyError):
        store.classify(run_id, exp_id, "astrology")


def test_live_classification_is_one_cheap_deterministic_call(monkeypatch, runs, run_id, exp_id):
    calls = []

    def fake(model, system, prompt, max_tokens, temperature=None):
        calls.append((model, prompt, temperature))
        ids = [line.split(" ")[1] for line in prompt.splitlines() if line.startswith("- o")]
        return json.dumps({"tags": {i: {"value": "plausible", "preferable": i == "o1-backlash"} for i in ids}}), Usage(model, 9, 9, 18)

    monkeypatch.setattr(lenses, "call_model", fake)
    store = ExplorationStore(runs.root, mode="live")
    snap = store.classify(run_id, exp_id, "cone")
    assert len(calls) == 1
    model, prompt, temperature = calls[0]
    assert model == "deepseek-v4-flash" and temperature == 0.0
    assert "o1-glasses-default" not in prompt  # the baseline is fixed, not asked
    assert cone(snap)["o1-backlash"]["preferable"] is True
    op = retags(store, run_id, exp_id)[0]
    assert op["input"]["prompt"] == prompt and op["output"]


def test_http_seam(runs, run_id, exp_id):
    client = TestClient(create_app(runs))
    base = f"/api/runs/{run_id}/explorations/{exp_id}"
    assert client.post(f"{base}/lenses/cone/classify").json()["lenses"]["cone"]["untagged"] == 0
    res = client.put(f"{base}/projections/o1-backlash/tags/cone", json={"value": "possible", "extras": {"preferable": True}})
    assert res.status_code == 200
    assert client.put(f"{base}/projections/o1-backlash/tags/cone", json={"value": "likely"}).status_code == 409
    assert client.post(f"{base}/lenses/nope/classify").status_code == 404
