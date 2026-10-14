"""Pending-edge anchors follow the sign-off gate (#37)."""

import pytest

from cultural_signal_graph.futures.fixtures import FIXTURE_GOAL
from cultural_signal_graph.futures.store import ExplorationStore
from cultural_signal_graph.runstore import RunStore, fixture_stage_fns

EDGE = "edge-ai-headset-wearables"
ANCHORS = ["sig-release-note", "sig-search-spike", "sig-viral-fad", "sig-gaming-chatter", EDGE]
# what rests on the edge in the fixture: the headset merge and everything below it
ON_EDGE = {"o2-headset-merge", "o3-glasses-first-games"}


@pytest.fixture()
def runs(tmp_path):
    return RunStore(tmp_path, stage_fns=fixture_stage_fns())


@pytest.fixture()
def run_id(runs):
    rid = runs.create("tech", "AI wearables adoption", "2026-01-01", "2026-06-30")["id"]
    runs.start(rid)  # paused at the gate: the edge is pending
    return rid


@pytest.fixture()
def store(runs):
    return ExplorationStore(runs.root)


@pytest.fixture()
def exp_id(store, run_id):
    x = store.create(run_id, FIXTURE_GOAL, ANCHORS, start_year=2026)["exploration"]["id"]
    store.generate(run_id, x)
    return x


def edge(snap):
    return next(a for a in snap["anchors"] if a["id"] == EDGE)


def stale(snap):
    return {p["id"] for p in snap["projections"] if p["stale"]}


def test_pending_edge_is_an_anchor(store, run_id, exp_id):
    snap = store.snapshot(run_id, exp_id)
    assert edge(snap)["pending"] and edge(snap)["status"] == "proposed"
    merge = next(p for p in snap["projections"] if p["id"] == "o2-headset-merge")
    assert EDGE in merge["anchors"]
    assert stale(snap) == set()


def test_rejecting_the_edge_stales_what_rests_on_it(runs, store, run_id, exp_id):
    runs.signoff(run_id, {EDGE: False})
    snap = store.snapshot(run_id, exp_id)
    assert edge(snap)["status"] == "rejected" and not edge(snap)["pending"]
    assert stale(snap) == ON_EDGE
    # a rejected edge is no longer offered to new explorations
    assert EDGE not in {a["id"] for a in store.anchors(run_id)}
    # and regenerating from the merge's parent replaces the stale branch
    snap = store.regenerate(run_id, exp_id, "o1-glasses-default")
    assert not ON_EDGE & {p["id"] for p in snap["projections"]}


def test_approving_clears_the_pending_tag(runs, store, run_id, exp_id):
    runs.signoff(run_id, {EDGE: True})
    snap = store.snapshot(run_id, exp_id)
    assert edge(snap)["status"] == "real" and not edge(snap)["pending"]
    assert stale(snap) == set()


def test_undoing_the_sign_off_re_evaluates(runs, store, run_id, exp_id):
    runs.signoff(run_id, {EDGE: False})
    assert stale(store.snapshot(run_id, exp_id)) == ON_EDGE
    runs.undo_signoff(run_id)
    snap = store.snapshot(run_id, exp_id)
    assert edge(snap)["pending"] and stale(snap) == set()
