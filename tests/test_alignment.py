"""Issue #5 acceptance tests for the alignment agent (premium model).

No live model calls — `_call_alignment_model` is monkeypatched and
`parse_alignment` is tested against the recorded fixture.
"""

import logging

from cultural_signal_graph import alignment as aln
from cultural_signal_graph.fixtures import (
    ALIGNED_EDGES,
    EXTRACTED,
    RECORDED_ALIGNMENT_OUTPUT,
)
from cultural_signal_graph.models import Usage


def test_parse_alignment_matches_golden():
    assert aln.parse_alignment(RECORDED_ALIGNMENT_OUTPUT) == ALIGNED_EDGES


def test_align_calls_model_and_logs_tokens(caplog, monkeypatch):
    fake_usage = Usage(
        model=aln.ALIGNMENT_MODEL,
        input_tokens=50,
        output_tokens=30,
        total_tokens=80,
    )

    def fake_call(extraction):
        return RECORDED_ALIGNMENT_OUTPUT, fake_usage

    monkeypatch.setattr(aln, "_call_alignment_model", fake_call)

    with caplog.at_level(logging.INFO, logger="cultural_signal_graph.alignment"):
        result = aln.align(EXTRACTED)

    assert result == ALIGNED_EDGES
    assert any("total_tokens=80" in record.message for record in caplog.records)


def test_parse_alignment_rejects_out_of_range_confidence():
    bad = RECORDED_ALIGNMENT_OUTPUT.replace("0.35", "1.5", 1)
    try:
        aln.parse_alignment(bad)
    except ValueError as exc:
        assert "confidence" in str(exc)
    else:
        raise AssertionError("expected ValueError for out-of-range confidence")
