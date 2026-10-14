/* Promote a futures-scoped reference into the forecast. Sources lock once a run
   starts, so this creates a NEW forecast run (same ask, original sources plus this
   one); the original run and its explorations stay exactly as they are. */

import { h } from "preact";
import { useState } from "preact/hooks";
import htm from "htm";
import * as S from "./store.js";

const html = htm.bind(h);

export function PromoteAction({ a }) {
  const [confirming, setConfirming] = useState(false);
  const done = S.promoted.value;
  if (a.scope === "promoted") {
    const from = a.promoted_from;
    return html`<div class="human-root assumption">Promoted into this run's forecast from
      <a href=${`/futures?run=${from.run}&x=${from.exploration}`}>an exploration on run ${from.run}</a>.</div>`;
  }
  if (a.scope !== "futures") return null;
  if (done && done.exploration.anchors.some((x) => x.id === a.id && x.source_uri === a.source_uri)) {
    const run = done.run.id;
    return html`<div class="action-form">
      <div>Promoted. New forecast run <b>${run}</b> has this reference as a source; it is ready to run.</div>
      <div class="row right">
        <a class="btn" href=${`/?run=${run}`}>Open the new run →</a>
        <a class="btn" href=${`/futures?run=${run}&x=${done.exploration.exploration.id}`}>Open the carried exploration →</a>
      </div>
    </div>`;
  }
  if (confirming) {
    return html`<div class="action-form">
      <div>Promote this reference into the forecast? This creates a <b>new forecast run</b> with the same ask and
        the original sources plus this one. This run and its explorations stay untouched; the exploration is copied
        to the new run, where a branch grows from this reference.</div>
      <div class="row right">
        <button class="ghost" onClick=${() => setConfirming(false)}>Cancel</button>
        <button class="primary" disabled=${S.busy.value} onClick=${async () => { await S.promoteReference(a.id); setConfirming(false); }}>Promote → new run</button>
      </div>
    </div>`;
  }
  return html`<div class="actions"><button onClick=${() => setConfirming(true)}
    title="Make this reference forecast evidence — in a new run">↗ Promote to forecast</button></div>`;
}
