# Cultural Signal Graph — Futures (v4) PRD

The forecast side (v1–v3) answers *"what is emerging, and can I defend it?"* This PRD defines
**Futures mode**: a second mode in the same app that takes a forecast's evidence as its
starting point and explores **speculative futures** from it — branching, multi-order,
deliberately unprovable — using futures-thinking frameworks as interchangeable ways of
organizing the result.

Futures mode is **internal**: a thinking tool for strategy and insight, not a client
deliverable.

---

## Problem Statement

A forecast brief stops at the present: here is the trend, here is the evidence. The
strategist's next question is always *"so where could this go?"* — and today that thinking
happens in their head or on a whiteboard, disconnected from the evidence that prompted it.
Three things are missing:

1. **No way to project forward from evidence.** There's no structured way to ask "given these
   signals, what are the 1st-, 2nd-, 3rd-order consequences over ten years?" and keep the
   answer tied to the signals that seeded it.
2. **No way to hold several futures at once.** Real futures work is plural — branches,
   alternatives, convergences. A single narrative hides the forks that matter.
3. **No way to switch frameworks without redoing the work.** Futures Wheel, 2×2 scenario
   matrix, Futures Cone, Three Horizons, PESTLE — each is a different *lens* on the same
   speculation, but today each would mean starting over.

## Solution

**One generator, many lenses.** A single generator grows a branching timeline of
**projections** from a chosen initial state of evidence, order by order — in method terms, a
Futures Wheel (consequence chaining). Other futures-thinking frameworks are **lenses**:
organizing views over the same projections. The same projection sits in ring 2 of the Wheel,
the top-right quadrant of the Matrix, and the "plausible" class of the Cone. Nodes shift
between structures; the speculation underneath doesn't change.

Lenses never create projections *directly*. Two amendments keep them faithful to their
methods: a lens may **seed a constrained fork** (e.g. the Matrix asks the generator for a
branch conditioned on a quadrant's axis values), and a lens may write **annotations** (e.g. a
scenario narrative per quadrant) — syntheses with their own provenance that are not
projections.

**Order is not time.** A projection's *order* is its causal distance from the initial state
(a 2nd-order consequence can land in year one). Each projection separately carries its own
**time window**. The Wheel arranges by order; the Scroll arranges by time.

The base view is the **Scroll**: a horizontal branching timeline, present on the left, future
to the right, with a sliding visible window — the strategist unrolls the orders they want to
look at, like a handscroll.

### Epistemic stance

- **No probabilities.** Projections carry no confidence score and no likelihood. Lens tags are
  qualitative (order, quadrant, cone class, horizon band, PESTLE category).
- **Futures thinking sits outside the audit.** Only the *anchors* — the evidence a projection
  grows from — are audited. Projections themselves aren't claims about the world.
- **Provenance is still mandatory.** Projections are generated from other projections, so every
  one records the exact LLM inputs and output that produced it, its parents, and its anchors.
  You can always trace a projection back to the evidence (or the human assumption) it started
  from.
- **One-way by default.** Projections live in the same graph as evidence but never appear in
  the forecast brief, and never alter the forecast's evidence. The only way back is an explicit,
  recorded **promotion** (see below).

---

## User flow

```
Forecast run (extracted)  →  Futures  →  New exploration  →  Generate  →  Scroll / Lenses  →  Fork · Edit · Ground  →  Export
```

**1. Enter Futures mode** — from any forecast run that has passed **extraction**. Everything
extracted is available as an anchor: signals, flagged signals (shown with their flag),
proposed-but-unsigned cross-domain edges (tagged *pending*), and drafted claims if the run has
reached the brief.

**2. New exploration** — a form:

```
┌ New exploration ─────────────────────────────────┐
│ Goal       [ the direction of AR/VR wearables  ] │
│ Initial    [ 4 anchors selected  ▸ pick ]        │
│ Horizon    [ 10 ] years                          │
│ Orders     [ 5 ]   (causal depth)                │
│                              [ Generate → ]      │
└──────────────────────────────────────────────────┘
```

