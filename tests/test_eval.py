"""Issue #8/#9 acceptance tests for the eval harness, golden set, and demo cases."""

from cultural_signal_graph.eval import check, evaluate
from cultural_signal_graph.fixtures import (
    ALIGNED_EDGES,
    DRAFTED_REASONING,
    EXTRACTED,
)
from cultural_signal_graph.golden import (
    CATCH_CASE,
    CROSS_DOMAIN_CASE,
    EVAL_CASES,
    SEED_CASE,
)
from cultural_signal_graph.pipeline import run


def _run(case):
    return run(
        case.corpus,
        category=case.category,
        extract_fn=lambda _: EXTRACTED,
        align_fn=lambda _: ALIGNED_EDGES,
        draft_fn=lambda extraction, category: DRAFTED_REASONING,
    )


def test_seed_case_scores_full_marks():
    metrics = evaluate(_run(SEED_CASE), SEED_CASE)
    assert check(metrics, SEED_CASE.thresholds) == []


def test_golden_set_has_known_outcomes_for_each_metric():
    assert SEED_CASE.expected_entity_ids
    assert SEED_CASE.expected_signal_ids
    assert SEED_CASE.expected_flag_ids
    assert SEED_CASE.expected_edge_ids
    assert SEED_CASE.gated_edge_ids


def test_regression_gate_blocks_on_missing_flag():
    forecast = _run(SEED_CASE)
    forecast.flags = []  # simulate a broken run that failed to surface the conflict
    metrics = evaluate(forecast, SEED_CASE)
    assert "flag_recall" in check(metrics, SEED_CASE.thresholds)


# --- Issue #9: demo scenarios as eval cases ---

def test_catch_flag_recall_passes():
    forecast = _run(CATCH_CASE)
    metrics = evaluate(forecast, CATCH_CASE)
    assert metrics["flag_recall"] == 1.0
    # the conflicting signal is flagged, not promoted to a confident claim
    claim_text = " ".join(c.statement for c in forecast.brief.claims)
    assert "passing fad" not in claim_text
    assert any(f.reason == "conflict" for f in forecast.brief.flags)


def test_cross_domain_gate_correctness_passes():
    forecast = _run(CROSS_DOMAIN_CASE)
    metrics = evaluate(forecast, CROSS_DOMAIN_CASE)
    assert metrics["gate_correctness"] == 1.0
    edge = forecast.brief.gated_edges[0]
    assert edge.status != "real"  # gated, not promoted


def test_all_demo_cases_pass_the_gate():
    for case in EVAL_CASES:
        metrics = evaluate(_run(case), case)
        assert check(metrics, case.thresholds) == [], f"{case.name} failed: {metrics}"
