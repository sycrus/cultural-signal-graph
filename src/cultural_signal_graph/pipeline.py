"""The forecast pipeline: batch `run` + LangGraph orchestration with a HITL gate.

`run` is the plain, deterministic batch path (no interrupt); un-decided cross-domain
edges stay "proposed". `build_forecast_graph` compiles the LangGraph pipeline whose
gate node interrupts for sign-off (ADR-0001). The graph's checkpointed state is
JSON-native (dicts, not dataclasses); the deterministic plumbing (graph construction,
flags, brief) runs in `forecast_run_from_state` after the interrupt resolves.
"""

from __future__ import annotations

from typing import Any, Callable, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .alignment import align
from .brief import assemble
from .draft import draft
from .extraction import extract
from .flags import detect_flags, resolve_edges
from .graph import build_graph
from .tracing import get_tracer
from .models import (
    EquivalenceEdge,
    Extraction,
    ForecastRun,
    SourceDoc,
    edge_from_dict,
    edge_to_dict,
    extraction_from_dict,
    extraction_to_dict,
    source_doc_from_dict,
    source_doc_to_dict,
)

AS_OF = "2026-09-08"


def _finalize(
    extraction: Extraction,
    edges: list[EquivalenceEdge],
    decisions: dict[str, bool],
    corpus: list[SourceDoc],
    category: str,
    reasoning: dict[str, str],
    extra_ontology: Any = None,
) -> ForecastRun:
    """Deterministic plumbing: build the graph, flag conflicts, assemble the brief."""
    with get_tracer().start_as_current_span("finalize") as span:
        graph = build_graph(extraction, edges, decisions, corpus, extra_ontology)
        flags = detect_flags(extraction.signals)
        gated_edges = resolve_edges(edges, decisions, extraction.entities)
        brief = assemble(extraction, corpus, flags, gated_edges, reasoning, category, as_of=AS_OF)
        span.set_attribute("output.claims", len(brief.claims))
        span.set_attribute("output.flags", len(brief.flags))
        return ForecastRun(
            graph=graph,
            brief=brief,
            flags=flags,
            gated_edges=gated_edges,
            extraction=extraction,
            edges=edges,
        )


def run(
    corpus: list[SourceDoc],
    category: str = "tech",
    extract_fn: Callable[[list[SourceDoc]], Extraction] = extract,
    align_fn: Callable[[Extraction], list[EquivalenceEdge]] = align,
    draft_fn: Callable[[Extraction, str], dict[str, str]] = draft,
    decisions: dict[str, bool] | None = None,
    extra_ontology: Any = None,
) -> ForecastRun:
    """Run the pipeline without the HITL interrupt. Un-decided edges stay
    "proposed"; `decisions` pre-supplies approve/reject outcomes."""
    with get_tracer().start_as_current_span("forecast") as span:
        span.set_attribute("category", category)
        decisions = decisions or {}
        extraction = extract_fn(corpus)
        edges = align_fn(extraction)
        reasoning = draft_fn(extraction, category)
        return _finalize(extraction, edges, decisions, corpus, category, reasoning, extra_ontology)


class ForecastState(TypedDict, total=False):
    corpus: list[dict]
    category: str
    extraction: dict
    edges: list[dict]
    decisions: dict[str, bool]
    reasoning: dict[str, str]


def initial_state(corpus: list[SourceDoc], category: str) -> dict:
    """Build the JSON-native initial state for a LangGraph run."""
    return {"corpus": [source_doc_to_dict(s) for s in corpus], "category": category}


def build_forecast_graph(
    extract_fn: Callable[[list[SourceDoc]], Extraction] = extract,
    align_fn: Callable[[Extraction], list[EquivalenceEdge]] = align,
    draft_fn: Callable[[Extraction, str], dict[str, str]] = draft,
):
    """Compile the LangGraph pipeline; the gate node interrupts for sign-off."""

    def extract_node(state: ForecastState) -> dict:
        corpus = [source_doc_from_dict(d) for d in state["corpus"]]
        return {"extraction": extraction_to_dict(extract_fn(corpus))}

    def align_node(state: ForecastState) -> dict:
        extraction = extraction_from_dict(state["extraction"])
        return {"edges": [edge_to_dict(e) for e in align_fn(extraction)]}

    def gate_node(state: ForecastState) -> dict:
        with get_tracer().start_as_current_span("gate") as span:
            edges = state.get("edges", [])
            span.set_attribute("input.edges", len(edges))
            if not edges:
                return {"decisions": {}}
            payload = [
                {
                    "id": edge["id"],
                    "left_entity_id": edge["left_entity_id"],
                    "right_entity_id": edge["right_entity_id"],
                    "confidence": edge["confidence"],
                }
                for edge in edges
            ]
            decisions = interrupt({"sign_off": payload})
            span.set_attribute("output.decisions", len(decisions))
            return {"decisions": decisions}

    def draft_node(state: ForecastState) -> dict:
        extraction = extraction_from_dict(state["extraction"])
        return {"reasoning": draft_fn(extraction, state["category"])}

    builder = StateGraph(ForecastState)
    builder.add_node("extract", extract_node)
    builder.add_node("align", align_node)
    builder.add_node("gate", gate_node)
    builder.add_node("draft", draft_node)
    builder.add_edge(START, "extract")
    builder.add_edge("extract", "align")
    builder.add_edge("align", "gate")
    builder.add_edge("gate", "draft")
    builder.add_edge("draft", END)
    return builder.compile(checkpointer=MemorySaver())


def forecast_run_from_state(state: ForecastState) -> ForecastRun:
    """Build a ForecastRun (incl. the RDF graph) from a finalized graph state."""
    extraction = extraction_from_dict(state["extraction"])
    edges = [edge_from_dict(e) for e in state["edges"]]
    decisions = state.get("decisions", {})
    corpus = [source_doc_from_dict(d) for d in state["corpus"]]
    return _finalize(
        extraction, edges, decisions, corpus, state["category"], state.get("reasoning", {})
    )
