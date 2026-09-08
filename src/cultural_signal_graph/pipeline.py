"""The thin end-to-end slice: corpus -> extraction -> graph -> flags -> brief.

A single deterministic `run` wires the real plumbing (graph construction, flag
and gate logic, brief assembly) around a stubbed extraction stage. No model
calls, no wall clock — the same corpus yields byte-identical output. Issue #5
will wrap this seam in a LangGraph graph with real HITL interrupts.
"""

from typing import Callable

from .brief import assemble
from .extraction import extract
from .flags import apply_gate, detect_flags
from .graph import build_graph
from .models import Extraction, ForecastRun, SourceDoc

AS_OF = "2026-09-08"


def run(
    corpus: list[SourceDoc],
    category: str = "tech",
    extract_fn: Callable[[list[SourceDoc]], Extraction] = extract,
) -> ForecastRun:
    """Run the pipeline end-to-end. `extract_fn` is injectable so tests can use a
    deterministic fixture instead of the live cheap-model call."""
    extraction = extract_fn(corpus)
    graph = build_graph(extraction, corpus)
    flags = detect_flags(extraction.signals)
    gated_edges = apply_gate(extraction)
    brief = assemble(extraction, corpus, flags, gated_edges, category, as_of=AS_OF)
    return ForecastRun(graph=graph, brief=brief, flags=flags, gated_edges=gated_edges)