The anchor picker suggests anchors relevant to the goal (one cheap call); the strategist
confirms or edits. It shows the initial state's **PESTLE coverage** (e.g. "no Political or
Legal anchors") so gaps are visible before generating. A run can hold many explorations — same evidence, different goals or
initial states — each stored separately. "Duplicate with changes" starts a new exploration
from an existing one's settings.

**3. Generate** — the Scroll fills in **live, order by order**, with a **Stop** button. Each
order is one model call that decides how many projections to create (within a cap), gives each
a **time window**, and may link to an existing projection instead of duplicating it
(**convergence**). Generation stops at whichever limit comes first: orders (depth) or horizon
(time).

- **Baseline.** The generator always produces one **projected** branch — the business-as-usual
  extrapolation (Voros's "projected" future), tagged as such. Not a probability claim; the
  reference line the alternatives are read against.
- **Discontinuities.** Each order includes at least one *anchored* **discontinuity** — a break
  from trend, tagged — so the generator doesn't only extrapolate. Unanchored wild cards stay
  human-only.

**4. The Scroll**

```
 ◀ rolled ┃ PRESENT   │ 2027      2028      2029      2030      2031  ┃ rolled ▶
          ┃ ▪ signal ─┼──●¹ ─────────●² ─────────────●³               ┃
          ┃ ▪ claim  ─┼─────●¹ ──┬───────●² ──┐                      ┃
          ┃ ▪ edge(p) │ ●¹(proj.)└──●³ ───────┴──────●⁴ converge      ┃
          ┃ ◇ ref (fs)│ ═══ baseline ════════════════════════         ┃
 ═════════╩════[▓▓▓▓▓▓▓▓▓▓ visible years ▓▓▓▓]═══╩══════════════════  ← minimap
  orders: [1][2][3][ 4 ][ 5 ]  ← depth filter                 (¹²³ = order)
```

- **x = time.** The Present column holds anchors in evidence styling, plus any futures-scoped
  references (◇). Each projection sits at its own time window; its order is shown as a badge.
  Edges can span any distance. The baseline branch is drawn as a distinct reference line.
- **Timing rule.** A child can't start before its parent. A violation (from generation or an
  edit) shows a **timing-conflict** marker — not stale; the content is still valid.
- **y = layout** by default (crossing-minimized lane packing), or **swimlanes** when a
  categorical lens drives it (PESTLE first; see Lenses).
- **Visible range** is chosen by dragging two "rollers" on the minimap over **years**, plus an
  **order-depth filter** (e.g. show orders 1–3). Out-of-range projections are rolled up at the
  edges with a count. The handscroll metaphor governs the *transitions* — sliding windows —
  not the visual texture.
- **Detail panel** (one, on the right): statement, year span, origin, anchors, parents, the
  generating call's inputs and raw output, lens tags, and **Edit · Fork · Delete · Ground this**.

**5. Lenses** — switch the view; the projections stay the same.

| Lens | Organizes by | Tag source |
|---|---|---|
| **Wheel** (Glenn) | Rings = order (causal depth), around the initial state | Deterministic (order) |
| **Matrix (2×2)** (intuitive logics) | Two critical uncertainties → four quadrants; each branch's end state is placed | Axes: model proposes 3–4 candidates from **flagged/conflicting signals** and where branches diverge most; strategist picks two or edits. Placement: cheap-model classification |
| **Cone** (Voros) | **Nested** classes — projected ⊂ plausible ⊂ possible; *preposterous* for wild cards — with **preferable** as a separate overlay, judged relative to the exploration's goal. A projection's tag is its innermost class | Cheap-model classification; the baseline branch is *projected* by construction |
| **Three Horizons** (Sharpe) | **Role, not time distance:** sustains-H1 (dominant system), H2− (transition absorbed by H1), H2+ (transition bridging to H3), H3 (emergent pattern). View plots the three curves over the horizon; projections placed by role and time window. **Anchors are tagged too** — flagged/weak signals are candidate H3 "pockets of the future in the present" | Cheap-model classification |
| **PESTLE** | Political / Economic / Social / Technological / Legal / Environmental — **multi-label**: one *primary* (the dominant dimension; its lane) plus *secondary* chips. Applies to **anchors and projections** | Cheap-model classification |

