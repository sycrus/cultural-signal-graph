"""Issue #14 acceptance tests for file-backed checkpoints."""

import json

from langgraph.types import Command

from cultural_signal_graph.checkpoint import dump_state, file_checkpointer
from cultural_signal_graph.fixtures import ALIGNED_EDGES, DRAFTED_REASONING, EXTRACTED, SEED_CORPUS
from cultural_signal_graph.pipeline import (
    build_forecast_graph,
    forecast_run_from_state,
    initial_state,
)

EDGE_ID = "edge-ai-headset-wearables"


def _fns():
    return (
        lambda _: EXTRACTED,
        lambda _: ALIGNED_EDGES,
        lambda extraction, category: DRAFTED_REASONING,
    )


def test_checkpoint_resumable_across_restart(tmp_path):
    db = str(tmp_path / "checkpoints.sqlite")
    config = {"configurable": {"thread_id": "resume-test"}}
    extract_fn, align_fn, draft_fn = _fns()

    # "process 1": compile + invoke -> interrupt at the gate
    graph1 = build_forecast_graph(extract_fn, align_fn, draft_fn, file_checkpointer(db))
    result = graph1.invoke(initial_state(SEED_CORPUS, "tech"), config)
    payload = result["__interrupt__"][0].value["sign_off"]

    # "process 2": a fresh graph over the same persisted checkpoint -> resume
    graph2 = build_forecast_graph(extract_fn, align_fn, draft_fn, file_checkpointer(db))
    state = graph2.invoke(Command(resume={e["id"]: True for e in payload}), config)
    forecast = forecast_run_from_state(state)
    assert forecast.brief.claims
    assert any(e.status == "real" for e in forecast.brief.gated_edges)


def test_checkpoint_state_dumps_to_json(tmp_path):
    db = str(tmp_path / "checkpoints.sqlite")
    config = {"configurable": {"thread_id": "dump-test"}}
    extract_fn, align_fn, draft_fn = _fns()

    graph = build_forecast_graph(extract_fn, align_fn, draft_fn, file_checkpointer(db))
    result = graph.invoke(initial_state(SEED_CORPUS, "tech"), config)
    payload = result["__interrupt__"][0].value["sign_off"]
    state = graph.invoke(Command(resume={e["id"]: True for e in payload}), config)

    out = tmp_path / "state.json"
    dump_state(state, out)
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "category" in data
    assert "edges" in data
    assert "reasoning" in data
