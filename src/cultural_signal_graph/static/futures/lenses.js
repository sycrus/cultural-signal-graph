/* The lens registry (ADR-0007): each lens is an organizing view over the same
   projections. Switching lenses re-arranges what is already there; it never
   generates. Lenses that need tags (quadrant, cone class, …) register a `tags` key. */

import { h } from "preact";
import htm from "htm";
import * as S from "./store.js";
import { Scroll } from "./scroll.js";
import { Wheel } from "./wheel.js";

const html = htm.bind(h);

export const LENSES = [
  { key: "scroll", label: "Scroll", hint: "Time left to right; the base view", view: Scroll },
  { key: "wheel", label: "Wheel", hint: "Futures Wheel: rings are orders (causal depth)", view: Wheel },
];

export function LensTabs() {
  return html`<div class="lens-tabs" role="tablist">
    ${LENSES.map(
      (l) => html`<button key=${l.key} role="tab" title=${l.hint}
        class=${S.lens.value === l.key ? "on" : ""} onClick=${() => S.setLens(l.key)}>${l.label}</button>`,
    )}
  </div>`;
}

export function LensView({ snap, selectedId, onSelect }) {
  const lens = LENSES.find((l) => l.key === S.lens.value) || LENSES[0];
  const View = lens.view;
  return html`<${View} snap=${snap} selectedId=${selectedId} onSelect=${onSelect} />`;
}
