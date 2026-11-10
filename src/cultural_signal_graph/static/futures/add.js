/* The strategist's own additions: a grounded assumption (needs a reference — the
   evidence it rests on), a wild card (no reference; greyed), or a reference alone.
   References land in the Present column as futures-scoped anchors: never in the
   forecast's evidence or brief. */

import { h } from "preact";
import { useState } from "preact/hooks";
import htm from "htm";
import * as S from "./store.js";
import { Button, Drawer, Tabs, toast } from "./ui.js";

const html = htm.bind(h);

export function AddPanel() {
  const s = S.snap.value;
  const opts = S.adding.value || {};
  const parent = opts.parent_id ? S.projectionsById.value[opts.parent_id] : null;
  const refs = s.anchors.filter((a) => a.kind === "reference");
  const [kind, setKind] = useState(opts.kind || "assumption");
  const [statement, setStatement] = useState("");
  const defaultStart = parent ? parent.window[1] : s.exploration.start_year + 1;
  const [start, setStart] = useState(defaultStart);
  const [end, setEnd] = useState(defaultStart + 1);
  const [refMode, setRefMode] = useState(refs.length ? "existing" : "new");
  const [refId, setRefId] = useState(refs[0]?.id || "");
  const [url, setUrl] = useState("");
  const [excerpt, setExcerpt] = useState("");
  const close = () => (S.adding.value = null);

  const submit = async () => {
    if (kind === "reference") {
      await S.addReference(url, excerpt);
    } else {
      const body = { kind, statement, window: [Number(start), Number(end)], parent_id: parent?.id || null };
      if (kind === "assumption") {
        if (refMode === "existing") body.reference_id = refId;
        else body.reference = { url, excerpt };
      }
      await S.addProjection(body);
    }
    if (!S.error.value) {
      close();
      toast(kind === "reference" ? "Reference added to the Present column." : kind === "wildcard" ? "Wild card added." : "Assumption added.");
    }
  };

  const referenceFields = html`
    <label>Source URL</label>
    <input value=${url} onInput=${(e) => setUrl(e.target.value)} placeholder="https://… (news, a government forecast or plan)" />
    <label>Excerpt</label>
    <textarea rows="3" value=${excerpt} onInput=${(e) => setExcerpt(e.target.value)} placeholder="What the source says"></textarea>
    <div class="hint">Summarized to one line for the generator. Stays futures-scoped: never forecast evidence.</div>`;

  return html`<${Drawer} kind="Add to the exploration" class="add-panel" onClose=${close}>
    <${Tabs} variant="soft" label="What to add" value=${kind} onChange=${setKind}
      items=${[{ key: "assumption", label: "Grounded assumption" }, { key: "wildcard", label: "Wild card" }, { key: "reference", label: "Reference" }]} />
    ${kind === "reference"
      ? referenceFields
      : html`
        <div class="hint">${kind === "assumption"
          ? "Your own projection, resting on a reference you supply."
          : "An outlier with no evidence — allowed, tagged, greyed. Its descendants trace back to it."}</div>
        <label>Statement</label>
        <textarea rows="3" value=${statement} onInput=${(e) => setStatement(e.target.value)}></textarea>
        <label>Time window</label>
        <div class="row">
          <input type="number" value=${start} onInput=${(e) => setStart(e.target.value)} />
          <span>→</span>
          <input type="number" value=${end} onInput=${(e) => setEnd(e.target.value)} />
        </div>
        <div class="hint">${parent
          ? html`Grows from “${parent.statement}” (order ${parent.order + 1}).
              <a href="#" onClick=${(e) => { e.preventDefault(); S.adding.value = { ...opts, parent_id: null }; }}>Detach</a>`
          : "Attached to the present (order 1). Select a projection and use “+ After this” to grow from it."}</div>
        ${kind === "assumption"
          ? html`<label>Reference</label>
            ${refs.length
              ? html`<${Tabs} variant="soft" size="sm" label="Reference" value=${refMode} onChange=${setRefMode}
                  items=${[{ key: "existing", label: "Existing" }, { key: "new", label: "New" }]} />`
              : null}
            ${refMode === "existing" && refs.length
              ? html`<select value=${refId} onChange=${(e) => setRefId(e.target.value)}>
                  ${refs.map((r) => html`<option key=${r.id} value=${r.id}>${r.text}</option>`)}
                </select>`
              : referenceFields}`
          : null}`}
    ${S.error.value ? html`<div class="error">${S.error.value}</div>` : null}
    <div class="row right" style="margin-top:12px">
      <${Button} variant="ghost" onClick=${close}>Cancel<//>
      <${Button} variant="primary" onClick=${submit} busy=${S.busy.value} busyLabel="Adding…">Add<//>
    </div>
  <//>`;
}
