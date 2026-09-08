# Cultural Signal Graph — UI (v3) PRD

The reasoning layer (v1/v2) is complete and auditable, but it's a CLI + files. This PRD
defines the **UI version**: a local web application that turns the pipeline into a
strategist-driven workflow, with the human-in-the-loop sign-off as its centerpiece.

---

## Problem Statement

A strategist using the system today runs a CLI and reads four files (`brief.md`,
`brief.json`, `graph.html`, `brief.pptx`). That's fine for a developer, but it buries the
product's whole differentiator — *"reproduce any conclusion back to its evidence"* — behind
file paths and a terminal. Three things are impossible in the current interface:

1. **You can't drive a forecast.** There's no way to enter a category/question/window and
   start a run; the CLI uses a hard-coded seed corpus.
2. **You can't watch it reason.** The stages (extract → align → gate → draft) run headlessly;
   there's no view of progress, tokens, or the trace.
3. **You can't perform the sign-off.** The HITL gate exists as a LangGraph `interrupt()`, but
   nothing surfaces it. A strategist can't approve or reject a cross-domain equivalence edge,
   which is the exact moment the product is supposed to add judgment.

---

## Solution

A **local web application** (one command, opens in a browser) that presents the pipeline as a
guided workflow. The critical fact that shapes everything: **the sign-off happens mid-run,
not after.** The pipeline is `discover → extract → align → ⛔ sign-off → draft → brief` — it
*pauses* after alignment, waits for the human, then resumes. So the UI is a **stepper**, not a
fire-and-forget dashboard.

```
Ask  →  Sources  →  Run  →  ⛔ Sign-off  →  Brief  →  Graph / Metrics
```

## User flow (when it's done, what the user sees)

**1. Ask** — a form for category, question, time window, and (v2) market.
*Done when:* the strategist clicks **Run**.

```
┌ Ask ─────────────────────────────┐
│ Category  [tech ▾]               │
│ Question  [AI wearables adoption]│
│ Window    [2026-01 ─ 2026-06]   │
│ Market    [SEA ▾ (optional)]    │
│                    [ Run → ]     │
└──────────────────────────────────┘
```

**2. Sources (collapsed by default)** — the discovered sources appear (index, or web backfill
for an unfamiliar category), editable so the strategist can add/remove before extraction.
*Done when:* they proceed to run. Auditable-by-default, one click to override, hidden for the
fast path.

**3. Run** — the stages light up as they complete, with per-stage tokens and latency.

```
extract ✓        align ✓        sign-off …        draft        brief
        [flash 878 tok]  [pro 564 tok]
```

**4. Sign-off — the centerpiece.** The run is *paused here*; nothing proceeds until the human
acts. The strategist sees the proposed cross-domain edges and decides each:

```
◉ Review 1 cross-domain link

┌──────────────────────────────────────┐
│  AI headset  ≈  AI wearables         │
│  confidence 0.85      gaming ⇄ tech  │
│                                      │
│  [ ✓ Approve ]   [ ✕ Reject ]        │
└──────────────────────────────────────┘
  Approving links gaming↔tech; rejecting keeps them separate.
```

**5. Brief** — after sign-off, drafting finishes and the review appears, with tabs
`[Brief] [Graph] [Metrics]`:

```
Trends
 1. Alibaba Quark AI glasses… (0.95)  ▸ reasoning  ▸ sources
 2. Smart glasses search surge (0.8)  ▸ reasoning
⚠ Conflicts — Logitech CEO: "solutions looking for a problem"
⛓ Gated edges — AI headset ≈ AI wearables · approved ✓
```

**6. Graph / Metrics** — the graph tab (click a claim → trace to sources) and the metrics tab
(eval scores, tokens, prediction accuracy).

## Layout (recommended)

**Vertical stepper.** A left rail lists the stages with their current state; the main canvas
shows the active stage's content. The sign-off is a rail item that *blocks* until resolved, and
its canvas shares the same "review" surface as the Brief step. This supports "reopen a past run"
naturally (jump to any completed stage) and makes the "you are here, here's what's blocked" state
legible. (A one-card-per-step wizard is prettier but forces a linear march and makes
"jump to the graph to check a source" awkward.)

## Rerun & undo

