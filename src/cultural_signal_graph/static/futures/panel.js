/* The one detail panel (right side): a projection's statement, window, origin, what
   it grows from, what grows from it, and the generating call's full input + raw output
   — or an anchor's evidence. Actions for the selected node are passed in as children. */

import { h } from "preact";
import { useEffect, useState } from "preact/hooks";
import htm from "htm";
import * as S from "./store.js";
import { TagEditor } from "./lenses.js";

const html = htm.bind(h);
const opCache = {};

function Ref({ id, onSelect }) {
  const a = S.anchorsById.value[id];
  const p = S.projectionsById.value[id];
  const text = a ? a.text : p ? p.statement : id;
  return html`<li><a href="#" class=${a ? "ref-anchor" : "ref-proj"}
    onClick=${(ev) => { ev.preventDefault(); onSelect(id); }}>${a ? "▪" : "●"} ${text}</a></li>`;
}

function Provenance({ seq }) {
  const key = `${S.snap.value.exploration.id}:${seq}`;
  const [op, setOp] = useState(opCache[key] || null);
  useEffect(() => {
    if (opCache[key]) return setOp(opCache[key]);
    setOp(null);
    S.fetchOp(seq).then((o) => setOp((opCache[key] = o)));
  }, [key]);
  if (!op) return html`<div class="hint">Loading provenance…</div>`;
  const input = op.input?.prompt || (op.input ? JSON.stringify(op.input, null, 2) : "—");
  return html`<div class="provenance">
    <div class="hint">${op.op} · ${op.model || "human"}${op.temperature != null ? ` · temp ${op.temperature}` : ""}
      · ${op.author} · ${op.at.replace("T", " ").slice(0, 16)}</div>
    ${op.warnings?.length ? html`<div class="warn-line">⚠ ${op.warnings.join("; ")}</div>` : null}
    ${op.model ? html`<details><summary>Model input</summary><pre>${input}</pre></details>
      <details><summary>Raw output</summary><pre>${op.output}</pre></details>` : null}
  </div>`;
}

export function DetailPanel({ id, onSelect, onClose, actions = null }) {
  const a = S.anchorsById.value[id];
  const p = S.projectionsById.value[id];
  if (!a && !p) return null;
  const children = (S.snap.value.projections || []).filter((q) => q.parents.includes(id) || q.anchors.includes(id));
  if (a) {
    return html`<aside class="detail-panel">
      <button class="ghost close" onClick=${onClose}>✕</button>
      <div class=${`panel-kind ${a.kind}`}>${a.scope === "futures" ? "futures-scoped reference" : `evidence · ${a.kind}`}${a.flag ? ` · ${a.flag}` : ""}${a.status ? ` · ${a.status === "proposed" ? "pending sign-off" : a.status}` : ""}</div>
      ${a.status === "rejected" ? html`<div class="human-root">Rejected at the sign-off gate: everything resting on it is stale.</div>` : null}
      ${a.pending ? html`<div class="hint">Proposed cross-domain edge, not yet signed off. If it is rejected, what grows from it goes stale.</div>` : null}
      <h3>${a.text}</h3>
      ${a.entity ? html`<div class="hint">about ${a.entity}${a.confidence != null ? ` · confidence ${a.confidence}` : ""}</div>` : null}
      ${a.source_uri ? html`<div><a href=${a.source_uri} target="_blank" rel="noopener">source ↗</a></div>` : null}
      ${a.excerpt ? html`<blockquote>${a.excerpt}</blockquote>` : null}
      ${children.length ? html`<h4>Grows into</h4><ul class="refs">${children.map((c) => html`<${Ref} key=${c.id} id=${c.id} onSelect=${onSelect} />`)}</ul>` : null}
      ${actions}
    </aside>`;
  }
  return html`<aside class="detail-panel">
    <button class="ghost close" onClick=${onClose}>✕</button>
    <div class="panel-kind projection">projection · order ${p.order} · ${p.origin}</div>
    <h3>${p.statement}</h3>
    <div class="proj-tags">
      <span class="tag">${p.window[0] === p.window[1] ? p.window[0] : `${p.window[0]}–${p.window[1]}`}</span>
      ${p.baseline ? html`<span class="tag baseline">baseline</span>` : null}
      ${p.discontinuity ? html`<span class="tag discontinuity">discontinuity</span>` : null}
      ${p.timing_conflict ? html`<span class="tag warn">timing conflict</span>` : null}
      ${p.stale ? html`<span class="tag warn">stale</span>` : null}
    </div>
    ${p.timing_conflict ? html`<div class="hint">Starts before something it grows from — the dates are off, the content still stands.</div>` : null}
    ${p.stale ? html`<div class="hint">Something it grows from changed after it was generated.</div>` : null}
    ${p.hint ? html`<div class="hint">Fork hint: “${p.hint}”</div>` : null}
    ${p.human_root
      ? html`<div class="human-root ${p.human_root}">${p.origin === p.human_root
          ? p.human_root === "wildcard" ? "Wild card — written by the strategist, no evidence behind it." : "Grounded assumption — written by the strategist, resting on the reference below."
          : `Grows from a ${p.human_root === "wildcard" ? "wild card" : "grounded assumption"}: it traces back to a human assumption, not only to evidence.`}</div>`
      : null}
    ${actions}
    <h4>Lens tags</h4>
    <${TagEditor} p=${p} />
    <h4>Grows from</h4>
    <ul class="refs">${[...p.anchors, ...p.parents].map((s) => html`<${Ref} key=${s} id=${s} onSelect=${onSelect} />`)}</ul>
    ${children.length ? html`<h4>Grows into</h4><ul class="refs">${children.map((c) => html`<${Ref} key=${c.id} id=${c.id} onSelect=${onSelect} />`)}</ul>` : null}
    <h4>Provenance</h4>
    <${Provenance} seq=${p.op} />
    ${p.edited_op != null && p.edited_op !== p.op ? html`<h4>Last edit</h4><${Provenance} seq=${p.edited_op} />` : null}
  </aside>`;
}
