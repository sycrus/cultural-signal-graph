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


EDGE_ID = "edge-ai-headset-wearables"


def test_exports_serve_after_finalize(client, run_id):
    # before finalize there is nothing to export
    assert client.get(f"/api/runs/{run_id}/exports/brief.md").status_code == 404

    client.post(f"/api/runs/{run_id}/start")
    client.post(f"/api/runs/{run_id}/signoff", json={"decisions": {EDGE_ID: True}})

    for name in ("brief.md", "brief.json", "brief.pptx", "graph.ttl", "usage.json"):
        res = client.get(f"/api/runs/{run_id}/exports/{name}")
        assert res.status_code == 200, name
    assert "Forecast brief" in client.get(f"/api/runs/{run_id}/exports/brief.md").text
    # unknown names (and traversal attempts) are not served
    assert client.get(f"/api/runs/{run_id}/exports/run.json").status_code == 404
    assert client.get(f"/api/runs/{run_id}/exports/..%2Frun.json").status_code == 404


def test_graph_explorer_serves_for_the_embed(client, run_id):
    assert client.get(f"/runs/{run_id}/graph.html").status_code == 404  # not finalized

    client.post(f"/api/runs/{run_id}/start")
    client.post(f"/api/runs/{run_id}/signoff", json={"decisions": {EDGE_ID: True}})

    res = client.get(f"/runs/{run_id}/graph.html")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "cytoscape" in res.text
    assert "ai_wearables" in res.text  # the data blob embeds the graph
    # the served page carries the notes overlay; the exported artifact does not
    assert f"/api/runs/{run_id}/notes" in res.text
    exported = client.get(f"/api/runs/{run_id}/exports/graph.html")
    assert exported.status_code == 404  # not in the export allowlist; artifact is offline


def test_notes_round_trip(client, run_id):
    res = client.get(f"/api/runs/{run_id}/notes")
    assert res.status_code == 200
    assert res.json() == []

    res = client.post(
        f"/api/runs/{run_id}/notes",
        json={"target_id": "sig-release-note", "target_kind": "node", "text": "check vs Q3 numbers", "author": "joe"},
    )
    assert res.status_code == 201
    note = res.json()
    assert note["text"] == "check vs Q3 numbers"
    assert note["created_at"]

    assert client.get(f"/api/runs/{run_id}/notes").json() == [note]

    assert (
        client.post(f"/api/runs/{run_id}/notes", json={"target_id": "x", "text": "  "}).status_code
        == 422
    )


def test_signoff_approve_resumes_and_finalizes(client, run_id):
    client.post(f"/api/runs/{run_id}/start")

    res = client.post(f"/api/runs/{run_id}/signoff", json={"decisions": {EDGE_ID: True}})
    assert res.status_code == 200
    snap = res.json()
    assert snap["status"] == "completed"
    assert snap["pending"] == []
    assert snap["decisions"] == {EDGE_ID: True}
    assert snap["brief"]["gated_edges"][0]["status"] == "real"

    # the run is no longer at the gate
    res = client.post(f"/api/runs/{run_id}/signoff", json={"decisions": {EDGE_ID: False}})
    assert res.status_code == 409


def test_signoff_undo_reopens_the_decision(client, run_id):
    client.post(f"/api/runs/{run_id}/start")
    client.post(f"/api/runs/{run_id}/signoff", json={"decisions": {EDGE_ID: True}})

    res = client.post(f"/api/runs/{run_id}/signoff/undo")
    assert res.status_code == 200
    snap = res.json()
    assert snap["status"] == "paused"
    assert snap["decisions"] == {}
    assert [e["id"] for e in snap["pending"]] == [EDGE_ID]
    assert snap["pending"][0]["left_category"] == "gaming"

    # the re-made decision goes through and the brief reflects it
    res = client.post(f"/api/runs/{run_id}/signoff", json={"decisions": {EDGE_ID: False}})
    assert res.status_code == 200
    assert res.json()["brief"]["gated_edges"][0]["status"] == "rejected"


def test_undo_without_a_pause_conflicts(tmp_path):
    # the injected align proposes no edges, so the run never pauses at the gate
    fns = fixture_stage_fns()
    store = RunStore(tmp_path, stage_fns=(fns[0], lambda _e: [], fns[2]))
    client = TestClient(create_app(store))
    run = client.post(
        "/api/runs",
        json={
            "category": "tech",
            "question": "AI wearables adoption",
            "window_start": "2026-01-01",
            "window_end": "2026-06-30",
        },
    ).json()
    client.post(f"/api/runs/{run['id']}/start")
    assert client.post(f"/api/runs/{run['id']}/signoff/undo").status_code == 409
