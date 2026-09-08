"""Issue #3 acceptance tests: extraction against a recorded golden fixture.

No live model calls — `_call_model` is monkeypatched and `parse_extraction` is
tested directly against the recorded fixture.
"""

import logging

from cultural_signal_graph import extraction as ext
from cultural_signal_graph.fixtures import EXTRACTED, RECORDED_MODEL_OUTPUT, SEED_CORPUS
from cultural_signal_graph.models import Usage


def test_parse_extraction_matches_golden():
    """A recorded model response parses to the typed golden Extraction."""
    assert ext.parse_extraction(RECORDED_MODEL_OUTPUT) == EXTRACTED


def test_extract_calls_model_and_logs_tokens(caplog, monkeypatch):
    """extract() calls the model seam, returns typed JSON, and logs token usage."""
    fake_usage = Usage(
        model=ext.EXTRACTION_MODEL,
        input_tokens=120,
        output_tokens=80,
        total_tokens=200,
    )

    def fake_call(corpus):
        return RECORDED_MODEL_OUTPUT, fake_usage

    monkeypatch.setattr(ext, "_call_model", fake_call)

    with caplog.at_level(logging.INFO, logger="cultural_signal_graph.extraction"):
        result = ext.extract(SEED_CORPUS)

    assert result == EXTRACTED
    assert any("total_tokens=200" in record.message for record in caplog.records)


def test_parse_extraction_rejects_out_of_range_confidence():
    bad = RECORDED_MODEL_OUTPUT.replace("0.85", "1.5", 1)
    try:
        ext.parse_extraction(bad)
    except ValueError as exc:
        assert "confidence" in str(exc)
    else:
        raise AssertionError("expected ValueError for out-of-range confidence")


def test_parse_extraction_handles_markdown_fences():
    fenced = "```json\n" + RECORDED_MODEL_OUTPUT + "\n```"
    assert ext.parse_extraction(fenced) == EXTRACTED
