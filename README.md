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

The provider is **DeepSeek**, called through its Anthropic-compatible endpoint
(`https://api.deepseek.com/anthropic`): `deepseek-v4-flash` for the cheap tier, `deepseek-v4-pro`
for the premium tier.

## The web app

The pipeline as a guided workflow. The run *pauses* mid-flight — nothing proceeds
until the strategist signs off, which is the moment the product adds judgment.

```
Ask  →  Sources  →  Run  →  ⛔ Sign-off  →  Brief  →  Graph / Metrics
```

- **Ask** — category, question, window, optional market; source discovery selects
  the sources (index, or live backfill for an unfamiliar category).
- **Sources** — collapsed by default, auditable; add, remove, or reset before
  extraction runs. Sources lock once the run starts.
- **Run** — each stage reports its tokens + latency, recorded at the stage boundary.
- **Sign-off** — the run stops at the gate; approve or reject each proposed
  cross-domain equivalence edge (approve → "real", reject → dropped). The decision
  stays editable until export: undo re-parks the run at the gate, and the downstream
  re-runs.
- **Brief** — claims as headlines with confidence, expandable reasoning and sources,
  flagged signals, gated edges with their resolved status; the artifacts download.
- **Graph** — the embedded explorer (search, layout controls, click-to-trace) with a
  notes overlay: annotate any node or edge (author + timestamp). An overlay only —
  it never affects reasoning or provenance.
- **Metrics** — cost (tokens, per-stage latency), eval scores against the golden
  case, and prediction accuracy (soft, lagging telemetry — reported, never gating).
- **Reopen** — past runs reload from `runs/`; jump to any completed stage.

Without `DEEPSEEK_API_KEY`, the app runs in **fixture mode** (badge in the header):
the recorded demo outputs on the pinned seed corpus, no model calls — the whole
loop is explorable offline.

## Outputs

A batch run writes six files into `out/`:

| File | What it is |
|---|---|
| `brief.md` | human-readable brief (claims, reasoning, conflicts, gated edges) |
| `brief.json` | the same, structured |
| `brief.pptx` | client-facing slide deck |
| `graph.html` | interactive graph explorer (search, layout controls, click-to-trace, offline) |
| `graph.ttl` | the RDF audit graph (confidence, temporal validity, provenance) |
| `usage.json` | token usage per model call |

A web-app run is a directory under `runs/` — reopening, re-deciding, and metrics
are file reads, never a database:

| File | What it is |
|---|---|
| `run.json` | the ask, sources, stage status with per-stage tokens/latency, sign-off state |
| `checkpoints.sqlite` | the LangGraph checkpoint — a paused run resumes across restarts |
| `state-pause.json` / `state-final.json` | the state at the gate / at finalize (undo, metrics, reopen) |
| `brief.md` … `usage.json` | the same six artifacts as the batch path, per run |
| `trends.json` | recorded trends, checked later for prediction accuracy |
| `notes.json` | the annotations overlay |

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
  static/        the stepper UI (app.js/app.css, vendored cytoscape.min.js)
  ontology/      upper.ttl, tech.ttl, gaming.ttl, shapes.ttl (SHACL)
```

## Testing

```bash
uv run pytest
```

85 tests, all fixture-based — no network or API key required. The eval harness
(`python -m cultural_signal_graph.eval_main`) runs the golden set and enforces the regression
gate.

## Docs

- **[PRD.md](PRD.md)** — the v1/v2 product spec.
- **[PRD-ui.md](PRD-ui.md)** — the UI (v3) spec: local web app, sign-off loop, layouts.
- **[CONTEXT.md](CONTEXT.md)** — the domain glossary (Entity, Signal, Source, Provenance, …).
- **[docs/adr/](docs/adr/)** — architecture decision records (LangGraph, RDFLib+files,
  category-as-input, source discovery, ontology retrieval, OTel+Langfuse).
- **[docs/observability.md](docs/observability.md)** — OTel + Langfuse setup.
