"""Eval harness + golden-set scoring (issue #8).

Scores a forecast run against a golden eval case across the PRD's correctness metrics —
flag recall/precision, provenance coverage, extraction precision/recall, alignment
correctness, faithfulness, gate correctness — and enforces a regression gate. Cost and
latency are captured by the OTel traces (issue #7), not scored here: they have no fixed
"known-expected outcome", so they're a live-run measurement rather than a golden gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import ForecastRun, SourceDoc

# A metric at or below its threshold blocks a change (the regression gate).
DEFAULT_THRESHOLDS = {
    "flag_recall": 1.0,
    "flag_precision": 1.0,
    "provenance_coverage": 1.0,
    "extraction_precision": 1.0,
    "extraction_recall": 1.0,
    "alignment_correctness": 1.0,
    "faithfulness": 1.0,
    "gate_correctness": 1.0,
}


@dataclass(frozen=True)
class EvalCase:
    """A held-out corpus with known-expected outcomes."""

    name: str
    corpus: list[SourceDoc]
    category: str
    expected_entity_ids: frozenset[str]
    expected_signal_ids: frozenset[str]
    expected_flag_ids: frozenset[str]
    expected_edge_ids: frozenset[str]
    gated_edge_ids: frozenset[str]
    thresholds: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_THRESHOLDS))


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def flag_recall(forecast: ForecastRun, case: EvalCase) -> float:
    flagged = {f.signal_id for f in forecast.flags}
    return _ratio(len(flagged & case.expected_flag_ids), len(case.expected_flag_ids))


def flag_precision(forecast: ForecastRun, case: EvalCase) -> float:
    flagged = {f.signal_id for f in forecast.flags}
    return _ratio(len(flagged & case.expected_flag_ids), len(flagged))


def provenance_coverage(forecast: ForecastRun) -> float:
    claims = forecast.brief.claims
    if not claims:
        return 1.0
    covered = sum(1 for c in claims if c.sources and c.temporal_validity)
    return covered / len(claims)


def extraction_precision(forecast: ForecastRun, case: EvalCase) -> float:
    extracted = {e.id for e in forecast.extraction.entities}
    return _ratio(len(extracted & case.expected_entity_ids), len(extracted))


def extraction_recall(forecast: ForecastRun, case: EvalCase) -> float:
    extracted = {e.id for e in forecast.extraction.entities}
    return _ratio(len(extracted & case.expected_entity_ids), len(case.expected_entity_ids))


def alignment_correctness(forecast: ForecastRun, case: EvalCase) -> float:
    proposed = {e.id for e in forecast.edges}
    return _ratio(len(proposed & case.expected_edge_ids), len(case.expected_edge_ids))


def faithfulness(forecast: ForecastRun, case: EvalCase) -> float:
    corpus_uris = {s.uri for s in case.corpus}
    claims = forecast.brief.claims
    if not claims:
        return 1.0
    supported = sum(
        1 for c in claims if c.sources and all(src.uri in corpus_uris for src in c.sources)
    )
    return supported / len(claims)


def gate_correctness(forecast: ForecastRun, case: EvalCase) -> float:
    gated = {e.id for e in forecast.gated_edges if e.status != "real"}
    return _ratio(len(gated & case.gated_edge_ids), len(case.gated_edge_ids))


def evaluate(forecast: ForecastRun, case: EvalCase) -> dict[str, float]:
    """Score a run against a case, returning every correctness metric."""
    return {
        "flag_recall": flag_recall(forecast, case),
        "flag_precision": flag_precision(forecast, case),
        "provenance_coverage": provenance_coverage(forecast),
        "extraction_precision": extraction_precision(forecast, case),
        "extraction_recall": extraction_recall(forecast, case),
        "alignment_correctness": alignment_correctness(forecast, case),
        "faithfulness": faithfulness(forecast, case),
        "gate_correctness": gate_correctness(forecast, case),
    }


def check(metrics: dict[str, float], thresholds: dict[str, float]) -> list[str]:
    """Return the metrics that fall below threshold (the regression gate)."""
    return [
        metric
        for metric, threshold in thresholds.items()
        if metrics.get(metric, 0.0) < threshold
    ]
