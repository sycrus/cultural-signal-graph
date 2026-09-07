# Cultural Signal Graph

An agentic knowledge-graph system for cultural/trend forecasting. It extracts signals from sources, links them into a provenance-bearing graph, and produces auditable forecast briefs that a human strategist signs off before they reach a client.

## Language

### Graph model

**Entity**:
A thing in the world that can trend: a product, brand, person, concept, or event.
_Avoid_: node, object, item

**Event**:
Something that happens at a point or interval in time and can drive signal — a product launch, a viral moment.
_Avoid_: occurrence, incident

**Signal**:
An observed piece of evidence that something is emerging — a search spike, a post, a sales jump.
_Avoid_: data point, mention, hit

**Source**:
Where a signal came from — a publication, platform, or API. Carries its own credibility score.
_Avoid_: feed, channel, origin

**Relationship**:
A typed connection between entities, events, or signals — an edge in the graph.
_Avoid_: link, association

**Confidence**:
A 0–1 score on a node or edge expressing how much we trust it. It is not a calibrated probability.
_Avoid_: probability, likelihood, certainty

**Temporal validity**:
The window during which an edge's claim holds, plus how its trust decays outside that window.
_Avoid_: freshness, recency

**Provenance**:
The first-class trace of where a claim came from and every step it passed through. Modeled on the edge itself, not bolted on.
_Avoid_: metadata, attribution

### Ontology

**Upper ontology**:
The thin shared schema — Entity, Event, Signal, Source, Relationship, Confidence, Timestamp — that every domain inherits.
_Avoid_: core schema, meta-model

**Sub-ontology**:
A domain-specific schema (tech, fashion, food, entertainment) that extends the upper ontology.
_Avoid_: domain model, vertical schema

**Crosswalk**:
The layer of confidence-scored equivalence edges connecting sub-ontologies.
_Avoid_: mapping layer, bridge

**Equivalence edge**:
An edge asserting two entities from different sub-ontologies mean the same thing, carrying its own confidence.
_Avoid_: match, dedup link

**Alignment**:
The process of discovering and creating equivalence edges across sub-ontologies.
_Avoid_: crosswalk (that is the resulting layer, not the process)

### Governance

**HITL gate**:
A point where the system stops for human judgment before a claim can proceed.
_Avoid_: approval step, checkpoint

**Flagged signal**:
A single-domain signal marked low-confidence or conflicting, surfaced in the brief but not blocking.
_Avoid_: warning, alert

**Sign-off**:
The human approval that turns a proposed cross-domain equivalence edge into a real one.

### Workflow

**Category**:
The runtime input that selects which sub-ontology to reason over. Tech is the v1 fixture, not a constant.
_Avoid_: vertical, domain (ambiguous)

**Forecast brief**:
The output artifact — a Markdown + JSON trend forecast with full provenance and surfaced conflicts.
_Avoid_: report, deck

**Trend**:
An emerging pattern with momentum, backed by multiple corroborating signals — not a single mention.
_Avoid_: fad, hype

**Source discovery**:
The context-dependent step that selects and pulls the sources relevant to the current ask, preferring free, high-quality ones.
_Avoid_: ingestion, connector

### Observability

**Trace**:
The end-to-end record of one forecast run — every agent step, model call, token count, and latency. The process-level half of the audit trail.
_Avoid_: log, history

**Span**:
One step inside a trace — a single agent invocation or model call, with its own inputs, outputs, and timing.
_Avoid_: step, record

**Eval**:
A scored check against a golden set that measures whether the reasoning is correct (flag recall, provenance coverage, faithfulness). Distinct from a unit test, which checks behavior.
_Avoid_: test, benchmark

**Golden set**:
A held-out corpus of signals with known-expected outcomes, used to score evals and catch regressions when prompts or models change.
_Avoid_: fixture, test data
