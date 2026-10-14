"""Three Horizons (#41): projections and anchors tagged by role (H1 / H2- / H2+ /
H3), not by time distance; flagged evidence surfaces as candidate H3 seeds."""

import json

import pytest

from cultural_signal_graph.futures import lenses
from cultural_signal_graph.futures.fixtures import FIXTURE_GOAL
from cultural_signal_graph.futures.store import ExplorationStore
from cultural_signal_graph.models import Usage
from cultural_signal_graph.runstore import RunStore, fixture_stage_fns

ANCHORS = ["sig-release-note", "sig-search-spike", "sig-viral-fad", "sig-gaming-chatter"]


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


def test_projections_and_anchors_are_tagged_by_role(store, run_id, exp_id):
    assert store.snapshot(run_id, exp_id)["lenses"]["horizons"]["untagged"] == 15 + 4
    snap = store.classify(run_id, exp_id, "horizons")
    assert snap["lenses"]["horizons"]["untagged"] == 0
    anchors = {a["id"]: a["tags"]["horizons"]["value"] for a in snap["anchors"]}
    assert anchors["sig-viral-fad"] == "H3"  # the flagged conflict: a candidate pocket of the future
    roles = {p["tags"]["horizons"]["value"] for p in snap["projections"]}
    assert roles <= {"H1", "H2-", "H2+", "H3"}
    # role, not time: the baseline is H1 even at order 5
    assert next(p for p in snap["projections"] if p["id"] == "o5-ambient-computing")["tags"]["horizons"]["value"] == "H1"


def test_anchor_roles_can_be_overridden(store, run_id, exp_id):
    store.classify(run_id, exp_id, "horizons")
    snap = store.set_tag(run_id, exp_id, "sig-search-spike", "horizons", {"value": "H3"}, author="jo")
    tag = next(a for a in snap["anchors"] if a["id"] == "sig-search-spike")["tags"]["horizons"]
    assert tag["value"] == "H3" and tag["source"] == "human"
    # anchors are only taggable by lenses that include them
    with pytest.raises(KeyError):
        store.set_tag(run_id, exp_id, "sig-search-spike", "cone", {"value": "plausible"})


def test_live_prompt_explains_role_not_time_and_lists_anchors(monkeypatch, runs, run_id, exp_id):
    seen = []

    def fake(model, system, prompt, max_tokens, temperature=None):
        seen.append(prompt)
        ids = [line[2:].split(" ")[0] for line in prompt.splitlines() if line.startswith("- ")]
        return json.dumps({"tags": {i: {"value": "H2+"} for i in ids}}), Usage(model, 1, 1, 2)

    monkeypatch.setattr(lenses, "call_model", fake)
    store = ExplorationStore(runs.root, mode="live")
    snap = store.classify(run_id, exp_id, "horizons")
    (prompt,) = seen
    assert "ROLE in the system, not by how far away it is in time" in prompt
    assert "- sig-viral-fad" in prompt and "- o1-backlash" in prompt
    assert snap["lenses"]["horizons"]["untagged"] == 0
