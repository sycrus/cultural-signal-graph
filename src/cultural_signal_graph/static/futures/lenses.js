/* The lens registry (ADR-0007): each lens is an organizing view over the same
   projections. Switching lenses re-arranges what is already there; it never
   generates. A lens with `tags` asks the server to classify untagged projections on
   open (one cheap call, cached as an op); the strategist overrides by dragging. */

import { h } from "preact";
import { useEffect } from "preact/hooks";
import htm from "htm";
import * as S from "./store.js";
import { Scroll } from "./scroll.js";
import { Wheel } from "./wheel.js";
import { Cone, CONE_CLASSES } from "./cone.js";
import { Matrix, MATRIX_VALUES } from "./matrix.js";
import { Horizons, HORIZON_VALUES } from "./horizons.js";
import { Pestle, PESTLE_VALUES } from "./pestle.js";

const html = htm.bind(h);

export const LENSES = [
  { key: "scroll", label: "Scroll", hint: "Time left to right; the base view", view: Scroll },
  { key: "wheel", label: "Wheel", hint: "Futures Wheel: rings are orders (causal depth)", view: Wheel },
  {
    key: "cone",
    label: "Cone",
    hint: "Futures Cone: projected ⊂ plausible ⊂ possible, preposterous outside; ★ preferable",
    view: Cone,
    tags: true,
    values: CONE_CLASSES,
    extras: [{ key: "preferable", label: "Preferable (serves the goal)" }],
  },
  {
    key: "matrix",
    label: "Matrix",
    hint: "2×2 scenario matrix: two critical uncertainties, four worlds",
    view: Matrix,
    tags: true,
    values: MATRIX_VALUES,
  },
  {
    key: "horizons",
    label: "Horizons",
    hint: "Three Horizons: by role — dominant (H1), transition (H2±), emerging (H3) — anchors too",
    view: Horizons,
    tags: true,
    anchors: true,
    values: HORIZON_VALUES,
  },
  {
    key: "pestle",
    label: "PESTLE",
    hint: "PESTLE swimlanes: each projection in its primary dimension, secondaries as chips",
    view: Pestle,
    tags: true,
    anchors: true,
    values: PESTLE_VALUES,
    multi: "secondary",
  },
];

export const lensSpec = (key) => LENSES.find((l) => l.key === key);

/* Out-of-cone projections are greyed in every other view. */
const outOfCone = (p) => p.tags?.cone?.value === "preposterous";

/* Lenses with time on x can stretch the axis past the container and pan. */
const SPREADS = [1, 1.5, 2, 3];
function SpreadPicker() {
  return html`<span class="spread-pick" title="Stretch the time axis — pan left and right when spread past Fit">
    ${SPREADS.map(
      (sv) => html`<button key=${sv} class=${S.spread.value === sv ? "on" : ""}
        onClick=${() => (S.spread.value = sv)}>${sv === 1 ? "Fit" : `${sv}×`}</button>`,
    )}
  </span>`;
}

export function LensTabs() {
  const timeLens = ["scroll", "cone", "horizons", "pestle"].includes(S.lens.value);
  return html`<div class="lens-bar">
    <div class="lens-tabs" role="tablist">
      ${LENSES.map(
        (l) => html`<button key=${l.key} role="tab" title=${l.hint}
          class=${S.lens.value === l.key ? "on" : ""} onClick=${() => S.setLens(l.key)}>${l.label}</button>`,
      )}
    </div>
    ${timeLens ? html`<span class="spacer"></span><${SpreadPicker} />` : null}
  </div>`;
}

export function LensView({ snap, selectedId, onSelect }) {
  const lens = lensSpec(S.lens.value) || LENSES[0];
  const status = snap.lenses?.[lens.key];
  const untagged = lens.tags && status?.ready ? status.untagged || 0 : 0;
  useEffect(() => {
    if (untagged && !S.busy.value && !S.generating.value) S.classifyLens(lens.key);
  }, [lens.key, untagged, S.generating.value]);
  const View = lens.view;
  return html`
    ${untagged && S.busy.value ? html`<div class="card"><span class="spinner"></span> Organizing ${untagged} projection${untagged === 1 ? "" : "s"} with the ${lens.label}…</div>` : null}
    <${View} snap=${snap} selectedId=${selectedId} onSelect=${onSelect}
      dimmed=${lens.key === "cone" ? () => false : outOfCone}
      onRetag=${(p, tag) => S.setTag(p.id, lens.key, tag)} />`;
}

/* The drawer's view of a projection's lens tags: what the model said, what you set. */
export function TagEditor({ p, anchorsOnly = false }) {
  const tagged = LENSES.filter((l) => l.tags && (!anchorsOnly || l.anchors));
  if (!tagged.length) return null;
  return html`<div class="tag-editor">
    ${tagged.map((l) => {
      const tag = p.tags?.[l.key];
      return html`<div key=${l.key} class="tag-row">
        <span class="tag-lens">${l.label}</span>
        <select value=${tag?.value || ""} disabled=${S.busy.value}
          onChange=${(e) => S.setTag(p.id, l.key, { value: e.target.value, extras: l.multi ? { [l.multi]: (tag?.[l.multi] || []).filter((v) => v !== e.target.value) } : Object.fromEntries((l.extras || []).map((x) => [x.key, !!tag?.[x.key]])) })}>
          ${!tag ? html`<option value="">untagged</option>` : null}
          ${l.values.map((v) => html`<option key=${v} value=${v}>${v}</option>`)}
        </select>
        ${l.multi && tag ? html`<span class="tag-multi">${l.values.filter((v) => v !== tag.value).map((v) => html`<label key=${v} class="tag-extra">
            <input type="checkbox" checked=${(tag[l.multi] || []).includes(v)} disabled=${S.busy.value}
              onChange=${(e) => {
                const cur = new Set(tag[l.multi] || []);
                e.target.checked ? cur.add(v) : cur.delete(v);
                S.setTag(p.id, l.key, { value: tag.value, extras: { [l.multi]: [...cur] } });
              }} /> ${v}</label>`)}</span>` : null}
        ${(l.extras || []).map((x) => html`<label key=${x.key} class="tag-extra">
          <input type="checkbox" checked=${!!tag?.[x.key]} disabled=${!tag || S.busy.value}
            onChange=${(e) => S.setTag(p.id, l.key, { value: tag.value, extras: { [x.key]: e.target.checked } })} /> ${x.label}</label>`)}
        ${tag ? html`<span class="hint">${tag.source === "human"
          ? `set by you${tag.model_value && tag.model_value !== tag.value ? ` · model said ${tag.model_value}` : ""}`
          : tag.fixed ? "by construction" : "model"}</span>` : null}
      </div>`;
    })}
  </div>`;
}
