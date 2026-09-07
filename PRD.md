# Cultural Signal Graph — PRD

An agentic knowledge-graph system for cultural/trend forecasting. It is the **strategy/insight layer** of the agency workflow — distinct from Greenlight (pre-production/concepting) — whose differentiator is **auditable, provenance-bearing reasoning**, not prediction accuracy.

---

## Problem Statement

A strategist producing a trend forecast today cannot defend *why* they believe a trend is real. The incumbents — WGSN, Nielsen, Kantar, Talkwalker, Heuritech — deliver conclusions as black boxes: no exposed reasoning, no source provenance, no confidence per claim, and no record of the conflicting evidence they chose to ignore. The strategist is left to either trust the box or redo the research by hand. Cross-domain claims (a gaming trend driving a consumer-electronics adoption signal) are the most valuable and the most fragile, and they are exactly where overconfidence is most dangerous.

## Solution

The Cultural Signal Graph ingests signals from sources, extracts and classifies entities/events/signals, links them into a knowledge graph whose edges carry **confidence, temporal validity, and provenance**, and produces an **auditable forecast brief**. It never silently averages away conflict: low-confidence and contradictory signals are **flagged**, and cross-domain alignment edges **stop for human sign-off** before being treated as real.

The system is agentic and multi-stage, grounded in an ontology (thin upper ontology + per-domain sub-ontologies) and external sources (IAB, Schema.org, Wikidata, AIRO), and it is deliberately scoped to be **buildable solo** and **cheap to run**.

### The trust surface

The output is not "here is the trend" — it is "here is the trend, here is every source behind it, here is how confident we are, here is the window each claim was true, and here are the conflicts we found." A strategist can reproduce any conclusion back to its evidence. This is the product.

---

## Goals

- **Auditable reasoning**: every forecast claim traces to a source with confidence + temporal validity.
- **Flag, don't forecast**: conflicting / low-credibility signal is surfaced, not blended into a confident claim.
- **Human-gated cross-domain claims**: cross-domain alignment edges require sign-off.
- **Runtime category**: any category can be input; tech is only the v1 fixture.
- **Solo-buildable**: zero infrastructure beyond local files; a single developer can ship it.
- **Token-conscious**: cheap to run often (see Cost levers).
- **Observable**: every run traced end-to-end; reasoning quality scored by evals, not eyeballed.

## Non-Goals

- **Prediction accuracy** (measuring whether trends materialize) — explicitly out of scope.
- **Live continuous connectors / monitoring** (v2+).
- **Interactive graph explorer** (v2).
- **SEA multi-market** (later; v1 is single-category).
- **Slide-deck output** (`.pptx`) — v1 ships Markdown + JSON.
- **Live web-search backfill** — the mechanism is architected but stubbed in v1.

---

## User Stories

1. As a strategist, I want to start a forecast by entering a category, a question/hypothesis, and a time window, so that I don't need to know how the system works internally.
2. As a strategist, I want to enter a category the system has never seen before, so that I'm not limited to a predefined list of domains.
3. As a strategist, I want the system to select and pull sources relevant to my ask — including ones I didn't know existed — so that I don't maintain a source list myself.
4. As a strategist, I want to inject my own curated signals or URLs, so that I can steer the system toward sources I trust.
5. As a strategist, I want every extracted entity/event/signal to carry its source and a confidence score, so that I can tell how much to trust each piece.
6. As a strategist, I want conflicting or low-credibility signals flagged rather than silently averaged in, so that the forecast does not overclaim.
7. As a strategist, I want to see the temporal validity of each claim, so that I don't treat stale evidence as current.
8. As a strategist, I want a proposed cross-domain link to stop and ask me before it's treated as real, so that shaky cross-domain inferences don't slip through.
9. As a strategist, I want to approve or reject a proposed cross-domain equivalence edge, so that I control what the system treats as established.
10. As a strategist, I want the forecast brief to include the full reasoning chain behind each claim, so that I can audit why the system concluded what it did.
11. As a strategist, I want the brief as both Markdown and structured JSON, so that I can read it and downstream tooling can consume it.
12. As a strategist, I want the brief to surface the conflicts and weak signals it excluded, so that I see what the system is *not* confident about.
13. As a strategist, I want to approve the brief before it ships to a client, so that nothing client-facing goes out unreviewed.
14. As a strategist, I want to reproduce any conclusion back to its sources and reasoning, so that I can defend the forecast to a client.
15. As a strategist, I want to run a "catch" scenario where I deliberately feed conflicting/low-credibility signal and watch the system flag instead of forecast, so that I can trust its skepticism.
16. As a strategist, I want a "cross-domain overconfidence" scenario where a shaky cross-domain link is proposed and gated, so that I can trust the human-review gate.
17. As an operator, I want the system to prefer free, high-quality sources by default, so that running it doesn't incur paid API costs.
18. As an operator, I want the system to minimize token usage, so that forecast runs stay cheap enough to use often.
19. As an operator, I want state persisted to files so I can stop and resume without rebuilding the graph, so that long runs are resumable.
20. As a strategist, I want an unfamiliar category to auto-seed its sub-ontology from grounding sources, so that I can forecast in a domain without an ontology engineer.
21. As a strategist, I want the system's reasoning to be reproducible — same inputs produce the same graph and flags — so that the audit trail is trustworthy.
22. As a strategist, I want to replay any forecast run and see every agent step, model call, token count, and latency, so that I can audit *how* a conclusion was reached, not just what it says.
23. As an operator, I want every run traced end-to-end with no gaps, so that a silent failure or a skipped gate is visible rather than invisible.
24. As an operator, I want to see token usage and latency per stage, so that I can find and fix the expensive parts of the pipeline.
25. As an operator, I want a golden eval set that scores flag-recall, provenance coverage, and alignment correctness, so that I can detect regressions when I change a prompt or model.
26. As an operator, I want to compare two runs (e.g. before/after a prompt change) side by side, so that I can tell whether the change improved reasoning or just moved noise around.

