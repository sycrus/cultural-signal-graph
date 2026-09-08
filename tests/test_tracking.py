"""Issue #17 acceptance tests for prediction-accuracy tracking."""

from cultural_signal_graph.fixtures import ALIGNED_EDGES, DRAFTED_REASONING, EXTRACTED, SEED_CORPUS
from cultural_signal_graph.pipeline import run
from cultural_signal_graph.tracking import mark_materialized, record_trends, report_accuracy


def _forecast():
    return run(
        SEED_CORPUS,
        category="tech",
        extract_fn=lambda _: EXTRACTED,
        align_fn=lambda _: ALIGNED_EDGES,
        draft_fn=lambda extraction, category: DRAFTED_REASONING,
    )


def test_prediction_accuracy_tracking(tmp_path):
    path = tmp_path / "trends.json"
    record_trends(_forecast(), path)
    assert report_accuracy(path)["trends_total"] == 2  # two confident claims

    mark_materialized("claim-1", True, path)
    mark_materialized("claim-2", False, path)
    report = report_accuracy(path)
    assert report["checked"] == 2
    assert report["materialized"] == 1
    assert report["accuracy"] == 0.5


def test_accuracy_is_reported_not_gated():
    # accuracy is a standalone report; it is not part of the eval correctness metrics.
    from cultural_signal_graph.eval import evaluate

    forecast = _forecast()
    from cultural_signal_graph.golden import SEED_CASE

    metrics = evaluate(forecast, SEED_CASE)
    assert "accuracy" not in metrics
