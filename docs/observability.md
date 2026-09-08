# Observability (OTel + Langfuse)

Every forecast run emits an OpenTelemetry trace: one span per agent stage
(`extract`, `align`, `gate`, `draft`, `finalize`) and one `model_call` span per
DeepSeek call, each recording model, token usage, and latency (span duration).
Traces are the process-level audit trail (ADR-0006), complementary to the RDF
graph's result-level provenance.

## How it works

- `src/cultural_signal_graph/tracing.py` installs the global `TracerProvider`.
- Stage functions open spans directly; model spans use GenAI semantic conventions
  (`gen_ai.request.model`, `gen_ai.usage.*_tokens`), which Langfuse maps to its
  native model/token fields.
- Tracing is a **no-op** unless enabled: `init_tracing_from_env()` (called by the CLI)
  installs an OTLP HTTP exporter only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set.

## Run Langfuse (self-hosted)

```bash
docker compose up -d
```

Open http://localhost:3000, create a project, and generate an API key pair
(public key + secret key).

## Export traces to Langfuse

Langfuse ingests OTLP over HTTP at `http://localhost:3000/api/public/otel` with
Basic auth (`public_key:secret_key`):

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:3000/api/public/otel"
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic $(printf '%s:%s' 'pk-lf-...' 'sk-lf-...' | base64)"
DEEPSEEK_API_KEY=... python -m cultural_signal_graph
```

Then view the trace in the Langfuse UI (Tracing tab).

## Tests

`tests/test_tracing.py` verifies trace completeness and per-span attributes using
an in-memory exporter — no Langfuse or network required.
