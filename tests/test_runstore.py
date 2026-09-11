"""Acceptance tests for the file-backed run store: lifecycle (#20–#22), the notes
overlay (#25), and reopen/metrics data (#26). All fixture-based, no network."""

import pytest

from cultural_signal_graph.fixtures import SEED_CORPUS
from cultural_signal_graph.runstore import RunStore, fixture_stage_fns

EDGE_ID = "edge-ai-headset-wearables"


def _store(tmp_path, align=None):
    fns = fixture_stage_fns()
    if align is not None:
        fns = (fns[0], align, fns[2])
    return RunStore(tmp_path, stage_fns=fns)


def _create(store, **overrides):
    fields = dict(
        category="tech",
        question="AI wearables adoption",
        window_start="2026-01-01",
        window_end="2026-06-30",
        market=None,
    )
    fields.update(overrides)
    return store.create(**fields)


def test_create_discovers_sources_and_parks_at_created(tmp_path):
    store = _store(tmp_path)
    run = _create(store)
    assert run["status"] == "created"
    assert run["stages"]["ask"]["status"] == "done"
    assert run["stages"]["sources"]["status"] == "done"
    # fixture mode pins the recorded demo corpus — the fixture outputs cite it
    assert [s["uri"] for s in run["sources"]] == [s.uri for s in SEED_CORPUS]
    assert (tmp_path / run["id"] / "run.json").exists()


def test_start_pauses_at_the_gate_with_named_pending_edges(tmp_path):
    store = _store(tmp_path)
    run_id = _create(store)["id"]

    snap = store.start(run_id)

    assert snap["status"] == "paused"
    assert snap["stages"]["extract"]["status"] == "done"
    assert snap["stages"]["align"]["status"] == "done"
    assert "latency_ms" in snap["stages"]["extract"]
    assert snap["stages"]["sign-off"]["status"] == "paused"
    assert [e["id"] for e in snap["pending"]] == [EDGE_ID]
    edge = snap["pending"][0]
    assert edge["left"] == "AI headset" and edge["right"] == "AI wearables"
    assert (tmp_path / run_id / "state-pause.json").exists()
    assert (tmp_path / run_id / "checkpoints.sqlite").exists()


def test_start_without_edges_finalizes_straight_through(tmp_path):
    store = _store(tmp_path, align=lambda _extraction: [])
    run_id = _create(store)["id"]

    snap = store.start(run_id)

    assert snap["status"] == "completed"
    assert snap["stages"]["sign-off"]["status"] == "done"
    assert snap["brief"]["claims"]


def test_approve_makes_the_edge_real_and_writes_artifacts(tmp_path):
    store = _store(tmp_path)
    run_id = _create(store)["id"]
    store.start(run_id)

    snap = store.signoff(run_id, {EDGE_ID: True})

    assert snap["status"] == "completed"
    assert snap["decisions"] == {EDGE_ID: True}
    assert snap["stages"]["sign-off"]["status"] == "done"
    assert snap["stages"]["draft"]["status"] == "done"
    graph_ttl = (tmp_path / run_id / "graph.ttl").read_text(encoding="utf-8")
    assert '"real"' in graph_ttl
    for name in ("brief.md", "brief.json", "graph.html", "usage.json", "trends.json", "brief.pptx"):
        assert (tmp_path / run_id / name).exists(), name
    assert snap["brief"]["gated_edges"][0]["status"] == "real"


def test_reject_drops_the_edge(tmp_path):
    store = _store(tmp_path)
    run_id = _create(store)["id"]
    store.start(run_id)

    snap = store.signoff(run_id, {EDGE_ID: False})

    assert snap["status"] == "completed"
    assert snap["brief"]["gated_edges"][0]["status"] == "rejected"


def test_undo_reopens_the_sign_off_and_downstream_re_runs(tmp_path):
    store = _store(tmp_path)
    run_id = _create(store)["id"]
    store.start(run_id)
    store.signoff(run_id, {EDGE_ID: True})
    brief_before = (tmp_path / run_id / "brief.json").read_text(encoding="utf-8")

    snap = store.undo_signoff(run_id)

    assert snap["status"] == "paused"
    assert snap["decisions"] == {}
    assert [e["id"] for e in snap["pending"]] == [EDGE_ID]
    assert snap["stages"]["draft"]["status"] == "pending"
    assert snap["stages"]["brief"]["status"] == "pending"

    # the re-made decision resumes through the same checkpointed interrupt
    snap = store.signoff(run_id, {EDGE_ID: False})
    assert snap["status"] == "completed"
    assert snap["brief"]["gated_edges"][0]["status"] == "rejected"
    assert (tmp_path / run_id / "brief.json").read_text(encoding="utf-8") != brief_before


def test_reopen_across_restart(tmp_path):
    store = _store(tmp_path)
    run_id = _create(store)["id"]
    store.start(run_id)
    store.signoff(run_id, {EDGE_ID: True})

    # a fresh store (a restarted server) reads the same files
    reopened = RunStore(tmp_path, stage_fns=fixture_stage_fns())
    assert [r["id"] for r in reopened.list()] == [run_id]
    snap = reopened.snapshot(run_id)
    assert snap["status"] == "completed"
    assert snap["brief"]["claims"]


def test_source_edits_apply_before_start(tmp_path):
    store = _store(tmp_path)
    run = _create(store)

    edited = [dict(run["sources"][0])]
    snap = store.edit_sources(run["id"], edited)
    assert snap["sources"] == edited

    snap = store.reset_sources(run["id"])
    assert snap["sources"] == run["sources"]


def test_start_twice_is_rejected(tmp_path):
    store = _store(tmp_path)
    run_id = _create(store)["id"]
    store.start(run_id)
    with pytest.raises(ValueError):
        store.start(run_id)


def test_notes_are_an_append_only_overlay(tmp_path):
    store = _store(tmp_path)
    run_id = _create(store)["id"]
    store.start(run_id)
    store.signoff(run_id, {EDGE_ID: True})
    brief_before = (tmp_path / run_id / "brief.json").read_bytes()
    graph_before = (tmp_path / run_id / "graph.ttl").read_bytes()

    entity = "https://cultural-signal-graph.dev/example#ai_wearables"
    note = store.add_note(run_id, target_id=entity, text="Watch Qwen roadmap here.", author="joe")
    assert note["author"] == "joe"
    assert note["created_at"]
    store.add_note(run_id, target_id=entity, text="Second note.")

    notes = store.notes(run_id)
    assert [n["text"] for n in notes] == ["Watch Qwen roadmap here.", "Second note."]
    assert notes[1]["author"] == "strategist"  # default author

    # the overlay never touches the reasoning artifacts
    assert (tmp_path / run_id / "brief.json").read_bytes() == brief_before
    assert (tmp_path / run_id / "graph.ttl").read_bytes() == graph_before

    with pytest.raises(ValueError):
        store.add_note(run_id, target_id=entity, text="   ")
    with pytest.raises(ValueError):
        store.add_note(run_id, target_id="no-such-node", text="ghost note")
