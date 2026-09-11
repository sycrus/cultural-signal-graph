"""Issue #20 acceptance tests for the local web app server."""

import pytest
from fastapi.testclient import TestClient

from cultural_signal_graph.runstore import RunStore, fixture_stage_fns
from cultural_signal_graph.server import create_app


@pytest.fixture()
def client(tmp_path):
    store = RunStore(tmp_path, stage_fns=fixture_stage_fns())
    return TestClient(create_app(store))


@pytest.fixture()
def run_id(client):
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


def test_root_serves_the_stepper_shell(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Cultural Signal Graph" in res.text
    assert "app.js" in res.text


def test_runs_api_round_trip(client):
    res = client.post(
        "/api/runs",
        json={
            "category": "tech",
            "question": "AI wearables adoption",
            "window_start": "2026-01-01",
            "window_end": "2026-06-30",
        },
    )
    assert res.status_code == 201
    run = res.json()
    assert run["status"] == "created"
    assert run["sources"]

    listed = client.get("/api/runs").json()
    assert [r["id"] for r in listed] == [run["id"]]

    snap = client.get(f"/api/runs/{run['id']}").json()
    assert snap["ask"]["category"] == "tech"
    assert snap["ask"]["window"]["end"] == "2026-06-30"
    assert snap["brief"] is None  # not finalized yet


def test_unknown_run_is_404(client):
    assert client.get("/api/runs/nope").status_code == 404


def test_sources_edit_and_reset(client, run_id):
    created = client.get(f"/api/runs/{run_id}").json()
    first = created["sources"][0]

    res = client.put(f"/api/runs/{run_id}/sources", json={"sources": [first]})
    assert res.status_code == 200
    assert [s["uri"] for s in res.json()["sources"]] == [first["uri"]]

    res = client.post(f"/api/runs/{run_id}/sources/reset")
    assert res.status_code == 200
    assert res.json()["sources"] == created["sources"]


def test_sources_edit_rejects_malformed_sources(client, run_id):
    res = client.put(f"/api/runs/{run_id}/sources", json={"sources": [{"uri": "x"}]})
    assert res.status_code == 422


def test_start_pauses_at_the_gate_then_conflicts(client, run_id):
    res = client.post(f"/api/runs/{run_id}/start")
    assert res.status_code == 200
    snap = res.json()
    assert snap["status"] == "paused"
    assert snap["pending"], "the demo corpus proposes one cross-domain edge"
    assert snap["stages"]["extract"]["status"] == "done"

    res = client.post(f"/api/runs/{run_id}/start")
    assert res.status_code == 409
