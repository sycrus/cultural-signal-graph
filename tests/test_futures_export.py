"""Graph-tab futures layer, RDF named graphs, export / import (#43)."""

import pytest
from fastapi.testclient import TestClient
from rdflib import Dataset, URIRef
from rdflib.namespace import RDF

from cultural_signal_graph.futures.fixtures import FIXTURE_GOAL
from cultural_signal_graph.futures.rdf import CSGF, EX, exploration_uri
from cultural_signal_graph.futures.store import ExplorationStore
from cultural_signal_graph.runstore import RunStore, fixture_stage_fns
from cultural_signal_graph.server import create_app

SEED_ANCHORS = ["sig-release-note", "sig-search-spike", "sig-viral-fad", "sig-gaming-chatter"]
EDGE = "edge-ai-headset-wearables"


def _run(runs):
    rid = runs.create("tech", "AI wearables adoption", "2026-01-01", "2026-06-30")["id"]
    runs.start(rid)
    runs.signoff(rid, {EDGE: True})
    return rid


@pytest.fixture()
def runs(tmp_path):
    return RunStore(tmp_path, stage_fns=fixture_stage_fns())


@pytest.fixture()
def run_id(runs):
    return _run(runs)


@pytest.fixture()
def store(runs):
    return ExplorationStore(runs.root)


@pytest.fixture()
def exp_id(store, run_id):
    x = store.create(run_id, FIXTURE_GOAL, SEED_ANCHORS, start_year=2026)["exploration"]["id"]
    store.generate(run_id, x)
    store.add_projection(run_id, x, "assumption", "Subsidies arrive", [2028, 2029],
                         reference={"url": "https://example.gov/plan", "excerpt": "A plan. More."})
    return x


def test_brief_is_byte_identical_with_and_without_explorations(runs, store, run_id, exp_id):
    bare = _run(runs)  # same corpus, no explorations
    store.fork(run_id, exp_id, "o1-backlash", hint="x")
    for name in ("brief.md", "brief.json", "graph.ttl"):
        assert (runs.root / run_id / name).read_bytes() == (runs.root / bare / name).read_bytes(), name
    # re-finalizing after futures work (undo + re-sign) still yields the same brief
    runs.undo_signoff(run_id)
    runs.signoff(run_id, {EDGE: True})
    assert (runs.root / run_id / "brief.json").read_bytes() == (runs.root / bare / "brief.json").read_bytes()


def test_exploration_is_a_named_graph_beside_the_evidence(runs, run_id, exp_id):
    client = TestClient(create_app(runs))
    res = client.get(f"/api/runs/{run_id}/futures.trig")
    assert res.status_code == 200
    ds = Dataset().parse(data=res.text, format="trig")
    named = ds.graph(exploration_uri(exp_id))
    projections = set(named.subjects(RDF.type, CSGF.Projection))
    assert len(projections) == 16
    # projections point at the evidence graph's own signal nodes
    merge = URIRef(f"{exploration_uri(exp_id)}#o2-headset-merge")
    assert (merge, CSGF.growsFrom, EX["sig-gaming-chatter"]) in named
    assert (EX["sig-gaming-chatter"], RDF.type, None) in ds.default_graph  # evidence stays default
    assert not list(ds.default_graph.subjects(RDF.type, CSGF.Projection))  # and stays clean


def test_graph_tab_futures_layer_is_a_toggle(runs, run_id, exp_id):
    client = TestClient(create_app(runs))
    plain = client.get(f"/runs/{run_id}/graph.html").text
    layered = client.get(f"/runs/{run_id}/graph.html?futures_layer=true").text
    assert '"kind": "projection"' not in plain
    assert '"kind": "projection"' in layered
    assert '"kind": "growsFrom"' in layered
    assert '"kind": "reference"' in layered


def test_exports(runs, run_id, exp_id):
    client = TestClient(create_app(runs))
    base = f"/api/runs/{run_id}/explorations/{exp_id}/exports"
    md = client.get(f"{base}/exploration.md")
    assert md.status_code == 200 and "attachment" in md.headers["content-disposition"]
    assert md.text.startswith(f"# Exploration: {FIXTURE_GOAL}")
    assert "## Order 5" in md.text and "grows from:" in md.text
    assert "baseline" in md.text and "assumption" in md.text
    js = client.get(f"{base}/exploration.json").json()
    assert js["exploration"]["id"] == exp_id
    assert client.get(f"{base}/exploration.trig").status_code == 200
    assert client.get(f"{base}/secrets.txt").status_code == 404


def test_log_reimports_to_the_same_state(runs, store, run_id, exp_id):
    client = TestClient(create_app(runs))
    log = client.get(f"/api/runs/{run_id}/explorations/{exp_id}/exports/log.jsonl").text
    res = client.post(f"/api/runs/{run_id}/explorations/import", json={"log": log})
    assert res.status_code == 201
    copy = res.json()
    assert copy["exploration"]["id"] != exp_id
    assert copy["exploration"]["imported_from"] == exp_id
    original = store.snapshot(run_id, exp_id)
    assert copy["projections"] == original["projections"]
    assert copy["anchors"] == original["anchors"]
    assert client.post(f"/api/runs/{run_id}/explorations/import", json={"log": "nope"}).status_code == 409
    assert client.post(f"/api/runs/{run_id}/explorations/import", json={"log": '{"op": "edit"}'}).status_code == 409