- The model **tentatively organizes** on first open of a lens (one traced call, cached as
  tags). The strategist **overrides by dragging** a node to another quadrant / class / band /
  lane; the override is recorded with author + timestamp. Both stay visible.
- **Categorical lenses can drive the Scroll's y-axis** as swimlanes (PESTLE first; Horizons and
  Cone later the same way).
- Outside the Cone lens, projections whose cone class falls outside possible / plausible /
  preferable are **greyed out**.
- **Lenses can expose gaps** — e.g. an empty Matrix quadrant, or no Legal projections in
  PESTLE, offers *"no branch explores this — fork?"*.
- **Lenses can seed constrained forks.** The Matrix is axis-first in practice: the strategist
  can generate a branch **per quadrant** (or all four at once), each conditioned on that
  quadrant's axis values — so the method forces the worlds a trend-following generator
  wouldn't reach. Generation still goes through the one generator.
- **Lenses can write annotations.** The Matrix writes a short **scenario narrative** per
  quadrant — a synthesis of that world across its branches. An annotation is not a projection:
  it has provenance (its model call), is marked as a synthesis, and goes stale when its
  quadrant's projections change.

**6. Fork, edit, add**

- **Fork** from any projection → regenerate downstream as a **sibling branch** in the same
  exploration, optionally with a hint (*"what if the EU bans always-on cameras?"*). The
  original branch is kept.
- **Edit / delete** a projection → its descendants are marked **stale** (visibly), with
  "regenerate downstream" offered — never automatic.
- **Grounded assumption** — the strategist adds a projection with a chosen time window (its
  order follows from its parent, or 1 if attached directly to an anchor), backed by a
  **reference** (URL + excerpt — e.g. a news item, a government forecast or plan). The
  reference lands in the Present column as a **futures-scoped anchor**: distinct styling, never
  in the brief or the forecast's evidence. A cheap call summarizes it into a one-line statement
  the generator can use. A grounded assumption can be a fork root.
- **Wild card** — a strategist-added projection with *no* reference. Allowed, tagged, greyed.
  Can be a fork root; its descendants visibly trace to a human assumption, not to evidence.
- **Ground this** (agent) — on any projection or assumption, run model-guided discovery (news,
  government forecasts/plans) to find references that **support or contradict** it, and propose
  them as futures-scoped anchors. Bounded steps; traced like discovery.

**7. Promotion** — a futures-scoped anchor can be **promoted** into the forecast. Forecast
sources lock once a run starts, so promotion **creates a new forecast run**: same ask, the
original sources plus the promoted reference. The original run and its explorations are
untouched; the new run records the exploration and anchor it came from. The exploration
carries over to the new run, and the generator grows a **branch from the promoted anchor**,
which may converge with existing projections.

**8. History & export** — every action is undoable/redoable (see Operation log). Export saves
the exploration as files: `exploration.json` (projections, edges, tags, provenance),
`exploration.md` (a readable walk through branches by order), and the operation log. PNG of the
current lens view is a nice-to-have. No client-facing deck.

**Where projections appear elsewhere**

- **Graph tab** (forecast): hidden by default; a "show futures layer" toggle, in futures
  styling.
- **Brief** (md / json / pptx): **never.** The brief stays evidence-only — it's the artifact
  that promises every statement traces to a source.

---

## Goals

- **Speculation grounded in evidence:** every model-generated projection traces back, through
  its parents, to at least one anchor.
- **Plural futures:** branches, forks, and convergences are first-class, not a single narrative.
- **Frameworks as lenses:** switching framework rearranges, never regenerates.
- **Strategist judgment wins:** the model organizes tentatively; every tag and every node is
  overridable, and overrides are recorded.
- **Fully reversible:** undo/redo across generation, edits, forks, and retags — redo never
  re-calls the model.
- **Inspectable generation:** the exact inputs and output of every model call are viewable
  in-app, offline, without Langfuse.
- **Cheap:** cheap model by default; generation bounded by orders × per-order cap.

