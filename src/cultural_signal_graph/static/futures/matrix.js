/* The Matrix lens (2×2, intuitive logics) — axis-first. Propose axes from the
   contested evidence, pick two, then read the four worlds: each quadrant holds the
   branch end states placed there, a scenario narrative (an annotation, never a
   projection), and a way to seed a branch for that world when it is thin or empty.
   Drag a projection to another quadrant to override its placement. */

import { h } from "preact";
import { useState } from "preact/hooks";
import htm from "htm";
import * as S from "./store.js";
import { marksText } from "./hints.js";

const html = htm.bind(h);

export const MATRIX_VALUES = ["q1", "q2", "q3", "q4", "none"];
const POLES = { q1: ["high", "high"], q2: ["low", "high"], q3: ["low", "low"], q4: ["high", "low"] };
const GRID = ["q2", "q1", "q3", "q4"]; // A runs low→high left to right; B high→low top to bottom

function AxisPicker({ snap, onDone }) {
  const cands = snap.axis_candidates || [];
  const [picked, setPicked] = useState(snap.axes ? snap.axes.map((a) => ({ ...a })) : []);
  const anchors = S.anchorsById.value;
  const toggle = (c) => {
    const has = picked.some((p) => p.name === c.name);
    setPicked(has ? picked.filter((p) => p.name !== c.name) : picked.length < 2 ? [...picked, { ...c }] : picked);
  };
  const edit = (i, key, value) => setPicked(picked.map((p, j) => (j === i ? { ...p, [key]: value } : p)));
  return html`<div class="card axis-picker">
    <h3>Critical uncertainties</h3>
    <p class="hint">Scenario planning starts from two uncertainties that matter and are unresolved. The model
      proposes candidates from your flagged and conflicting evidence; pick two and edit them freely.
      ${snap.axes ? " Changing the axes starts a new matrix: placements and narratives reset (undoable)." : ""}</p>
    <button onClick=${S.proposeAxes} disabled=${S.busy.value}>${cands.length ? "↻ Propose again" : "Propose axes"}</button>
    ${cands.map((c) => {
      const on = picked.some((p) => p.name === c.name);
      return html`<label key=${c.name} class=${`axis-cand ${on ? "on" : ""}`}>
        <input type="checkbox" checked=${on} onChange=${() => toggle(c)} />
        <span><b>${c.name}</b> <span class="hint">${c.low} ↔ ${c.high}</span>
          ${c.why ? html`<div class="hint">${c.why}</div>` : null}
          ${c.from.length ? html`<div class="axis-from">from: ${c.from.map((id) => html`<span key=${id} class="anchor-kind flagged">${anchors[id]?.text || id}</span>`)}</div>` : null}
        </span>
      </label>`;
    })}
    ${picked.map((a, i) => html`<div key=${i} class="axis-edit">
      <span class="axis-letter">${i === 0 ? "A" : "B"}</span>
      <input value=${a.name} onInput=${(e) => edit(i, "name", e.target.value)} />
      <input value=${a.low} onInput=${(e) => edit(i, "low", e.target.value)} placeholder="low pole" />
      <span>↔</span>
      <input value=${a.high} onInput=${(e) => edit(i, "high", e.target.value)} placeholder="high pole" />
    </div>`)}
    <div class="row right">
      ${snap.axes ? html`<button class="ghost" onClick=${onDone}>Cancel</button>` : null}
      <button class="primary" disabled=${picked.length !== 2 || S.busy.value}
        onClick=${async () => { await S.setAxes(picked); onDone(); }}>Use these two axes</button>
    </div>
  </div>`;
}