---

## Implementation Decisions

**Orchestration — LangGraph** (ADR-0001). Graph-native state machine; checkpointing/persistence and human-in-the-loop interrupts implement the HITL gates directly.

**Graph storage — RDFLib + files** (ADR-0002). In-memory RDF, persisted as Turtle/JSON-LD. SHACL validation via `pyshacl`. No graph database in v1.

**Category is a runtime input** (ADR-0003). Tech is the hand-authored v1 fixture; unfamiliar categories auto-seed.

**Source discovery is context-dependent** (ADR-0004). Known index first, live web backfill stubbed in v1.

**Ontology retrieval is hybrid** (ADR-0005). Embedding-first, LLM-on-miss, SHACL-validated; embeddings cached once.

**Observability & evals — OpenTelemetry + Langfuse** (ADR-0006). OTel instrumentation (one span per agent stage and per model/tool call) exports to a self-hosted Langfuse for the monitoring UI and eval workflow. Traces are the process-level audit trail.

**Ontology model.** Federated: thin upper ontology (Entity, Event, Signal, Source, Relationship, Confidence, Timestamp) + domain sub-ontologies. Edges carry temporal + confidence semantics (validity windows, decay). Provenance is first-class (edge attributes or its own node). A crosswalk layer holds confidence-scored equivalence edges between sub-ontologies.

**External grounding.**
- **IAB Tech Lab Content/Audience Taxonomy** — advertising-native category grounding.
- **Schema.org** — general entity backbone (Event, Product, CreativeWork, Organization).
- **Wikidata** — cross-domain entity resolution.
- **AIRO** (AI Risk Ontology, ISO 31000/23894) — the confidence/provenance/governance layer.

**Multi-agent pipeline.** Extraction/classification → graph construction → alignment → reasoning/forecast-drafting, plus a context-dependent **source-discovery** step. Framework: LangGraph. Protocol awareness: **MCP** for tool access; **A2A** only if a cross-system handshake becomes necessary (not v1).

**HITL gates — split by tier.** Single-domain low-confidence/conflicting signal → **flagged** (async, surfaced in the brief). Cross-domain alignment edge → **blocking sign-off** (LangGraph interrupt) before being treated as real.

**Model routing — two tiers.** Cheap model for extraction/classification; premium model for alignment judgment and forecast drafting. Specific model IDs pinned at build time.

**Sub-ontology seeding — hybrid.** Tech hand-authored; unfamiliar categories auto-seeded from IAB + Schema.org + Wikidata, SHACL-validated.

**Cost levers.** N-hop subgraph retrieval (no full-graph load); cached ontology/taxonomy embeddings; cheap/premium model routing; structured JSON over prose; incremental delta updates (no full rebuilds); prompt caching for static schema/system instructions; state externalized to files.

---

## Testing Decisions

Test **external behavior, not implementation** — through the pipeline's JSON seams, not agent internals. Prefer the highest seam: given an input corpus, assert the observable flags and brief; don't reach into individual agents.

- **Seams.** The pipeline is a sequence of JSON interfaces: corpus → extracted signals → graph → flags → brief. Test at the highest seam where possible (corpus → brief/flags).
- **Provenance completeness.** Every claim in the brief carries ≥1 source with confidence + temporal validity. A test asserts no claim is emitted without a provenance trail.
- **Flag recall (the "catch").** Plant conflicting/low-credibility signals in a corpus; assert they surface as flags and are *not* emitted as confident trends.
- **Cross-domain gating.** A low-confidence proposed equivalence edge is *not* promoted to "real" until sign-off; assert the interrupt fires.
- **Source discovery.** Given an ask, the system selects contextually relevant sources from the index and does not require the operator to enumerate them.
- **Reproducibility.** Same corpus → same graph and flags (deterministic given fixed model temperature/seed).

**Unit tests vs. evals.** Unit tests assert behavior at the JSON seams; evals score *reasoning quality* against the golden set (see Evals & Observability). They are complementary, not interchangeable — both gate a change before it ships.

