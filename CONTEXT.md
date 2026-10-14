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

### Futures

**Exploration**:
One futures session on a forecast run: a goal, an initial state (selected anchors), a horizon, and a number of orders. A run can hold many.
_Avoid_: scenario (a Matrix quadrant's world), session

**Projection**:
A speculative future event in an exploration. Carries no confidence and no probability — only qualitative lens tags and its provenance (anchors, parents, the generating model call).
_Avoid_: prediction, future event (Event means something that actually happened), forecast

**Order**:
A projection's causal depth from the initial state (1st-, 2nd-, 3rd-order consequence). Not time: a 2nd-order consequence can land before a 1st-order one.
_Avoid_: level, generation, step

**Time window**:
The span of years a projection is expected to occur in, estimated by the generator and editable. Separate from order; a child can't start before its parent.
_Avoid_: date, timestamp, horizon (the exploration's overall limit)

**Baseline**:
The one projected, business-as-usual branch every exploration contains — the reference the alternatives are read against. Not a probability claim.
_Avoid_: probable future, default scenario

**Discontinuity**:
An anchored projection that breaks from trend, tagged as such. The generator includes at least one per order.
_Avoid_: wild card (that is human-added and unanchored), disruption

**Branch**:
One path through an exploration's projection DAG. Branches may converge on a shared projection.
_Avoid_: thread, scenario

**Fork**:
A strategist-initiated sibling branch, regenerated downstream from a chosen projection, optionally with a "what if" hint. The original branch is kept.
_Avoid_: variant, copy

**Anchor**:
A node an exploration or projection grows from. Evidence anchors are forecast nodes (signals, flagged signals, pending edges, claims); futures-scoped anchors are strategist references that never enter the forecast's evidence.
_Avoid_: seed, input, source (a Source is where evidence came from)

**Grounded assumption**:
A strategist-added projection backed by a futures-scoped reference (e.g. a news item, a government forecast or plan).
_Avoid_: hypothesis, manual node

**Wild card**:
A strategist-added projection with no reference. Allowed, tagged, greyed.
_Avoid_: outlier, black swan

**Promotion**:
Moving a futures-scoped reference into the forecast. Always creates a new forecast run; the original run is untouched.
_Avoid_: import, sync

**Lens**:
An organizing view over an exploration's projections — Wheel, Matrix, Cone, Horizons, PESTLE. A lens tags and arranges (the strategist can override any tag); it never creates projections directly, but may seed a constrained fork or write an annotation.
_Avoid_: framework (the method a lens is based on), mode, view

**Annotation**:
A lens-written synthesis over projections — e.g. a Matrix scenario narrative per quadrant. Has provenance; is not a projection; goes stale when its projections change.
_Avoid_: summary, note (a Note is a human overlay on the forecast graph)

**Scroll**:
The base view of an exploration: a horizontal branching timeline, present on the left, with a sliding visible window over orders.
_Avoid_: timeline (generic), canvas

**Operation log**:
The append-only record of every action on an exploration, including the full input and output of each model call. The exploration's source of truth: state is its replay, undo/redo move a cursor over it.
_Avoid_: history, event log, undo stack

**Stale**:
A projection whose anchor or ancestor was edited, deleted, or rejected after it was generated. Marked, never auto-regenerated.
_Avoid_: invalid, outdated
