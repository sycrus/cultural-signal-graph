"""Edit, delete, undo/redo, stale, regenerate downstream (#34) — through the store
and the HTTP seam, over the recorded fixture exploration."""

import pytest
from fastapi.testclient import TestClient

from cultural_signal_graph.futures import generator as gen
from cultural_signal_graph.futures.fixtures import FIXTURE_GOAL
from cultural_signal_graph.futures.store import ExplorationStore
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
    x = store.create(run_id, FIXTURE_GOAL, SEED_ANCHORS, horizon=10, orders=5, start_year=2026)["exploration"]["id"]
    store.generate(run_id, x)
    return x


def by_id(snap):
    return {p["id"]: p for p in snap["projections"]}


def stale_ids(snap):
    return {p["id"] for p in snap["projections"] if p["stale"]}


# downstream of o1-privacy-rules in the fixture DAG
PRIVACY_DOWNSTREAM = {
    "o2-audio-only", "o2-footage-leak", "o3-recording-norms",
    "o4-subsidized-monitors", "o4-unaugmented-status", "o5-two-tier-society",
}


def test_fresh_generation_has_nothing_stale(store, run_id, exp_id):
    assert stale_ids(store.snapshot(run_id, exp_id)) == set()


def test_editing_a_statement_marks_exactly_its_descendants_stale(store, run_id, exp_id):
    snap = store.edit(run_id, exp_id, "o1-privacy-rules", statement="Privacy rules are shelved after lobbying")
    assert by_id(snap)["o1-privacy-rules"]["statement"] == "Privacy rules are shelved after lobbying"
    assert not by_id(snap)["o1-privacy-rules"]["stale"]
    assert stale_ids(snap) == PRIVACY_DOWNSTREAM


def test_window_edit_inversion_is_a_timing_conflict_not_stale(store, run_id, exp_id):
    snap = store.edit(run_id, exp_id, "o1-privacy-rules", window=[2031, 2032])
    p = by_id(snap)
    assert p["o2-footage-leak"]["timing_conflict"]  # 2029 now starts before its parent
    assert stale_ids(snap) == set()


def test_delete_marks_descendants_stale_and_keeps_them(store, run_id, exp_id):
    snap = store.delete(run_id, exp_id, "o1-privacy-rules")
    assert "o1-privacy-rules" not in by_id(snap)
    assert snap["removed"]["o1-privacy-rules"].startswith("Always-on cameras")
    assert stale_ids(snap) == PRIVACY_DOWNSTREAM


def test_undo_redo_round_trips_every_op(store, run_id, exp_id):
    before = store.snapshot(run_id, exp_id)
    store.edit(run_id, exp_id, "o1-backlash", statement="changed", window=[2027, 2029])
    after_edit = store.snapshot(run_id, exp_id)
    store.delete(run_id, exp_id, "o2-footage-leak")
    after_delete = store.snapshot(run_id, exp_id)

    def strip(s):  # cursor/undo flags differ by design
        return {k: v for k, v in s.items() if k not in ("cursor", "can_undo", "can_redo")}

    assert strip(store.undo(run_id, exp_id)) == strip(after_edit)
    assert strip(store.undo(run_id, exp_id)) == strip(before)
    assert strip(store.redo(run_id, exp_id)) == strip(after_edit)
    assert strip(store.redo(run_id, exp_id)) == strip(after_delete)
    with pytest.raises(ValueError):
        store.redo(run_id, exp_id)


def test_redo_of_a_generation_makes_no_model_call(runs, run_id):
    calls = []

    def counting(state, order):
        calls.append(order)
        return gen.fixture_generator(state, order)

    store = ExplorationStore(runs.root, generator=counting)
    x = store.create(run_id, FIXTURE_GOAL, SEED_ANCHORS, start_year=2026)["exploration"]["id"]
    full = store.generate(run_id, x)
    assert len(calls) == 5
    for _ in range(5):
        store.undo(run_id, x)
    assert store.snapshot(run_id, x)["projections"] == []
    for _ in range(5):
        store.redo(run_id, x)
    assert len(calls) == 5  # replayed from the log, not regenerated
    assert by_id(store.snapshot(run_id, x)) == by_id(full)


def test_new_action_after_undo_drops_the_redo_tail(store, run_id, exp_id):
    store.edit(run_id, exp_id, "o1-backlash", statement="first")
    store.undo(run_id, exp_id)
    snap = store.edit(run_id, exp_id, "o1-backlash", statement="second")
    assert not snap["can_redo"]
    assert by_id(snap)["o1-backlash"]["statement"] == "second"
    assert [o["op"] for o in store.ops(run_id, exp_id)][-2:] == ["generate_order", "edit"]


def test_create_cannot_be_undone(store, run_id):
    x = store.create(run_id, FIXTURE_GOAL, SEED_ANCHORS)["exploration"]["id"]
    with pytest.raises(ValueError):
        store.undo(run_id, x)


def test_regenerate_downstream_replaces_the_stale_branch(store, run_id, exp_id):
    store.edit(run_id, exp_id, "o1-privacy-rules", statement="Privacy rules are shelved after lobbying")
    snap = store.regenerate(run_id, exp_id, "o1-privacy-rules")
    ps = by_id(snap)
    assert not PRIVACY_DOWNSTREAM & set(ps)  # the stale ones are replaced
    assert stale_ids(snap) == set()
    new = [p for p in snap["projections"] if p["op"] == snap["cursor"] - 1]
    assert new and any("o1-privacy-rules" in p["parents"] for p in new)
    for p in new:
        assert p["parents"]  # grows from the branch, never unanchored
    # one op: a single undo brings the stale branch back
    snap = store.undo(run_id, exp_id)
    assert stale_ids(snap) == PRIVACY_DOWNSTREAM


def test_regenerate_needs_something_stale(store, run_id, exp_id):
    with pytest.raises(ValueError):
        store.regenerate(run_id, exp_id, "o1-backlash")


def test_regenerating_the_baseline_keeps_one_baseline_branch(store, run_id, exp_id):
    store.edit(run_id, exp_id, "o1-glasses-default", statement="Glasses stall at a niche")
    snap = store.regenerate(run_id, exp_id, "o1-glasses-default")
    per_order = {}
    for p in snap["projections"]:
        per_order.setdefault(p["order"], 0)
        per_order[p["order"]] += p["baseline"]
    assert all(n <= 1 for n in per_order.values())
    assert per_order[1] == 1 and per_order[2] == 1


def test_http_seam(runs, run_id, exp_id):
    client = TestClient(create_app(runs))
    base = f"/api/runs/{run_id}/explorations/{exp_id}"
    res = client.patch(f"{base}/projections/o1-backlash", json={"statement": "edited", "author": "jo"})
    assert res.status_code == 200
    op = client.get(f"{base}/ops/{res.json()['cursor'] - 1}").json()
    assert op["op"] == "edit" and op["author"] == "jo" and op["before"]["statement"].startswith("AI glasses")
    assert client.patch(f"{base}/projections/o1-backlash", json={"window": [2030, 2029]}).status_code == 409
    assert client.patch(f"{base}/projections/nope", json={"statement": "x"}).status_code == 404
    assert client.delete(f"{base}/projections/o2-footage-leak").status_code == 200
    assert client.post(f"{base}/undo").json()["can_redo"]
    assert client.post(f"{base}/redo").status_code == 200
    assert client.post(f"{base}/projections/o1-backlash/regenerate").status_code == 200
