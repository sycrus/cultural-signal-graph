/* Actions on the selected projection (shown in the detail panel): edit, delete,
   regenerate what went stale below it. Every action is an op — undoable. */

import { h } from "preact";
import { useEffect, useState } from "preact/hooks";
import htm from "htm";
import * as S from "./store.js";
import { GroundButton } from "./ground.js";
import { Button, Chip, toast } from "./ui.js";

/* Undo and redo say what they did, with the way back. */
async function undo() {
  await S.undo();
  if (!S.error.value) toast("Undone.", { action: { label: "Redo", run: redo } });
}
async function redo() {
  await S.redo();
  if (!S.error.value) toast("Redone.", { action: { label: "Undo", run: undo } });
}

const html = htm.bind(h);

export function ProjectionActions({ p, extra = null }) {
  const [mode, setMode] = useState(null); // null | "edit" | "delete" | "fork"
  const [hint, setHint] = useState("");
  const [statement, setStatement] = useState(p.statement);
  const [start, setStart] = useState(p.window[0]);
  const [end, setEnd] = useState(p.window[1]);
  useEffect(() => {
    setMode(null);
    setStatement(p.statement);
    setStart(p.window[0]);
    setEnd(p.window[1]);
  }, [p.id, p.statement, p.window[0], p.window[1]]);

  const staleBelow = S.snap.value.projections.some(
    (q) => q.stale && (q.parents.includes(p.id) || q.anchors.includes(p.id)),
  );
  const busy = S.busy.value || S.generating.value;

  if (mode === "edit") {
    const save = () => {
      const changes = {};
      if (statement.trim() !== p.statement) changes.statement = statement;
      if (Number(start) !== p.window[0] || Number(end) !== p.window[1]) changes.window = [Number(start), Number(end)];
      if (Object.keys(changes).length) S.editProjection(p.id, changes);
      setMode(null);
    };
    return html`<div class="action-form">
      <label>Statement</label>
      <textarea rows="3" value=${statement} onInput=${(e) => setStatement(e.target.value)}></textarea>
      <label>Time window</label>
      <div class="row">
        <input type="number" value=${start} onInput=${(e) => setStart(e.target.value)} />
        <span>→</span>
        <input type="number" value=${end} onInput=${(e) => setEnd(e.target.value)} />
      </div>
      <div class="hint">A new statement marks what grew from it stale; a new window only flags timing.</div>
      <div class="row right">
        <${Button} variant="ghost" onClick=${() => setMode(null)}>Cancel<//>
        <${Button} variant="primary" onClick=${save} disabled=${busy}>Save<//>
      </div>
    </div>`;
  }
  if (mode === "fork") {
    const depthLeft = S.snap.value.exploration.orders - p.order;
    return html`<div class="action-form">
      <label>What if… <span class="hint">(optional)</span></label>
      <input value=${hint} onInput=${(e) => setHint(e.target.value)} placeholder="the EU bans always-on cameras" />
      <div class="hint">Grows a sibling branch from here, ${depthLeft} order${depthLeft === 1 ? "" : "s"} deep. The original stays.</div>
      <div class="row right">
        <${Button} variant="ghost" onClick=${() => setMode(null)}>Cancel<//>
        <${Button} variant="primary" disabled=${busy}
          onClick=${() => { S.forkProjection(p.id, hint); setHint(""); setMode(null); }}>⑂ Fork<//>
      </div>
    </div>`;
  }
  if (mode === "delete") {
    return html`<div class="action-form danger">
      <div>Delete this projection? What grew from it stays, marked stale. Undo brings it back.</div>
      <div class="row right">
        <${Button} variant="ghost" onClick=${() => setMode(null)}>Cancel<//>
        <${Button} variant="danger" disabled=${busy} onClick=${async () => {
          await S.deleteProjection(p.id);
          if (!S.error.value) toast("Projection deleted. What grew from it is marked stale.", { action: { label: "Undo", run: undo } });
        }}>Delete<//>
      </div>
    </div>`;
  }
  return html`<div class="actions">
    <${Button} onClick=${() => setMode("edit")} disabled=${busy}>✎ Edit<//>
    <${Button} onClick=${() => setMode("fork")} disabled=${busy || p.order >= S.snap.value.exploration.orders}
      title=${p.order >= S.snap.value.exploration.orders ? "At the depth limit" : "Explore an alternative from here"}>⑂ Fork<//>
    <${GroundButton} p=${p} />
    ${extra}
    <${Button} onClick=${() => { S.adding.value = { kind: "assumption", parent_id: p.id }; }} disabled=${busy}
      title="Add your own assumption or wild card growing from this one">+ After this<//>
    <${Button} variant="ghost" onClick=${() => setMode("delete")} disabled=${busy}>Delete<//>
    ${staleBelow
      ? html`<${Button} variant="primary" onClick=${() => S.regenerateDownstream(p.id)} disabled=${busy}
          title="Replace the stale projections below this one with a fresh branch">↻ Regenerate downstream<//>`
      : null}
  </div>`;
}

export function HistoryBar() {
  const s = S.snap.value;
  const busy = S.busy.value || S.generating.value;
  useEffect(() => {
    const onKey = (e) => {
      if (!(e.ctrlKey || e.metaKey) || e.target.closest("input, textarea")) return;
      const k = e.key.toLowerCase();
      if (k === "z" && !e.shiftKey && S.snap.value?.can_undo) {
        e.preventDefault();
        undo();
      } else if ((k === "y" || (k === "z" && e.shiftKey)) && S.snap.value?.can_redo) {
        e.preventDefault();
        redo();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const stale = s.projections.filter((p) => p.stale).length;
  return html`<span class="history">
    ${stale ? html`<${Chip} tone="danger" title="Projections whose upstream changed after they were generated">${stale} stale<//>` : null}
    <${Button} variant="ghost" onClick=${undo} disabled=${!s.can_undo || busy} title="Undo (Ctrl+Z)">↶ Undo<//>
    <${Button} variant="ghost" onClick=${redo} disabled=${!s.can_redo || busy} title="Redo (Ctrl+Shift+Z) — replays the log, no model call">↷ Redo<//>
  </span>`;
}