## Non-Goals

- Probabilities, likelihoods, or confidence on projections.
- Reasoning evals or accuracy scoring of futures (there is no ground truth).
- Client-facing output (deck, polished report). Internal only, for now.
- Projections in the forecast brief, or silently altering forecast evidence.
- Multi-user collaboration on an exploration.

---

## User Stories

1. As a strategist, I want to **start an exploration from a forecast run's extracted evidence**,
   so that my speculation begins from signals I can defend.
2. As a strategist, I want to **use flagged signals and pending cross-domain edges as anchors**,
   so that weak or contested evidence can still seed a possible future.
3. As a strategist, I want to **set a goal, horizon, and number of orders**, so that the
   exploration answers a question I care about at a timescale I choose.
4. As a strategist, I want **anchor suggestions for my goal** that I can accept or edit, so that
   I don't hand-pick from dozens of signals.
5. As a strategist, I want to **keep many explorations per run**, each with its own goal, so
   that I can explore different directions from the same evidence.
6. As a strategist, I want to **watch the timeline fill in order by order, and stop it**, so
   that I can cut a run that's going wrong.
7. As a strategist, I want to **see the whole branching timeline first**, so that I judge the
   overall shape before drilling in.
8. As a strategist, I want to **slide the visible window across years and filter by order**,
   so that I focus on the time range and causal depth that matter.
9. As a strategist, I want to **see where branches converge**, so that I spot outcomes reachable
   by many paths.
10. As a strategist, I want to **open any projection and see its anchors, parents, and the exact
    model input and output that produced it**, so that I know where an idea came from.
11. As a strategist, I want to **switch between Wheel, Matrix, Cone, Horizons, and PESTLE**
    without regenerating, so that I can look at the same futures through different frameworks.
12. As a strategist, I want **Matrix axes proposed from my forecast's conflicts**, so that
    critical uncertainties come from the evidence, not a blank page.
12a. As a strategist, I want to **generate a branch per Matrix quadrant and read a scenario
    narrative for each**, so that I inhabit all four worlds, not just the ones the trends point
    at.
12b. As a strategist, I want a **baseline branch** to compare alternatives against, so that
    "different" has a reference.
12c. As a strategist, I want **discontinuities** proposed alongside extrapolations, so that the
    exploration isn't just the trend continued.
13. As a strategist, I want to **drag a projection to a different quadrant / class / band /
    lane**, so that my judgment overrides the model's, and both are recorded.
14. As a strategist, I want **PESTLE lanes on the Scroll**, with secondary categories shown, so
    that I see the domain spread of a future without duplicating nodes — and **PESTLE coverage
    of my anchors** before I generate, so that blind spots show early.
15. As a strategist, I want to **fork from any projection with a "what if" hint**, so that I can
    explore an alternative without losing the original.
16. As a strategist, I want to **edit or delete a projection and see which descendants are now
    stale**, so that I choose what to regenerate.
17. As a strategist, I want to **add a grounded assumption backed by a news item or government
    plan**, so that my own thinking enters the timeline with its evidence.
18. As a strategist, I want to **add a wild card with no evidence**, clearly marked, so that I
    can test an outlier without passing it off as grounded.
19. As a strategist, I want to **ask the system to find evidence for or against a projection**,
    so that I can ground a speculation quickly.
20. As a strategist, I want to **promote a futures-scoped reference into a new forecast run**,
    so that evidence I found while speculating can strengthen the forecast, deliberately.
21. As a strategist, I want to **undo and redo any action**, so that exploring is never
    destructive.
22. As a strategist, I want to **save an exploration to files and reopen it later**, so that the
    work persists.
23. As a strategist, I want to **toggle the futures layer on the forecast Graph tab**, so that I
    can see speculation next to the evidence it grew from.
24. As an operator, I want **every futures model call traced with full input and output**, so
    that generation is inspectable in Langfuse as well as in-app.
25. As an operator, I want **futures mode to work offline in fixture mode**, so that the whole
    loop is explorable without an API key.
26. As an operator, I want **the model per call type configurable**, so that I can compare cheap
    vs premium generation on the same exploration.

