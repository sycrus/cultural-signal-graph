/* The Three Horizons lens (Sharpe): three curves over the horizon — H1, the dominant
   system, declining in fit; H3, the emerging pattern, rising; H2, the transition
   between. Items sit on their horizon's curve by ROLE, at their time window (anchors
   at the present: flagged evidence often shows up as an H3 seed). H2+ bridges toward
   H3, H2- is captured by H1. Drag a node onto another curve to re-tag it. */

import { h } from "preact";
import { useLayoutEffect, useRef, useState } from "preact/hooks";
import htm from "htm";
import { lineage } from "./layout.js";
import { marksText } from "./hints.js";

const html = htm.bind(h);

export const HORIZON_VALUES = ["H1", "H2-", "H2+", "H3"];
const CURVE = {
  H1: (t) => 0.86 - 0.72 * smooth(t),
  H2: (t) => 0.16 + 0.56 * Math.sin(Math.PI * Math.min(1, Math.max(0, t * 0.95 + 0.04))),
  H3: (t) => 0.1 + 0.76 * smooth(t),
};
const LABEL = { H1: "H1 · dominant system", H2: "H2 · transition", H3: "H3 · emerging pattern" };

function smooth(t) {
  const x = Math.min(1, Math.max(0, t));
  return x * x * (3 - 2 * x);
}

const curveOf = (value) => (value || "H2+").slice(0, 2);

export function Horizons({ snap, selectedId, onSelect, onRetag }) {
  const ref = useRef(null);
  const [width, setWidth] = useState(0);
  const [drag, setDrag] = useState(null);
  useLayoutEffect(() => {
    setWidth(ref.current.getBoundingClientRect().width);
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  if (!width) return html`<div class="horizons" ref=${ref}></div>`;

  const e = snap.exploration;
  const height = 440;
  const pad = { l: 60, r: 40, t: 30, b: 40 };
  const W = width - pad.l - pad.r;
  const H = height - pad.t - pad.b;
  const tOf = (year) => (year - e.start_year) / Math.max(e.horizon, 1);
  const X = (t) => pad.l + t * W;
  const Y = (v) => pad.t + (1 - v) * H;
  const curvePath = (f) =>
    Array.from({ length: 61 }, (_, i) => `${i ? "L" : "M"}${X(i / 60).toFixed(1)},${Y(f(i / 60)).toFixed(1)}`).join(" ");

  // place items on their curve; nudge collisions apart vertically
  const items = [
    ...snap.anchors.map((a) => ({ id: a.id, text: a.text, t: 0, tag: a.tags?.horizons, anchor: true, node: a })),
    ...snap.projections.map((p) => ({ id: p.id, text: p.statement, t: tOf((p.window[0] + p.window[1]) / 2), tag: p.tags?.horizons, node: p })),
  ];
  const placed = [];
  const pos = {};
  for (const it of items) {
    const c = curveOf(it.tag?.value);
    let x = X(it.t);
    let y = Y(CURVE[c](it.t));
    let k = 0;
    while (placed.some(([px, py]) => Math.abs(px - x) < 14 && Math.abs(py - y) < 14) && k < 12) {
      k++;
      y += (k % 2 ? 1 : -1) * 14 * Math.ceil(k / 2);
    }
    placed.push([x, y]);
    pos[it.id] = [x, y + (drag?.id === it.id ? drag.dy : 0)];
  }
  const path = lineage(snap, selectedId);
  const nearest = (x, y) => {
    const t = (x - pad.l) / W;
    return Object.keys(CURVE).reduce((best, c) => (Math.abs(Y(CURVE[c](t)) - y) < Math.abs(Y(CURVE[best](t)) - y) ? c : best), "H1");
  };
  const startDrag = (it) => (ev) => {
    ev.preventDefault();
    const y0 = ev.clientY;
    const [bx, by] = pos[it.id];
    let moved = false;
    const move = (m) => {
      if (Math.abs(m.clientY - y0) > 4) moved = true;
      setDrag({ id: it.id, dy: m.clientY - y0 });
    };
    const up = (u) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      setDrag(null);
      if (!moved) return onSelect(it.id);
      const c = nearest(bx, by + (u.clientY - y0));
      const was = it.tag?.value;
      const value = c === "H2" ? (was === "H2-" ? "H2-" : "H2+") : c;
      if (value !== was) onRetag(it.node, { value });
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  const years = [];
  for (let yr = e.start_year; yr <= e.start_year + e.horizon; yr += e.horizon > 12 ? 2 : 1) years.push(yr);
  const selected = items.find((it) => it.id === selectedId);

  return html`<div class="horizons" ref=${ref}>
    <svg width=${width} height=${height}>
      ${years.map((yr) => html`<g key=${yr}><line x1=${X(tOf(yr))} x2=${X(tOf(yr))} y1=${pad.t} y2=${pad.t + H} class="h-grid" />
        <text x=${X(tOf(yr))} y=${height - 14} text-anchor="middle" class="h-year">${yr}</text></g>`)}
      <text x=${pad.l - 10} y=${pad.t + 8} text-anchor="end" class="h-axis">prevalence</text>
      ${Object.entries(CURVE).map(([c, f]) => html`<g key=${c}>
        <path d=${curvePath(f)} class=${`h-curve ${c}`} />
        <text x=${X(c === "H1" ? 0.02 : c === "H2" ? 0.42 : 0.86)} y=${Y(f(c === "H1" ? 0.02 : c === "H2" ? 0.5 : 0.86)) - 10} class=${`h-label ${c}`}>${LABEL[c]}</text>
      </g>`)}
      ${items.map((it) => {
        const [x, y] = pos[it.id];
        const v = it.tag?.value;
        return html`<g key=${it.id} class=${`h-node ${curveOf(v)} ${v === "H2-" ? "captured" : ""} ${it.anchor ? "anchor" : ""} ${selectedId === it.id ? "selected" : ""} ${path.size && !path.has(it.id) ? "faded" : ""} ${it.tag?.source === "human" ? "by-human" : ""}`}
          onPointerDown=${startDrag(it)}>
          ${it.anchor ? html`<rect x=${x - 6} y=${y - 6} width="12" height="12" rx="2" />` : html`<circle cx=${x} cy=${y} r="6.5" />`}
          <title>${marksText(it) ? marksText(it) + "\n" : ""}${it.text}${v ? ` — ${v}${it.tag.source === "human" ? " (set by you)" : ""}` : " — untagged"}${it.anchor ? " · evidence" : ""}</title>
        </g>`;
      })}
      ${selected ? html`<text x=${Math.min(pos[selected.id][0] + 10, width - 10)} y=${pos[selected.id][1] - 10}
        text-anchor=${pos[selected.id][0] > width * 0.7 ? "end" : "start"} class="h-selected-label">${selected.text.slice(0, 70)}${selected.text.length > 70 ? "…" : ""}</text>` : null}
    </svg>
    <div class="h-legend hint">■ evidence (anchors, at the present) · ● projections at their time window · hollow on H2 = H2− (captured by H1), filled = H2+ (bridging to H3) · drag onto another curve to re-tag</div>
  </div>`;
}
