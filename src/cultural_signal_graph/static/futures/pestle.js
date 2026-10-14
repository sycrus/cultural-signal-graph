/* The PESTLE lens: the Scroll with its y-axis driven by each projection's PRIMARY
   dimension (one swimlane each — no duplicated nodes), secondary dimensions shown as
   chips. A coverage bar shows the spread; an empty dimension offers to seed a branch
   that follows it. Drag a card to another lane to change its primary. */

import { h } from "preact";
import htm from "htm";
import * as S from "./store.js";
import { Scroll } from "./scroll.js";

const html = htm.bind(h);

export const PESTLE_VALUES = ["political", "economic", "social", "technological", "legal", "environmental"];
export const PESTLE_LETTER = { political: "P", economic: "E", social: "S", technological: "T", legal: "L", environmental: "En" };

export function Coverage({ items, onGap = null, label = "projections" }) {
  /* Counts per primary dimension; zeros are gaps. */
  const count = Object.fromEntries(PESTLE_VALUES.map((v) => [v, 0]));
  const touch = Object.fromEntries(PESTLE_VALUES.map((v) => [v, 0]));
  for (const it of items) {
    const t = it.tags?.pestle;
    if (!t) continue;
    count[t.value] += 1;
    for (const s of t.secondary || []) touch[s] += 1;
  }
  const gaps = PESTLE_VALUES.filter((v) => !count[v]);
  return html`<div class="pestle-coverage">
    ${PESTLE_VALUES.map((v) => html`<span key=${v} class=${`pc ${count[v] ? "" : "gap"}`}
      title=${`${count[v]} ${label} with ${v} as primary; ${touch[v]} more touch it`}>
      <b>${PESTLE_LETTER[v]}</b> ${v} <span class="n">${count[v]}${touch[v] ? `+${touch[v]}` : ""}</span>
      ${!count[v] && onGap ? html`<button class="ghost" onClick=${() => onGap(v)} disabled=${S.busy.value || S.generating.value}
          title=${`Seed a branch that follows the ${v} dimension`}>seed?</button>` : null}
    </span>`)}
    ${gaps.length ? html`<span class="hint">No ${gaps.join(", ")} ${label}.</span>` : null}
  </div>`;
}

export function Pestle({ snap, selectedId, onSelect, onRetag, dimmed }) {
  const chips = (p) =>
    (p.tags.pestle?.secondary || []).map((s) => html`<span key=${s} class="pestle-chip" title=${`also ${s}`}>${PESTLE_LETTER[s]}</span>`);
  return html`<div>
    <${Coverage} items=${snap.projections} onGap=${S.seedDimension} />
    <${Scroll} snap=${snap} selectedId=${selectedId} onSelect=${onSelect} dimmed=${dimmed}
      laneKey=${(p) => p.tags.pestle?.value || "~untagged"}
      laneLabel=${(k) => (k === "~untagged" ? "untagged" : k)}
      chips=${chips}
      onLaneDrop=${(p, key) => key !== "~untagged" && onRetag(p, { value: key, extras: { secondary: p.tags.pestle?.secondary || [] } })} />
  </div>`;
}
