"""Issue #6 acceptance tests for the drafting stage (premium model)."""

import logging

from cultural_signal_graph import draft as dr
from cultural_signal_graph.fixtures import (
    DRAFTED_REASONING,
    EXTRACTED,
    RECORDED_DRAFT_OUTPUT,
)
from cultural_signal_graph.models import Usage


def test_parse_draft_matches_golden():
    assert dr.parse_draft(RECORDED_DRAFT_OUTPUT) == DRAFTED_REASONING


def test_draft_calls_model_and_logs_tokens(caplog, monkeypatch):
    fake_usage = Usage(
        model=dr.DRAFTING_MODEL,
        input_tokens=40,
        output_tokens=50,
        total_tokens=90,
    )

    def fake_call(signals, category):
        return RECORDED_DRAFT_OUTPUT, fake_usage

    monkeypatch.setattr(dr, "_call_draft_model", fake_call)

    with caplog.at_level(logging.INFO, logger="cultural_signal_graph.draft"):
        result = dr.draft(EXTRACTED, "tech")

    assert result == DRAFTED_REASONING
    assert any("total_tokens=90" in record.message for record in caplog.records)
