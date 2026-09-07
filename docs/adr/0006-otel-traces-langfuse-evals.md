# OpenTelemetry traces + Langfuse for observability and evals

Instrumentation uses OpenTelemetry so agent activity is vendor-neutral and the backend is swappable; traces export to a self-hosted Langfuse, which provides the monitoring UI and the eval workflow (datasets, scores, LLM-as-judge, prompt management). Traces are the process-level audit trail — alongside the graph's result-level provenance — which the governance thesis requires. v1 evals are a pytest golden set scoring flag recall, provenance coverage, extraction precision/recall, alignment correctness, faithfulness, gate correctness, and cost/latency, gated on every prompt/model change.

**Considered options:** Arize Phoenix (rejected — equally OTel-native and pip-installable, but weaker prompt-management/iteration UX); LangSmith (rejected — best LangGraph-native eval DX, but paid cloud and traces leave the machine, in tension with owning the audit trail); SigNoz/Jaeger (rejected — tracing/APM only, no eval workflow).
