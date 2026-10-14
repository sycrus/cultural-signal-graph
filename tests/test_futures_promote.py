"""Promotion (#44): a futures-scoped reference becomes a source of a NEW forecast run;
the original run and its explorations are untouched."""

import pytest
from fastapi.testclient import TestClient

from cultural_signal_graph.futures.fixtures import FIXTURE_GOAL
from cultural_signal_graph.futures.promote import promote
from cultural_signal_graph.futures.store import ExplorationStore
from cultural_signal_graph.runstore import RunStore, fixture_stage_fns
from cultural_signal_graph.server import create_app

ANCHORS = ["sig-release-note", "sig-search-spike", "sig-viral-fad", "sig-gaming-chatter"]
REF = {"url": "https://example.gov/ai-wearables-plan", "excerpt": "The ministry plans subsidies from 2028. Pilots in three cities."}


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
    x = store.create(run_id, FIXTURE_GOAL, ANCHORS, start_year=2026)["exploration"]["id"]
    store.generate(run_id, x)
    store.add_projection(run_id, x, "assumption", "Subsidies seed a second market", [2028, 2030], reference=REF)
    return x


def _files(root, run_id):
    return {p.relative_to(root): p.read_bytes() for p in (root / run_id).rglob("*") if p.is_file() and p.suffix != ".sqlite"}


def test_promotion_creates_a_new_run_and_leaves_the_original_untouched(runs, store, run_id, exp_id):
    before = _files(runs.root, run_id)
    out = promote(runs, store, run_id, exp_id, "ref-1", author="jo")
    assert _files(runs.root, run_id) == before  # not a byte changed in the original run

    new = out["run"]
    assert new["id"] != run_id and new["status"] == "created"
    assert new["ask"] == runs.snapshot(run_id)["ask"]
    uris = [s["uri"] for s in new["sources"]]
    assert uris[:-1] == [s["uri"] for s in runs.snapshot(run_id)["sources"]]
    assert uris[-1] == REF["url"] and new["sources"][-1]["text"] == REF["excerpt"]
    assert new["origin"] == {"promoted_from": {"run": run_id, "exploration": exp_id, "reference": "ref-1", "url": REF["url"]}}


def test_the_exploration_carries_over_and_grows_from_the_promoted_anchor(runs, store, run_id, exp_id):
    out = promote(runs, store, run_id, exp_id, "ref-1")
    carried = out["exploration"]
    assert carried["exploration"]["run_id"] == out["run"]["id"]
    assert carried["exploration"]["imported_from"] == exp_id
    original = {p["id"] for p in store.snapshot(run_id, exp_id)["projections"]}
    branch = [p for p in carried["projections"] if p["id"] not in original]
    assert branch and any("ref-1" in p["anchors"] for p in branch)
    ref = next(a for a in carried["anchors"] if a["id"] == "ref-1")
    assert ref["scope"] == "promoted"
    assert store.ops(out["run"]["id"], carried["exploration"]["id"])[-1]["op"] == "promote"


def test_only_futures_references_can_be_promoted(runs, store, run_id, exp_id):
    with pytest.raises(KeyError):
        promote(runs, store, run_id, exp_id, "sig-release-note")  # already evidence
    promote(runs, store, run_id, exp_id, "ref-1")


def test_http_seam(runs, run_id, exp_id):
    client = TestClient(create_app(runs))
    res = client.post(f"/api/runs/{run_id}/explorations/{exp_id}/references/ref-1/promote", json={"author": "jo"})
    assert res.status_code == 201
    new_id = res.json()["run"]["id"]
    assert client.get(f"/api/runs/{new_id}").json()["origin"]["promoted_from"]["reference"] == "ref-1"
    assert client.post(f"/api/runs/{run_id}/explorations/{exp_id}/references/nope/promote").status_code == 404
