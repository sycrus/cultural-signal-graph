"""OpenTelemetry tracing (ADR-0006).

One span per agent stage and per model call, recording tokens + latency, exported via
OTLP to a self-hosted Langfuse. `init_tracing(exporter)` installs the global provider —
pass an `InMemorySpanExporter` in tests, or an OTLP exporter in production.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from .models import Usage

SERVICE_NAME = "cultural-signal-graph"


def init_tracing(exporter=None) -> None:
    """Install the global TracerProvider; `exporter=None` leaves tracing a no-op."""
    provider = TracerProvider()
    if exporter is not None:
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def init_tracing_from_env() -> None:
    """Enable OTLP export when `OTEL_EXPORTER_OTLP_ENDPOINT` is set (e.g. Langfuse)."""
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        init_tracing(OTLPSpanExporter())


def get_tracer():
    return trace.get_tracer(SERVICE_NAME)


@contextmanager
def model_span():
    """A CLIENT span for one model call; set token/model attrs via `record_usage`."""
    with get_tracer().start_as_current_span("model_call", kind=trace.SpanKind.CLIENT) as span:
        span.set_attribute("gen_ai.system", "deepseek")
        yield span


def record_usage(span: trace.Span, usage: Usage) -> None:
    """Record GenAI token/model attributes on a model-call span."""
    span.set_attribute("gen_ai.request.model", usage.model)
    span.set_attribute("gen_ai.usage.input_tokens", usage.input_tokens)
    span.set_attribute("gen_ai.usage.output_tokens", usage.output_tokens)
    span.set_attribute("gen_ai.usage.total_tokens", usage.total_tokens)