Every action must be re-doable — no destructive one-shot. The file-backed checkpoint (#14) is
the mechanism: state is persisted at each stage boundary, so a step can be re-run and a decision
re-made.

- **Re-run a step.** "Re-run extraction" re-executes that stage (and downstream) from the prior
  checkpoint. Model stages (extract/align/draft) re-run *fresh* (a new model call, may differ);
  deterministic stages (graph build, flags) *replay* identically. Exposed as a per-stage
  "Re-run" affordance, and a top-level "Re-run from here".
- **Undo a sign-off.** The decision is recorded but stays editable until the run is exported.
  Re-open the sign-off step, change Approve→Reject (or vice-versa), and the downstream
  (draft → brief) re-runs. This is the key undo: the sign-off is the one genuinely irreversible
  *decision*, and it must not be.
- **Revert source edits.** "Reset sources" restores the auto-discovered set.
- **Replay vs re-run, distinguished in the UI.** Replay (from checkpoint) is deterministic and
  labeled as such; re-run (fresh model) is labeled "may change".

## Information hierarchy (legibility)

Summary first, detail on demand — everywhere, not just the graph.

- **Graph nodes carry short identifiers, not prose.** A signal node shows a short tag (e.g.
  "Alibaba ships Quark…"), not its full statement; the full statement, confidence, temporal
  validity, and provenance live in the right property panel on click. Smaller label font
  (~9px), tighter max-width.
- **Brief claims are headlines.** A claim shows a headline + confidence; the reasoning chain and
  source list are collapsed and expandable.
- **One detail panel, not many tooltips.** A single property panel (right side) is the home for
  node/claim detail; hover hints are minimal.

*(This also fixes the current `graph.html`: node labels are too long and the font too large;
  full text moves to the property panel.)*

## Annotations & corrections

The graph is an **audit trail** — the user *annotates* it, never mutates it in place.

- **Notes (v3).** Free-text annotations attached to a node/edge, with author + timestamp,
  from the Graph tab's property panel ("Add note"). A pure overlay — never affects reasoning
  or provenance.
- **Corrections (KIV v4).** Changing what the system *extracted* — rename an entity, adjust a
  confidence, add a missed signal. This alters the audit trail, so it needs a careful model:
  *correct, don't overwrite*. A correction is a first-class event on a separate human layer
  (old → new value, who/when/why), the machine layer stays preserved, and it can trigger a
  downstream re-run. Deferred to v4 because it touches the core "reproduce any conclusion back
  to its evidence" promise.

---

## Goals

- **Human sign-off becomes real.** A strategist approves/rejects a cross-domain edge and the
  graph reflects it.
- **Auditable reasoning is visible, not just available.** Every claim's chain of evidence is
  one click away.
- **One command, zero setup.** `run` starts a local server; the browser does the rest.
- **Existing artifacts stay.** `brief.md/json`, `graph.ttl`, `brief.pptx`, `usage.json` remain
  the exportable, versionable outputs.
- **Reversible.** Every action (sign-off, source edit) can be re-done.

## Non-Goals

- Multi-user / auth / teams; mobile; hosted SaaS.
- Prediction accuracy as a correctness gate (stays reported telemetry, #17).
- Reimplementing flag/gate/brief/draft logic client-side.

## User Stories

1. As a strategist, I want to **enter a category, question, window, and market** and start a
   forecast, without a terminal.
2. As a strategist, I want to **watch the run progress** (stage, tokens, latency).
3. As a strategist, I want to **read each claim with its reasoning and sources**.
4. As a strategist, I want **conflicts and low-confidence signals flagged visually**.
5. As a strategist, I want to **approve or reject a proposed cross-domain edge**.
6. As a strategist, I want to **click a claim and trace it to its sources in the graph**.
7. As a strategist, I want to **see eval scores, cost, and prediction accuracy**.
8. As a strategist, I want to **reopen a past run** (from a checkpoint).
9. As a strategist, I want to **undo a sign-off or revert a source edit**, so mistakes aren't
   permanent.

## Key Decisions (resolved by the flow)

- **Form factor:** local web app (Python server + browser).
- **Backend:** FastAPI — holds the paused LangGraph run (file-backed checkpoint, #14) and serves
  the `resume(decisions)` endpoint the sign-off calls.
- **Frontend:** server-rendered + a little JS, reusing the vendored Cytoscape graph.
- **Sign-off first**, not a read-only dashboard: without it the run dead-ends at the gate, and
  the dashboard is just "step 5 without steps 1–4".
- **Source discovery shown, collapsed:** auditable by default, hidden for the fast path.
- **State:** file-backed (`runs/`), so reopening and re-running are file reads, not a database.

## Success Metrics

- **Sign-off completes the loop:** approve/reject a cross-domain edge and the resulting
  `graph.ttl` shows it "real" or dropped — verified by the existing gate-correctness test,
  exercised through the UI.
- **Undo works:** a sign-off can be reversed and the brief regenerates.
- **Time-to-audit:** from "start a forecast" to "I can defend this claim" in under a minute.
- **No regressions:** the existing 60 tests still pass.

## Out of Scope

- Multi-user accounts, auth, teams; mobile; hosted deployment.
- Re-implementing flag/gate/brief/draft logic client-side.
- Changing how reasoning, flagging, or gating *works* — only how it's *presented and acted on*.
- Correcting/editing extracted data (KIV v4 — alters the audit trail).