**Prior art.** Greenfield — no existing test suite. Introduce `pytest` for the Python core (graph construction, SHACL, HITL gating, brief assembly); the agent stages are tested at their JSON seams with recorded fixtures rather than live model calls.

---

## Evals & Observability

Traces are the *process-level* audit trail; the graph's provenance is the *result-level* trail. Both are required for "reproduce any conclusion," which is the product.

**Tracing — OpenTelemetry.** Every forecast run emits a trace: one span per agent stage (source discovery, extraction/classification, graph construction, alignment, HITL, drafting) and one per model/tool call, each recording inputs/outputs, token counts, and latency. OTel keeps instrumentation vendor-neutral. Traces export to a self-hosted **Langfuse**, which provides the monitoring UI and hosts the eval workflow. (Alternatives: Arize Phoenix for OTel-native/pip-only; LangSmith for first-party LangGraph DX at cloud cost.)

**Evals — golden set + scored metrics.** A held-out corpus of signals with known-expected outcomes scores each run. The two demos are formal eval cases, not scripts.

| Metric | Scores |
|---|---|
| Flag recall / precision | conflicting & low-credibility signal flagged — neither missed nor over-flagged |
| Provenance coverage | % of brief claims with source + confidence + temporal validity |
| Extraction precision / recall | entities, events, signals extracted vs. golden |
| Alignment correctness | cross-domain equivalence edges vs. golden |
| Faithfulness | brief claims supported by the graph, not hallucinated |
| Gate correctness | cross-domain edges blocked until sign-off |
| Cost / latency | tokens + ms per stage |

Evals run as a **regression gate** on every prompt/model change — a change doesn't ship unless the golden-set scores hold.

---

## Success Metrics (governance-first)

"v1 works" means:

- **Provenance coverage** (scored eval): 100% of brief claims trace to ≥1 source with confidence + temporal validity.
- **Flag recall** (scored eval): planted conflicting/low-credibility signals are surfaced as flags, neither missed nor over-flagged.
- **Gate correctness**: no cross-domain edge is promoted without sign-off.
- **Faithfulness** (scored eval): every brief claim is supported by graph evidence.
- **Reproducibility**: a human can reproduce any conclusion from the graph — and from its trace.
- **Trace coverage**: 100% of runs produce a complete, gap-free trace, viewable in Langfuse.
- **Cost**: a single run stays under a token budget that makes weekly use trivial.

Forecast **accuracy is a non-goal** for v1 (needs labeled outcomes + months of lag, and contradicts the positioning). It may be tracked later as soft telemetry.

---

## Out of Scope (v1)

- Live continuous connectors / monitoring (v2+).
- Interactive graph explorer (v2).
- Live web-search backfill — stubbed, not enabled (v2).
- Second-category auto-seed proof beyond tech — mechanism built, not yet exercised on a real unfamiliar domain (v2).
- SEA multi-market (later).
- Slide-deck (`.pptx`) output.
- Prediction-accuracy measurement.

---

## Further Notes

### Demo scenarios (the differentiator, made concrete — and formal eval cases)

1. **The "catch" demo.** Feed a corpus asserting a tech trend (e.g. "AI wearables are the next must-have") where one viral-but-low-credibility social post claims it, commerce/search sources don't corroborate, and two sources actively conflict. Expected: the system scores confidence low, flags the conflict, and the brief says *insufficient corroboration* rather than a confident trend. This is the "flag recall" eval case.

2. **The "cross-domain overconfidence" demo.** Feed signals that tempt a cross-domain leap (e.g. a spike in gaming-community chatter about a peripheral loosely linked to a consumer-electronics adoption claim). Expected: the alignment agent proposes a low-confidence cross-domain edge, the HITL gate blocks and asks for sign-off, and the strategist sees the shaky link surfaced — not auto-accepted. This is the "gate correctness" eval case.

### Build order (for `to-tickets` later)

1. Bootstrap repo (Python + `uv` + `pytest`; `CONTEXT.md` and ADRs already present).
2. Upper ontology + hand-authored tech sub-ontology, with SHACL shapes.
3. Extraction/classification agent (cheap model) over a seed corpus → Signal/Entity/Event JSON.
4. Graph construction (RDFLib) with confidence + temporal + provenance.
5. HITL gates (LangGraph interrupt for cross-domain; flag for single-domain).
6. Source discovery (known index + context-dependent selection).
7. OTel instrumentation + Langfuse; golden eval set + scoring harness.
8. Reasoning/forecast-drafting (premium model) → brief (Markdown + JSON).
9. Wire the two demo scenarios as eval cases.
10. (v2) live backfill, explorer, second-category auto-seed.

### Planning methodology

This PRD is an **alignment artifact, not a build target** (Pocock's model): ontology and governance decisions were made through exploration first and formalized here. **OpenSpec** is scoped to the ontology-definition phase, using its custom-schema feature for ADR-style decision records. Between phases, externalize state to files and use `/clear` rather than `/compact`.
