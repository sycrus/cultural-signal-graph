"""Issue #7 acceptance tests for OpenTelemetry tracing."""

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from cultural_signal_graph import alignment as aln
from cultural_signal_graph import draft as dr
from cultural_signal_graph import extraction as ext
from cultural_signal_graph import tracing
from cultural_signal_graph.fixtures import (
    RECORDED_ALIGNMENT_OUTPUT,
    RECORDED_DRAFT_OUTPUT,
    RECORDED_MODEL_OUTPUT,
    SEED_CORPUS,
)
from cultural_signal_graph.models import Usage
from cultural_signal_graph.pipeline import run

# OTel forbids re-setting the global TracerProvider, so install it once here and
# clear the shared exporter at the start of each test.
_exporter = InMemorySpanExporter()
tracing.init_tracing(_exporter)


@pytest.fixture
def spans(monkeypatch):
    _exporter.clear()

    def fake_usage(model: str) -> Usage:
        return Usage(model=model, input_tokens=100, output_tokens=50, total_tokens=150)

    # Monkeypatch only the model seams; the real stage functions still run (and
    # emit spans), but no network and deterministic output.
    monkeypatch.setattr(
        ext, "_call_model", lambda corpus: (RECORDED_MODEL_OUTPUT, fake_usage(ext.EXTRACTION_MODEL))
    )
    monkeypatch.setattr(
        aln,
        "_call_alignment_model",
        lambda extraction: (RECORDED_ALIGNMENT_OUTPUT, fake_usage(aln.ALIGNMENT_MODEL)),
    )
    monkeypatch.setattr(
        dr,
        "_call_draft_model",
        lambda signals, category: (RECORDED_DRAFT_OUTPUT, fake_usage(dr.DRAFTING_MODEL)),
    )
    return _exporter


def test_batch_run_produces_complete_trace(spans):
    run(SEED_CORPUS, category="tech")
    finished = spans.get_finished_spans()
    names = {s.name for s in finished}

    assert {"forecast", "extract", "align", "draft", "finalize"} <= names

    model_spans = [s for s in finished if s.name == "model_call"]
    assert len(model_spans) == 3
    for model_span in model_spans:
        assert model_span.attributes["gen_ai.request.model"] in (
            "deepseek-v4-flash",
            "deepseek-v4-pro",
        )
        assert model_span.attributes["gen_ai.usage.input_tokens"] == 100
        assert model_span.attributes["gen_ai.usage.output_tokens"] == 50

    # Latency is the span's own duration: every span must have start and end time.
    for span in finished:
        assert span.start_time is not None
        assert span.end_time is not None


def test_langgraph_flow_produces_gate_span(spans):
    from langgraph.types import Command

    from cultural_signal_graph.pipeline import build_forecast_graph, initial_state

    graph = build_forecast_graph()
    config = {"configurable": {"thread_id": "gate-trace"}}
    result = graph.invoke(initial_state(SEED_CORPUS, "tech"), config)
    payload = result["__interrupt__"][0].value["sign_off"]
    graph.invoke(Command(resume={e["id"]: True for e in payload}), config)

    names = {s.name for s in spans.get_finished_spans()}
    assert {"extract", "align", "gate", "draft"} <= names


def test_cost_latency_is_computed_and_gated(spans):
    from cultural_signal_graph.eval import DEFAULT_COST_BUDGETS, check_cost, cost_latency
    from cultural_signal_graph.tracing import get_finished_spans

    run(SEED_CORPUS, category="tech")
    cost = cost_latency(get_finished_spans())
    assert cost["input_tokens"] == 300  # 3 model calls x 100
    assert cost["output_tokens"] == 150  # 3 model calls x 50
    assert cost["total_tokens"] == 450
    assert check_cost(cost, DEFAULT_COST_BUDGETS) == []  # within budget
    assert check_cost(cost, {"total_tokens": 100}) == ["total_tokens"]  # over budget


def test_run_captures_token_usage(spans):
    forecast = run(SEED_CORPUS, category="tech")
    assert len(forecast.usage) == 3  # extract + align + draft
    assert sum(u.total_tokens for u in forecast.usage) == 450


class _FakeMessages:
    def __init__(self, text):
        self.text = text
        self.kwargs = None

    def create(self, **kwargs):
        from types import SimpleNamespace

        self.kwargs = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.text)],
            usage=SimpleNamespace(input_tokens=12, output_tokens=7),
        )


def test_model_call_span_records_full_input_and_output(monkeypatch):
    """Issue #29: the model-call span carries the prompt that went in and the raw
    text that came out, not just token counts."""
    import json
    from types import SimpleNamespace

    from cultural_signal_graph import llm

    fake = _FakeMessages(RECORDED_MODEL_OUTPUT)
    monkeypatch.setattr(llm, "get_client", lambda: SimpleNamespace(messages=fake))
    _exporter.clear()

    ext.extract(SEED_CORPUS)

    (model_call,) = [s for s in _exporter.get_finished_spans() if s.name == "model_call"]
    recorded_input = json.loads(model_call.attributes["gen_ai.prompt"])
    assert recorded_input["system"] == fake.kwargs["system"]
    assert recorded_input["messages"] == fake.kwargs["messages"]
    assert SEED_CORPUS[0].uri in recorded_input["messages"][0]["content"]
    assert model_call.attributes["gen_ai.completion"] == RECORDED_MODEL_OUTPUT
    assert model_call.attributes["gen_ai.usage.input_tokens"] == 12
    assert model_call.attributes["gen_ai.request.model"] == ext.EXTRACTION_MODEL


def test_call_model_passes_temperature_only_when_set(monkeypatch):
    from types import SimpleNamespace

    from cultural_signal_graph import llm

    fake = _FakeMessages("[]")
    monkeypatch.setattr(llm, "get_client", lambda: SimpleNamespace(messages=fake))
    llm.call_model("m", "sys", "hi", max_tokens=10)
    assert "extra_body" not in fake.kwargs
    llm.call_model("m", "sys", "hi", max_tokens=10, temperature=0.9)
    assert fake.kwargs["extra_body"] == {"temperature": 0.9}