---

## Implementation Decisions

**One projection DAG; lenses are views** (ADR-0007). A single generator writes projections;
lenses read them and attach tags, and may additionally seed constrained forks and write
annotations (never projections directly). Branches may converge (multiple parents). Lens tags
are cached on the projection; strategist overrides are edits. A projection carries **order**
(causal depth) and a **time window** separately.

**Operation log is the source of truth; generator is a plain workflow** (ADR-0008). Each
exploration is an append-only log at `runs/<run>/explorations/<id>/log.jsonl`. Operations:
`create`, `generate_order`, `fork`, `seed_fork` (lens-constrained), `edit`, `set_window`,
`delete`, `add_assumption`, `add_wildcard`, `add_reference`, `retag`, `set_axes`, `annotate`,
`stop`. Generation operations embed the full prompt
inputs and raw model output.

- **State = replay of the log up to a cursor.** Undo/redo move the cursor. Redo of a generation
  replays the stored output — no model call. A new action after undo truncates the redo tail.
- **Stale propagation** is computed on replay: a projection is stale if any ancestor or anchor
  was edited, deleted, or (for pending edges) rejected at the gate after it was generated.
- **Materialized into the run's RDF graph** as a named graph per exploration, so projections
  share the graph with evidence and are distinguished by type and graph name.
- **Generator** is a plain Python loop over orders, appending one `generate_order` op per
  order and checking a cancel flag between orders (Stop). Not LangGraph: there is no HITL
  interrupt, and the log already checkpoints.

**Agents.** The pipeline is a workflow. Context-dependent judgments (how many projections per
order, convergence) are made *inside* each order's call. The one agent is **Ground this**,
reusing `discovery.py`'s model-guided search with a bounded step count.

**Model routing.** Every futures call type defaults to the cheap model (`deepseek-v4-flash`),
configurable per call type in `config.py`. Temperatures: generation / fork ≈ 0.9 (siblings
should diverge), axis proposal ≈ 0.5, classification 0. Futures reproducibility comes from the
stored log, not from temperature 0. Revisit after a flash-vs-pro side-by-side on the same
exploration.

**Generation limits.** Inputs: horizon (default 10 years, the time limit), orders (default 5,
the depth limit); generation stops at whichever comes first. Each order's call decides its
projection count within a per-node and per-order cap, assigns each projection a time window,
includes ≥1 anchored discontinuity, and the first call also opens the baseline branch. Caps
are configurable and will be tuned once the system is operational.

**Anchors.** Evidence anchors: extracted signals, flagged signals, pending cross-domain edges,
drafted claims. Futures-scoped anchors: strategist references (and those proposed by Ground
this). A model-generated projection must have ≥1 anchor or ≥1 anchored parent.

**Tracing.** Every futures model call is an OTel span with full input and output as
attributes (Langfuse shows them), *and* the same I/O lives in the operation log (the in-app
provenance panel works offline). Backport span input/output to the forecast pipeline's model
calls, closing the same gap there.

**Transport.** Live fill over **Server-Sent Events** (one stream per active generation). A
dropped connection re-syncs from the log.

**Frontend.** Futures mode uses **Preact + htm + @preact/signals**, vendored as ES modules —
no build step, "one command" preserved. One signal-backed exploration state drives the Scroll
and all lens views. The existing stepper stays vanilla JS.

**Rendering.** **D3** (SVG) for all futures views, vendored. The Scroll positions x by time
window and y by a crossing-minimizing lane packer (d3-dag's crossing minimization is a
candidate; layers are no longer pinned to columns) — the riskiest layout piece. Custom
geometry for Wheel, Matrix, Cone, Horizons curves. Cytoscape
remains on the forecast Graph tab.

**Design system — after the functional parts.** A custom, token-first system: CSS custom
properties (color, type scale, spacing, radii, motion; an *evidence* palette, a *futures*
palette, a lens-tag palette) plus ~10 Preact components (button, chip, panel, tabs,
roller/slider, node card, drawer, toast, toggle, empty state). One `tokens.css` drives D3
fills and the Cytoscape stylesheet too, and reskins the **whole app** (stepper, brief,
metrics, Graph tab). Direction: clean and specific rather than generic SaaS; the handscroll
governs transitions (sliding windows), not textures. Cytoscape is restyled first and replaced
only if it still falls short.

