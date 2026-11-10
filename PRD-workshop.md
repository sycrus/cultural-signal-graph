# Cultural Signal Graph — Workshop surface PRD

The strategist surface (`PRD-futures.md`) helps a strategist, alone or in a small agency team,
explore speculative futures grown from forecast evidence. The **workshop surface** runs the
same futures engine (ADR-0012) for a **group**: stakeholders, internal or external, or people
from different disciplines, brought together so their expertise and perspectives shape the
futures. Participants' ideas are the primary material. The model **proposes**, only when asked,
as extra stimulus.

---

## Problem Statement

Agencies run futures workshops, but what participants produce (notes, whiteboard photos, a
facilitator's write-up) is disconnected from the evidence and hard to build on. Four things are
missing:

1. **Capture with ownership.** Ideas lose who said them, and people need to own their ideas to
   talk about them.
2. **Structure while ideas are still forming.** Many ideas arrive before anyone knows what they
   build on or when they would happen.
3. **Help seeing connections.** Linking a room's ideas into consequences and convergences is
   hard to do live. A model can propose it.
4. **A take-away that stays faithful.** A synthesis that reimagines what people said erases
   their contribution.

## Solution

**People write and place; the model proposes; the facilitator decides.** A **workshop** is an
exploration run in stages by a **facilitator**, with **participants** contributing from their
phones. Ideas go onto the **Scroll** (the shared timeline) or into the **tray** (the pool of
unplaced ideas). When the facilitator asks, the model adds **proposals**: candidate ideas,
connections between existing ideas, and placements for tray items. Each comes with a one-line
reason, and the facilitator accepts or rejects it.

### Setting

- **In the room**, about 4–12 people, one **shared screen** driven by the facilitator, and
  participants on their phones. Remote sessions are future work.
- **One host** runs the server (a facilitator's machine or a small shared box). Phones reach it
  on the local network or through a tunnel.
- A workshop may **grow from a forecast run** (default: its extracted evidence is the Inspire
  material) or **start from a goal alone**, in which case it gets a thin run with no sources and
  no extraction.
- A workshop can span **several sessions**: it is one exploration, paused and reopened, with a
  session marker in the log for each sitting.

### Stages

The facilitator advances the stage and can step back. Each stage changes what the shared screen
and phones offer. Every stage change is an op.

| Stage | Participants | Model proposes (on request) |
|---|---|---|
| **Inspire** | Bring references and prompts; react to the evidence | Anchors for the goal (existing picker); with no forecast run, **Ground this** proposes references for the goal |
| **Envision** | Add ideas and place them | Candidate ideas, connections, convergences, placements for tray items; lens-seeded forks |
| **Prototype** | Fill prototype templates, attach photos of sketches or models | A first draft of a template's text fields |

### Capture

- **Join.** The facilitator opens a session, and the shared screen shows a **QR code / join
  link** carrying a random per-session token, valid until the facilitator ends the session.
  Participants pick their name from a **participant list prepared in advance** (name + role /
  discipline), with typing a name as the fallback for late arrivals. The join screen says what
  is recorded and how it will be credited (see Consent).
- **Push.** The facilitator sets the current **focus**, e.g. "consequences of the AR
  glasses branch". The focus prompt appears on every phone, and submissions are tagged with
  it.
- **Placing from a phone.** A phone never shows the whole board, only the ideas in the
  current focus:
  1. type the idea;
  2. **Builds on…**: pick one or more ideas in the focus (an idea may have several parents),
     or **Elsewhere**, which sends it to the **parking lot** in the tray, untagged;
  3. **When?**: a coarse slider (*soon · a few years · later*), clamped so it starts no
     earlier than any parent.

  Order follows from the parents; nobody thinks about causal depth. An idea with parents and a
  time lands on the Scroll; otherwise it goes to the tray.
- **On the shared screen**, the facilitator (or whoever is presenting) can also add an idea
  and place it directly.
- The UI must make placing feel light. The interaction pattern is still to be designed.
  Post-its are the mental model, not the form factor.

### Proposals

- The model proposes **only when the facilitator asks**. It is optional stimulus and never
  runs ahead of the room.
- Proposals arrive in a **proposals drawer**. **Ghost nodes and edges** show on the Scroll only
  for the item hovered or the batch selected, so model output never crowds out the room's ideas.
- **Kinds:** a candidate idea, a **connection** (this is a consequence of that; these converge),
  and a **placement** for a tray item (parents + time).
- **No probabilities.** A proposal carries a reason, never a score.
- **Rooted in the room.** Every model proposal traces to an accepted participant idea or a
  reference. When a proposal builds on a participant's idea, it **credits them** ("builds on
  Maria's idea"), and that credit carries into the synthesis.
- **Lenses** are facilitator tools on the shared screen (e.g. "which Matrix quadrant is
  empty? Fill it"). A lens-seeded fork arrives as a proposal like any other.

### Roles and control

- **Facilitator:** runs stages and pushes, accepts or rejects proposals, places and edits any
  idea, and is the **only one who can undo**. Undo reverses the latest op, whoever made it,
  including a phone submission.
- **Co-facilitator (tray steward)** (optional): sorts the tray and parking lot, so the
  facilitator can keep running the room. Can place and edit, but not accept proposals or undo.
- **Participant:** submits and places ideas in the current focus, and fills prototype
  templates.

Moderation load is shared two ways, and a workshop can use either or both: the co-facilitator
role, and **placement proposals** from the model, which turn sorting into accept / reject.

### Prototype templates

- Facilitator-defined, **customisable** templates (e.g. "postcard from the future",
  "artifact from 2032"), saved to a **reusable library**.
- Fields are text plus **photo upload**, so a sketch or physical model can be photographed.
  Uploads are stored under the run and attributed to the uploader in the log.
- The model can draft text fields on request. There is no image generation.

### Synthesis and take-away

- The model **drafts** the synthesis from accepted ideas, scenario narratives and authors. It
  must **not reimagine anything**: **every sentence cites the accepted ideas it draws on and
  their authors**, and a sentence that cites nothing is rejected (the same discipline as the
  Ground this judge). Facilitator edits are marked human-written. The model's draft stays in the
  log.
- **Format:** a readable document (Markdown / PDF) first, containing the synthesis, the
  prototype templates with photos, and the credits. A deck reusing the existing `.pptx` exporter
  comes second. The raw exploration (model provenance, internal evidence) stays internal.
- **Credit setting**, chosen by the facilitator before export: **by name**, **by role /
  discipline** (default), or **anonymous**. Recognising whose expertise or perspective an idea
  came from is the point of a cross-disciplinary workshop.

### Consent and removal

- The join screen states what is recorded (name, role, ideas, photos) and how it is credited.
- The facilitator can **remove a participant**: their name is anonymised across the log and
  their photos deleted. Their ideas stay, credited by role only. Replay keeps working because
  removal rewrites an identity, not history.

### Promotion

A reference found in a workshop, by a participant or by Ground this, can be **promoted** into a
new forecast run through the existing path (ADR-0010). The finder's credit carries over.

### Epistemic stance (kept from the strategist surface)

- No probabilities, likelihoods or votes presented as likelihood.
- Provenance is mandatory: every idea records its author, and every proposal records its model
  call and who accepted it.
- One-way into evidence: workshop ideas never enter a forecast brief or the forecast's
  evidence except through promotion.

---

## Engine changes (shared by both surfaces, per ADR-0012)

- **Operation log in SQLite** (ADR-0013): one table per run, so concurrent writes are ordered by
  transactions. `log.jsonl` stays the export / import format.
- **Named authors** on every op, with participant name + role. The strategist surface sends the
  current teammate's name too.
- A **proposed** state for model output (ideas, connections, placements) with `accept` /
  `reject` ops, following the pattern of pending cross-domain edges.
- **Unplaced ideas** (the tray, including the parking lot), placed later by an op.
- Ops for **stage**, **session** start/end, **focus** (push), participant **removal**, template
  definitions and photo uploads.
- The structural check extends its roots: model proposals must trace to an anchor, an
  accepted participant idea, or a reference. Human ideas are roots themselves.

## Concurrency roadmap

| Level | When | Approach |
|---|---|---|
| 1. Never lose a write | **Now** | SQLite-backed log (ADR-0013) |
| 2. Everyone sees changes live | Soon | Broadcast each appended op to open clients (`sse-starlette` + `broadcaster`, or FastAPI WebSockets) |
| 3. Several people editing, each with their own undo | Future | A CRDT (Yjs via `pycrdt` / `pycrdt-websocket`, or Loro) with per-person undo. Changes the source-of-truth model of ADR-0008, so it needs its own ADR |

## Non-Goals (for now)

- Remote sessions with full boards on every device.
- Per-person undo, and concurrent editing of the same idea.
- Image generation.
- Changing the strategist surface's defaults. Its teams gain named authors only; the tray stays
  workshop-only.
- Workshop ideas in the forecast brief.
- Votes as likelihood.

## Testing Decisions (outline)

- **Concurrent writes:** parallel submissions from phones and facilitator ops all land, in
  order.
- **Roots:** no model proposal without an anchor, an accepted participant idea or a reference.
- **Credit chain:** a proposal built on a participant's idea credits them, and so does the
  synthesis sentence that uses it.
- **Synthesis citations:** every sentence cites at least one accepted idea; an uncited sentence
  is rejected.
- **Undo:** facilitator undo reverses the latest op whoever wrote it; participants cannot undo.
- **Session token:** a token stops working when its session ends; phones can only write within
  the current focus.
- **Removal:** a removed participant's name is gone from replayed state and exports, their
  photos are deleted, and their ideas remain, credited by role.
- **Credit setting:** the exported document honours name / role / anonymous.
- **Fixture mode:** a recorded workshop, both with and without a forecast run, exercising
  phone placement, the parking lot, accepted and rejected proposals, a template with a
  photo, and the synthesis.
