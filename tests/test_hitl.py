"""Issue #5 acceptance tests for the HITL sign-off gate (LangGraph interrupt)."""

from langgraph.types import Command
from rdflib import Namespace

from cultural_signal_graph.fixtures import ALIGNED_EDGES, EXTRACTED, SEED_CORPUS
from cultural_signal_graph.pipeline import (
    build_forecast_graph,
    forecast_run_from_state,
    initial_state,
)

CSG = Namespace("https://cultural-signal-graph.dev/ontology#")
EX = Namespace("https://cultural-signal-graph.dev/example#")

EDGE_ID = "edge-ai-headset-wearables"


def _graph():
    return build_forecast_graph(
        extract_fn=lambda _: EXTRACTED, align_fn=lambda _: ALIGNED_EDGES
    )


def _invoke(graph):
    config = {"configurable": {"thread_id": "hitl-test"}}
    return graph.invoke(initial_state(SEED_CORPUS, "tech"), config), config


def _edge_status(graph):
    return [str(s) for s in graph.objects(EX[EDGE_ID], CSG.status)]


def _is_real(graph):
    return bool(list(graph.triples((EX["ai_headset"], CSG.equivalentTo, EX["ai_wearables"]))))


def test_low_confidence_edge_interrupts_for_sign_off():
    graph = _graph()
    result, _ = _invoke(graph)
    interrupts = result.get("__interrupt__")
    assert interrupts, "expected the gate to interrupt for sign-off"
    payload = interrupts[0].value
    assert EDGE_ID in [e["id"] for e in payload["sign_off"]]


def test_approved_edge_becomes_real():
    graph = _graph()
    _result, config = _invoke(graph)
    state = graph.invoke(Command(resume={EDGE_ID: True}), config)
    forecast = forecast_run_from_state(state)
    assert _is_real(forecast.graph)
    assert "real" in _edge_status(forecast.graph)


def test_rejected_edge_is_not_real():
    graph = _graph()
    _result, config = _invoke(graph)
    state = graph.invoke(Command(resume={EDGE_ID: False}), config)
    forecast = forecast_run_from_state(state)
    assert not _is_real(forecast.graph)
    assert "rejected" in _edge_status(forecast.graph)
