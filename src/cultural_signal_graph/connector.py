"""Live connectors — poll sources and incrementally update the graph (issue #13).

Instead of a full batch rebuild, a connector re-runs extraction on a schedule, diffs the
new signals against the ones already in the graph, merges only those, and re-runs flag
detection so a changed signal re-triggers flags/gates.
"""

from __future__ import annotations

import time

from .flags import detect_flags
from .graph import add_signal, add_source
from .models import Extraction, Flag, Signal, SourceDoc


def new_signals(extraction: Extraction, known_signal_ids: set[str]) -> list[Signal]:
    """Signals in `extraction` that aren't already in the graph."""
    return [s for s in extraction.signals if s.id not in known_signal_ids]


def merge_new_signals(
    graph, extraction: Extraction, known_signal_ids: set[str], sources: list[SourceDoc]
) -> int:
    """Add only the new signals to the graph (sources are idempotent). Returns count."""
    added = 0
    for signal in new_signals(extraction, known_signal_ids):
        add_signal(graph, signal)
        added += 1
    for source in sources:
        add_source(graph, source)
    return added


def recompute_flags(signals: list[Signal]) -> list[Flag]:
    """Re-run flag detection over the current signal set (re-triggers on change)."""
    return detect_flags(signals)


def poll(corpus: list[SourceDoc], extract_fn, known_signal_ids: set[str]):
    """One poll: re-extract and return the new signals plus the extraction."""
    extraction = extract_fn(corpus)
    return new_signals(extraction, known_signal_ids), extraction


def run_polling(corpus, extract_fn, interval: float = 60.0):
    """Poll on a schedule, yielding new signals each cycle. Infinite; stop the caller."""
    known: set[str] = set()
    while True:
        extraction = extract_fn(corpus)
        fresh = new_signals(extraction, known)
        known.update(s.id for s in extraction.signals)
        yield fresh
        time.sleep(interval)