export function Matrix({ snap, selectedId, onSelect, onRetag }) {
  const [picking, setPicking] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [over, setOver] = useState(null);
  if (!snap.axes || picking) return html`<${AxisPicker} snap=${snap} onDone=${() => setPicking(false)} />`;

  const [A, B] = snap.axes;
  const hasChildren = new Set(snap.projections.flatMap((p) => p.parents));
  const shown = (p) => showAll || !hasChildren.has(p.id); // end states by default
  const inQ = (q) => snap.projections.filter((p) => (p.tags.matrix?.value || "none") === q);
  const notes = Object.fromEntries((snap.annotations || []).filter((a) => a.lens === "matrix").map((a) => [a.key, a]));
  const busy = S.busy.value || S.generating.value;

  const drop = (q) => (ev) => {
    ev.preventDefault();
    setOver(null);
    const pid = ev.dataTransfer.getData("text/plain");
    const p = S.projectionsById.value[pid];
    if (p && (p.tags.matrix?.value || "none") !== q) onRetag(p, { value: q });
  };
  const chip = (p) => html`<span key=${p.id} draggable="true"
    class=${`m-chip ${p.origin} ${selectedId === p.id ? "selected" : ""} ${p.tags.matrix?.source === "human" ? "by-human" : ""}`}
    onDragStart=${(ev) => ev.dataTransfer.setData("text/plain", p.id)}
    onClick=${() => onSelect(p.id)} title=${`${marksText(p) ? marksText(p) + "\n" : ""}${p.statement} (${p.window[0]}–${p.window[1]}) — drag to another world`}>
    <span class="order-badge">${p.order}</span>${p.statement}</span>`;

  const cell = (q) => {
    const members = inQ(q);
    const visible = members.filter(shown);
    const note = notes[q];
    const [pa, pb] = POLES[q];
    return html`<div key=${q} class=${`m-cell ${over === q ? "over" : ""}`}
      onDragOver=${(ev) => { ev.preventDefault(); setOver(q); }} onDragLeave=${() => setOver(null)} onDrop=${drop(q)}>
      <div class="m-world">${A.name}: <b>${A[pa]}</b> · ${B.name}: <b>${B[pb]}</b></div>
      ${note
        ? html`<p class=${`m-narrative ${note.stale ? "stale" : ""}`}>${note.text}
            ${note.stale ? html`<span class="stale-mark" title="Its projections changed after it was written">stale</span>` : null}</p>`
        : null}
      <div class="m-chips">${visible.map(chip)}</div>
      ${!members.length ? html`<div class="m-empty">No branch explores this world.</div>` : null}
      <div class="m-actions">
        <button class=${members.length ? "ghost" : "primary"} disabled=${busy} onClick=${() => S.seedQuadrant(q)}
          title="Generate a branch from the present, conditioned on this world">⑂ Seed a branch here</button>
        <button class="ghost" disabled=${busy || !members.length} onClick=${() => S.writeNarrative(q)}>
          ${note ? (note.stale ? "↻ Rewrite narrative" : "↻ Narrative") : "✎ Write narrative"}</button>
        <span class="hint">${members.length} placed${members.length !== visible.length ? ` · ${visible.length} end states` : ""}</span>
      </div>
    </div>`;
  };

  const none = inQ("none");
  return html`<div class="matrix">
    <div class="m-tools">
      <span><span class="axis-letter">A</span> ${A.name}: ${A.low} → ${A.high}</span>
      <span><span class="axis-letter">B</span> ${B.name}: ${B.low} → ${B.high}</span>
      <span class="spacer"></span>
      <button class=${`chip ${showAll ? "on" : ""}`} onClick=${() => setShowAll(!showAll)}>${showAll ? "All projections" : "End states"}</button>
      <button class="ghost" onClick=${() => setPicking(true)}>Change axes</button>
    </div>
    <div class="m-frame">
      <div class="m-axis-b"><span>${B.high}</span><span>${B.name}</span><span>${B.low}</span></div>
      <div class="m-grid">${GRID.map(cell)}</div>
    </div>
    <div class="m-axis-a"><span>${A.low}</span><span>${A.name}</span><span>${A.high}</span></div>
    ${none.length
      ? html`<details class="m-none" onDragOver=${(ev) => ev.preventDefault()} onDrop=${drop("none")}>
          <summary>${none.length} say nothing about either axis</summary>
          <div class="m-chips">${none.map(chip)}</div>
        </details>`
      : null}
  </div>`;
}