**Server.** New routes under `/runs/{run_id}/explorations/...` on the existing FastAPI app:
create, list, get snapshot, generate (SSE), stop, apply op, undo, redo, classify lens, propose
axes, ground, promote, export. Same error mapping as today (unknown → 404, wrong state → 409).

---

## Testing Decisions

Test external behavior through the exploration's seams, not generator internals, with
recorded fixtures instead of live model calls.

- **Replay determinism.** A given log replays to the same state; undo/redo round-trips; redo of
  a generation makes no model call.
- **Structural check (the one futures "eval").** No model-generated projection without an
  anchor or anchored parent. Asserted on every generate and fork.
- **Convergence.** A generation output linking to an existing projection yields one node with
  multiple parents, not a duplicate.
- **Stale propagation.** Editing/deleting a projection marks exactly its descendants stale;
  rejecting a pending edge at the gate marks the projections anchored to it stale.
- **One-way rule.** The forecast brief (md/json/pptx) contains no projections; the forecast's
  evidence graph is unchanged by any futures operation except promotion, which creates a new
  run and leaves the original untouched.
- **Lens overrides.** A drag-retag persists, survives replay, and is attributed.
- **Timing rule.** A child window starting before its parent's yields a timing-conflict
  marker, not a stale mark.
- **Generation invariants.** Every exploration has exactly one baseline branch; each generated
  order contains ≥1 anchored discontinuity; generation halts at the depth or time limit.
- **Lens forks and annotations.** A quadrant-seeded fork records its axis constraint; a
  scenario narrative goes stale when its quadrant's projections change.
- **Fixture mode.** One recorded exploration on the seed corpus (goal "direction of AI
  wearables", 5 orders / 10 years) exercising a fork, a convergence, a wild card, a grounded
  assumption, and a pending-edge anchor, plus recorded lens classifications. It doubles as the
  golden case for the structural check.
- **No regressions.** The existing suite still passes.

---

## Success Metrics

- From a forecast run, a strategist creates an exploration and sees a 5-order Scroll in one
  sitting, with live fill and Stop working.
- Switching lenses never triggers generation; overrides persist.
- Every projection's detail panel shows its full generating input/output and traces to an
  anchor or a labeled human assumption.
- Undo/redo works across every operation type; redo is free.
- The forecast brief is byte-identical with and without explorations on the run.
- An exploration costs a predictable, small number of cheap-model calls (≈ orders + lens
  classifications).

## Out of Scope (v4)

- Client-facing futures output.
- Probabilities or scoring of projections.
- Chaining lenses into generation pipelines (lenses only seed forks and write annotations).
- **Backcasting** (Robinson) — generating from a preferable future back to the present. A
  second generator direction for a later version; it fits the operation log and DAG
  unchanged.
- Causal Layered Analysis — a depth method on one issue, not an organizing lens.
- Replacing Cytoscape (only if restyling falls short).
- Multi-user editing.

## Build order (for `to-tickets`)

1. Operation log + replay + undo/redo + stale propagation (pure Python, test-first).
2. Generator: per-order calls, convergence, cancel; fixture exploration; span I/O tracing
   (and the forecast-pipeline backport).
3. Server routes + SSE.
4. Preact shell + Scroll (d3-dag), minimap rollers, detail panel, live fill.
5. Fork, edit/delete, stale UI, wild cards, grounded assumptions + futures-scoped anchors.
6. Lens framework (classification + drag override) → Wheel → Matrix (axis proposal,
   quadrant-seeded forks, scenario narratives) → Cone (nested + baseline) → Horizons (by role,
   anchors too) → PESTLE (multi-label, anchors too, + Scroll swimlanes).
7. Graph-tab futures toggle; export.
8. Promotion → new forecast run.
9. Ground this (agent).
10. Design system (tokens + components), reskinning the whole app.
