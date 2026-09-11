# Cultural Signal Graph

An agentic knowledge-graph system for cultural/trend forecasting whose output is
**auditable, provenance-bearing reasoning**, not a black-box prediction.

It ingests signals from sources, extracts and classifies entities/events/signals, links them
into an RDF graph whose edges carry **confidence, temporal validity, and provenance**, and
produces a **forecast brief** a strategist can reproduce back to its evidence. It never
silently averages away conflict — low-confidence/contradictory signals are **flagged**, and
cross-domain alignment edges **stop for human sign-off**.

## The pipeline

```
sources → extract (deepseek-v4-flash) → align (deepseek-v4-pro) → ⛔ sign-off → draft (deepseek-v4-pro) → brief + graph
```

- **Source discovery** — select sources from a known index, or backfill from the live web
  (Wikipedia) for an unfamiliar category.
- **Extraction** (cheap model) — sources → typed entities + signals with confidence and
  temporal validity.
- **Alignment** (premium model) — propose cross-domain equivalence edges.
- **HITL gate** — a LangGraph `interrupt()` pauses the run for sign-off; approve → "real",
  reject → dropped.
- **Drafting** (premium model) — write a reasoning chain per claim (provenance stays
  structural, so claims can't fabricate a source).
- **Finalize** — build the RDF graph, flag conflicts, assemble the brief.

## Quick start

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync                      # install dependencies

cp .env.example .env         # then set DEEPSEEK_API_KEY=sk-...  (auto-loaded)

python -m cultural_signal_graph         # batch run: writes the six files into out/
python -m cultural_signal_graph.server  # UI: local web app, opens in the browser
```

Without `DEEPSEEK_API_KEY`, the web app runs in **fixture mode** — the recorded demo
outputs, no model calls — so the whole loop (ask → sources → run → sign-off → brief →
graph → metrics) is explorable offline.

The provider is **DeepSeek**, called through its Anthropic-compatible endpoint
(`https://api.deepseek.com/anthropic`): `deepseek-v4-flash` for the cheap tier, `deepseek-v4-pro`
for the premium tier.

## Outputs

A run writes six files into `out/`:

| File | What it is |
|---|---|
| `brief.md` | human-readable brief (claims, reasoning, conflicts, gated edges) |
| `brief.json` | the same, structured |
| `brief.pptx` | client-facing slide deck |
| `graph.html` | interactive graph explorer (search, layout controls, click-to-trace, offline) |
| `graph.ttl` | the RDF audit graph (confidence, temporal validity, provenance) |
| `usage.json` | token usage per model call |

## Layout

```
src/cultural_signal_graph/
  pipeline.py    run() batch path + build_forecast_graph() (LangGraph + HITL interrupt)
  discovery.py   known index + live backfill
  extraction.py  cheap-model extraction        alignment.py  premium-model edges
  draft.py       premium-model reasoning       seed.py       sub-ontology auto-seed
  graph.py       RDFLib graph construction     flags.py      flag + gate logic
  brief.py       brief assembly                slides.py     .pptx export
  viz.py         graph.html explorer           tracking.py   prediction-accuracy telemetry
  eval.py        eval harness + regression gate   golden.py  golden set
  tracing.py     OpenTelemetry spans           checkpoint.py  file-backed checkpoints
  llm.py         DeepSeek client + JSON/CURIE helpers
  server.py      local web app (FastAPI)       runstore.py  runs/ dir state machine
  ontology/      upper.ttl, tech.ttl, gaming.ttl, shapes.ttl (SHACL)
```

## Testing

```bash
uv run pytest
```

72 tests, all fixture-based — no network or API key required. The eval harness
(`python -m cultural_signal_graph.eval_main`) runs the golden set and enforces the regression
gate.

## Docs

- **[PRD.md](PRD.md)** — the v1/v2 product spec.
- **[PRD-ui.md](PRD-ui.md)** — the UI (v3) spec: local web app, sign-off loop, layouts.
- **[CONTEXT.md](CONTEXT.md)** — the domain glossary (Entity, Signal, Source, Provenance, …).
- **[docs/adr/](docs/adr/)** — architecture decision records (LangGraph, RDFLib+files,
  category-as-input, source discovery, ontology retrieval, OTel+Langfuse).
- **[docs/observability.md](docs/observability.md)** — OTel + Langfuse setup.
