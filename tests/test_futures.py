"""Futures mode (PRD-futures.md): explorations over a forecast run's anchors.

Exercised through the HTTP seam over a fixture-mode store, plus the operation log /
replay seam directly — never generator internals."""

import json

import pytest
from fastapi.testclient import TestClient

from cultural_signal_graph.futures.fixtures import FIXTURE_GOAL
from cultural_signal_graph.futures.log import OperationLog
from cultural_signal_graph.futures.replay import replay
from cultural_signal_graph.runstore import RunStore, fixture_stage_fns
from cultural_signal_graph.server import create_app

SEED_ANCHORS = ["sig-release-note", "sig-search-spike", "sig-viral-fad", "sig-gaming-chatter"]


@pytest.fixture()
def store(tmp_path):
    return RunStore(tmp_path, stage_fns=fixture_stage_fns())


@pytest.fixture()
def client(store):
    return TestClient(create_app(store))


def _new_run(client) -> str:
    res = client.post(
        "/api/runs",
        json={
            "category": "tech",
            "question": "AI wearables adoption",
            "window_start": "2026-01-01",
            "window_end": "2026-06-30",
        },
    )
    return res.json()["id"]


@pytest.fixture()
def extracted_run(client) -> str:
    """A run past extraction: parked at the sign-off gate."""
    run_id = _new_run(client)
    assert client.post(f"/api/runs/{run_id}/start").json()["status"] == "paused"
    return run_id


def _explore(client, run_id, anchors=SEED_ANCHORS, **kw) -> dict:
    body = {"goal": FIXTURE_GOAL, "anchor_ids": anchors, "horizon": 10, "orders": 5, **kw}
    res = client.post(f"/api/runs/{run_id}/explorations", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def test_futures_page_is_served(client):
    res = client.get("/futures")
    assert res.status_code == 200
    assert "futures.js" in res.text


def test_futures_unavailable_before_extraction(client):
    run_id = _new_run(client)
    assert client.get(f"/api/runs/{run_id}/futures/anchors").status_code == 409
    res = client.post(
        f"/api/runs/{run_id}/explorations",
        json={"goal": "x", "anchor_ids": ["sig-release-note"]},
    )
    assert res.status_code == 409


def test_anchors_after_extraction_mark_flagged_signals(client, extracted_run):
    anchors = {a["id"]: a for a in client.get(f"/api/runs/{extracted_run}/futures/anchors").json()}
    assert set(anchors) == set(SEED_ANCHORS)
    assert anchors["sig-viral-fad"]["kind"] == "flagged"
    assert anchors["sig-viral-fad"]["flag"] == "conflict"
    # not finalized yet: nothing is a claim
    assert all(a["kind"] != "claim" for a in anchors.values())


def test_anchors_after_brief_mark_claims(client, extracted_run):
    client.post(f"/api/runs/{extracted_run}/signoff", json={"decisions": {"edge-ai-headset-wearables": True}})
    anchors = {a["id"]: a for a in client.get(f"/api/runs/{extracted_run}/futures/anchors").json()}
    assert anchors["sig-release-note"]["kind"] == "claim"
    assert anchors["sig-viral-fad"]["kind"] == "flagged"


def test_create_then_generate_fixture_exploration(client, extracted_run):
    snap = _explore(client, extracted_run)
    assert snap["exploration"]["goal"] == FIXTURE_GOAL
    assert snap["projections"] == []
    assert [a["id"] for a in snap["anchors"]] == SEED_ANCHORS

    exp_id = snap["exploration"]["id"]
    snap = client.post(f"/api/runs/{extracted_run}/explorations/{exp_id}/generate").json()
    projections = {p["id"]: p for p in snap["projections"]}
    assert snap["orders_generated"] == 5
    assert {p["order"] for p in projections.values()} == {1, 2, 3, 4, 5}
    # convergence: one node with several parents, not duplicates
    assert projections["o2-audio-only"]["parents"] == ["o1-privacy-rules", "o1-backlash"]
    # a projection may grow from an earlier projection and an anchor at once
    assert projections["o2-headset-merge"]["anchors"] == ["sig-gaming-chatter"]
    for p in projections.values():
        assert p["parents"] or p["anchors"]
        assert p["window"][0] <= p["window"][1]


def test_unselected_anchors_prune_the_fixture(client, extracted_run):
    exp_id = _explore(client, extracted_run, anchors=["sig-viral-fad"])["exploration"]["id"]
    snap = client.post(f"/api/runs/{extracted_run}/explorations/{exp_id}/generate").json()
    ids = {p["id"] for p in snap["projections"]}
    assert "o1-backlash" in ids
    assert "o1-glasses-default" not in ids  # its anchors were not picked
    for p in snap["projections"]:
        assert set(p["parents"]) <= ids
        assert set(p["anchors"]) <= {"sig-viral-fad"}


def test_reopen_replays_to_the_same_state(client, store, extracted_run):
    exp_id = _explore(client, extracted_run)["exploration"]["id"]
    first = client.post(f"/api/runs/{extracted_run}/explorations/{exp_id}/generate").json()
    # a fresh app over the same files reopens the exploration identically
    reopened = TestClient(create_app(RunStore(store.root, stage_fns=fixture_stage_fns())))
    again = reopened.get(f"/api/runs/{extracted_run}/explorations/{exp_id}").json()
    assert again == first


def test_replay_is_deterministic(client, store, extracted_run):
    exp_id = _explore(client, extracted_run)["exploration"]["id"]
    client.post(f"/api/runs/{extracted_run}/explorations/{exp_id}/generate")
    ops = OperationLog(store.root / extracted_run / "explorations" / exp_id).active()
    assert [o["op"] for o in ops] == ["create"] + ["generate_order"] * 5
    assert replay(ops) == replay(json.loads(json.dumps(ops)))


def test_many_explorations_per_run_are_listed(client, extracted_run):
    a = _explore(client, extracted_run)["exploration"]["id"]
    b = _explore(client, extracted_run, goal="the direction of AR/VR wearables", orders=3)["exploration"]["id"]
    listed = client.get(f"/api/runs/{extracted_run}/explorations").json()
    assert {e["id"] for e in listed} == {a, b}
    by_id = {e["id"]: e for e in listed}
    assert by_id[b]["orders"] == 3
    assert by_id[a]["anchor_ids"] == SEED_ANCHORS


def test_bad_requests(client, extracted_run):
    res = client.post(
        f"/api/runs/{extracted_run}/explorations",
        json={"goal": "x", "anchor_ids": ["nope"]},
    )
    assert res.status_code == 409
    assert client.get(f"/api/runs/{extracted_run}/explorations/x-bad").status_code == 404
    assert client.get(f"/api/runs/{extracted_run}/explorations/..%2F..").status_code == 404
    assert client.get("/api/runs/unknown/explorations").status_code == 404
