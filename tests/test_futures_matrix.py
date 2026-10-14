"""The 2×2 Matrix (#40): axis proposals from contested evidence, chosen axes,
quadrant placement, quadrant-seeded branches, scenario narratives as annotations."""

import json

import pytest
from fastapi.testclient import TestClient

from cultural_signal_graph.futures import generator as gen
from cultural_signal_graph.futures import matrix
from cultural_signal_graph.futures.fixtures import FIXTURE_GOAL
from cultural_signal_graph.futures.store import ExplorationStore
from cultural_signal_graph.models import Usage
from cultural_signal_graph.runstore import RunStore, fixture_stage_fns
from cultural_signal_graph.server import create_app

ANCHORS = ["sig-release-note", "sig-search-spike", "sig-viral-fad", "sig-gaming-chatter"]
AXES = [
    {"name": "Privacy regulation", "low": "permissive", "high": "restrictive", "from": ["sig-viral-fad"]},
    {"name": "Consumer appetite", "low": "indifferent", "high": "eager", "from": []},
]


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
    x = store.create(run_id, FIXTURE_GOAL, ANCHORS, start_year=2026)["exploration"]["id"]
    store.generate(run_id, x)
    return x


def test_matrix_needs_axes_before_placing(store, run_id, exp_id):
    snap = store.snapshot(run_id, exp_id)
    assert snap["lenses"]["matrix"]["ready"] is False
    with pytest.raises(ValueError):
        store.classify(run_id, exp_id, "matrix")


def test_axis_proposals_cite_the_flags_they_came_from(store, run_id, exp_id):
    snap = store.propose_axes(run_id, exp_id)
    cands = snap["axis_candidates"]
    assert 3 <= len(cands) <= 4
    assert any("sig-viral-fad" in c["from"] for c in cands)  # the flagged conflict
    for c in cands:
        assert set(c["from"]) <= set(ANCHORS)


def test_set_axes_then_place_into_quadrants(store, run_id, exp_id):
    snap = store.set_axes(run_id, exp_id, AXES)
    assert snap["axes"][0]["name"] == "Privacy regulation" and snap["lenses"]["matrix"]["ready"]
    snap = store.classify(run_id, exp_id, "matrix")
    assert all(p["tags"]["matrix"]["value"] in ("q1", "q2", "q3", "q4", "none") for p in snap["projections"])
    # new axes are a new matrix: placements start over
    snap = store.set_axes(run_id, exp_id, [AXES[1], AXES[0]])
    assert all("matrix" not in p["tags"] for p in snap["projections"])
    with pytest.raises(ValueError):
        store.set_axes(run_id, exp_id, AXES[:1])


def test_seeded_fork_records_its_constraint_and_lands_in_its_quadrant(store, run_id, exp_id):
    store.set_axes(run_id, exp_id, AXES)
    before = {p["id"] for p in store.snapshot(run_id, exp_id)["projections"]}
    snap = store.seed_quadrant(run_id, exp_id, "q2")
    seeded = [p for p in snap["projections"] if p["id"] not in before]
    assert seeded and all(p["origin"] == "seeded" for p in seeded)
    assert all(p["tags"]["matrix"]["value"] == "q2" and p["tags"]["matrix"]["source"] == "seeded" for p in seeded)
    assert all(p["parents"] or p["anchors"] for p in seeded)  # grown from the present, never unanchored
    op = store.ops(run_id, exp_id)[-1]
    assert op["op"] == "seed_fork" and op["quadrant"] == "q2"
    assert op["constraint"] == {"Privacy regulation": "permissive", "Consumer appetite": "eager"}


def test_live_seed_prompt_states_the_world(monkeypatch, runs, run_id, exp_id):
    prompts = []

    def fake(prompt, call_type="generate"):
        prompts.append(prompt)
        out = {"projections": [{"id": "s1", "statement": "Lax rules, eager buyers", "from": ["sig-release-note"],
                                "window": [2027, 2028], "baseline": False, "discontinuity": False}]} if len(prompts) == 1 else {"projections": []}
        return json.dumps(out), Usage("m", 1, 1, 2), "deepseek-v4-flash", 0.9

    monkeypatch.setattr(gen, "_call_generation_model", fake)
    store = ExplorationStore(runs.root, mode="live", generator=gen.fixture_generator)
    store.set_axes(run_id, exp_id, AXES)
    store.seed_quadrant(run_id, exp_id, "q2")
    assert "Privacy regulation is permissive and Consumer appetite is eager" in prompts[0]


def test_narrative_is_an_annotation_that_goes_stale(store, run_id, exp_id):
    store.set_axes(run_id, exp_id, AXES)
    store.classify(run_id, exp_id, "matrix")
    n_before = len(store.snapshot(run_id, exp_id)["projections"])
    snap = store.write_narrative(run_id, exp_id, "q1")
    (ann,) = snap["annotations"]
    assert ann["key"] == "q1" and ann["text"] and not ann["stale"]
    assert len(snap["projections"]) == n_before  # a lens never writes projections
    member = ann["based_on"][0]
    store.set_tag(run_id, exp_id, member, "matrix", {"value": "q3"})  # moved out of the quadrant
    assert store.snapshot(run_id, exp_id)["annotations"][0]["stale"]
    store.undo(run_id, exp_id)
    store.edit(run_id, exp_id, member, statement="reworded")  # re-stated
    assert store.snapshot(run_id, exp_id)["annotations"][0]["stale"]


def test_live_axes_and_narrative_are_traced_calls(monkeypatch, runs, run_id, exp_id):
    calls = []

    def fake(model, system, prompt, max_tokens, temperature=None):
        calls.append((prompt, temperature))
        if "candidate axes" in prompt:
            return json.dumps({"axes": [
                {"name": "A", "low": "a-", "high": "a+", "from": ["sig-viral-fad", "bogus"], "why": "w"},
                {"name": "B", "low": "b-", "high": "b+", "from": [], "why": "w"},
                {"name": "C", "low": "c-", "high": "c+", "from": [], "why": "w"},
            ]}), Usage(model, 1, 1, 2)
        return json.dumps({"narrative": "A world of eager buyers."}), Usage(model, 1, 1, 2)

    monkeypatch.setattr(matrix, "call_model", fake)
    store = ExplorationStore(runs.root, mode="live")
    snap = store.propose_axes(run_id, exp_id)
    assert snap["axis_candidates"][0]["from"] == ["sig-viral-fad"]  # unknown ids dropped
    assert calls[0][1] == 0.5 and "[conflict]" in calls[0][0]
    store.set_axes(run_id, exp_id, snap["axis_candidates"][:2])
    snap = store.write_narrative(run_id, exp_id, "q1")
    assert snap["annotations"][0]["text"] == "A world of eager buyers."
    op = store.ops(run_id, exp_id)[-1]
    assert op["op"] == "annotate" and op["input"]["prompt"] == calls[1][0]


def test_http_seam(runs, run_id, exp_id):
    client = TestClient(create_app(runs))
    base = f"/api/runs/{run_id}/explorations/{exp_id}/lenses/matrix"
    assert client.post(f"{base}/quadrants/q1/seed").status_code == 409  # no axes yet
    assert client.post(f"{base}/axes/propose").status_code == 200
    res = client.put(f"{base}/axes", json={"axes": AXES})
    assert res.status_code == 200 and res.json()["axes"][0]["from"] == ["sig-viral-fad"]
    assert client.post(f"{base}/quadrants/q3/seed").status_code == 200
    assert client.post(f"{base}/quadrants/q9/narrative").status_code == 404
    assert client.post(f"{base}/quadrants/q3/narrative").status_code == 200
