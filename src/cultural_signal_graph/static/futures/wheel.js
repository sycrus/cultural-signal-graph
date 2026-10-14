/* The Wheel lens (Glenn's Futures Wheel): the initial state at the center, one ring
   per order (causal depth) — the generator's native shape. Each node sits near the
   mean angle of what it grows from, nudged apart so labels stay readable. Same
   projections, same selection as the Scroll: a lens arranges, it never generates. */

import { h } from "preact";
import { useLayoutEffect, useMemo, useRef, useState } from "preact/hooks";
import htm from "htm";
import { lineage } from "./layout.js";
import { nodeTitle } from "./hints.js";

const html = htm.bind(h);
const TAU = Math.PI * 2;

function spread(items, minGap) {
  /* Relax target angles on the circle so neighbours are at least `minGap` apart,
     keeping their order. */
  if (items.length < 2) return items;
  const gap = Math.min(minGap, TAU / items.length);
  items.sort((a, b) => a.angle - b.angle);
  for (let pass = 0; pass < 60; pass++) {
    let moved = false;
    for (let i = 0; i < items.length; i++) {
      const a = items[i];
      const b = items[(i + 1) % items.length];
      let d = b.angle - a.angle;
      if (i === items.length - 1) d += TAU;
      if (d < gap) {
        const push = (gap - d) / 2;
        a.angle -= push;
        b.angle += push;
        moved = true;
      }
    }
    if (!moved) break;
  }
  return items;
}

export function wheelLayout(snap) {
  /* -> {angle: {id: radians}, rings: maxOrder} */
  const angle = {};
  // each anchor gets an arc proportional to how much grows from it
  const children = {};
  for (const p of snap.projections) for (const s of [...p.parents, ...p.anchors]) (children[s] ||= []).push(p.id);
  const reach = (id, seen = new Set()) => {
    for (const c of children[id] || []) if (!seen.has(c)) (seen.add(c), reach(c, seen));
    return seen;
  };
  const weights = snap.anchors.map((a) => 1 + reach(a.id).size);
  const total = weights.reduce((x, y) => x + y, 0) || 1;
  let acc = 0;
  snap.anchors.forEach((a, i) => {
    angle[a.id] = ((acc + weights[i] / 2) / total) * TAU - Math.PI / 2;
    acc += weights[i];
  });
  const maxOrder = Math.max(0, ...snap.projections.map((p) => p.order));
  for (let order = 1; order <= maxOrder; order++) {
    const ring = snap.projections
      .filter((p) => p.order === order)
      .map((p) => {
        const src = [...p.parents, ...p.anchors].filter((s) => s in angle);
        // circular mean of the source angles
        const x = src.reduce((sum, s) => sum + Math.cos(angle[s]), 0);
        const y = src.reduce((sum, s) => sum + Math.sin(angle[s]), 0);
        return { id: p.id, angle: src.length ? Math.atan2(y, x) : -Math.PI / 2 };
      });
    for (const item of spread(ring, Math.min((TAU / ring.length) * 0.85, 0.9))) angle[item.id] = item.angle;
  }
  return { angle, rings: maxOrder };
}

export function Wheel({ snap, selectedId, onSelect, dimmed = () => false }) {
  const ref = useRef(null);
  const [width, setWidth] = useState(0);
  const [labelAll, setLabelAll] = useState(snap.projections.length <= 12);
  useLayoutEffect(() => {
    setWidth(ref.current.getBoundingClientRect().width);
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  const { angle, rings } = useMemo(() => wheelLayout(snap), [snap]);
  if (!width) return html`<div class="wheel" ref=${ref}></div>`;

  const size = Math.max(360, Math.min(width - 16, 900));
  const c = size / 2;
  const inner = Math.min(70, size * 0.09);
  const step = (c - inner - 70) / Math.max(rings, 1);
  const radius = (order) => inner + order * step;
  const pos = (id, order) => [c + Math.cos(angle[id]) * radius(order), c + Math.sin(angle[id]) * radius(order)];
  const byId = Object.fromEntries(snap.projections.map((p) => [p.id, p]));
  const path = lineage(snap, selectedId);
  const at = (id) => (byId[id] ? pos(id, byId[id].order) : pos(id, 0));

  const edges = [];
  for (const p of snap.projections) {
    for (const src of [...p.parents, ...p.anchors]) {
      if (!(src in angle)) continue;
      const [x1, y1] = at(src);
      const [x2, y2] = at(p.id);
      edges.push(html`<path key=${`${src}>${p.id}`} d=${`M${x1},${y1} Q${c + (x1 + x2 - 2 * c) * 0.55},${c + (y1 + y2 - 2 * c) * 0.55} ${x2},${y2}`}
        class=${`edge ${p.baseline && (byId[src]?.baseline || !byId[src]) ? "baseline" : ""} ${path.has(src) && path.has(p.id) ? "lit" : ""} ${path.size && !(path.has(src) && path.has(p.id)) ? "faded" : ""}`} />`);
    }
  }
  const label = (text, x, y) => {
    const right = x >= c;
    const t = text.length > 38 ? text.slice(0, 36) + "…" : text;
    return html`<text x=${x + (right ? 9 : -9)} y=${y + 3.5} text-anchor=${right ? "start" : "end"} class="wheel-label">${t}</text>`;
  };

  return html`<div class="wheel" ref=${ref}>
    <div class="wheel-tools">
      <button class="chip ${labelAll ? "on" : ""}" onClick=${() => setLabelAll(!labelAll)}>${labelAll ? "Labels: all" : "Labels: order 1 + selection"}</button>
    </div>
    <svg width=${size} height=${size} viewBox=${`0 0 ${size} ${size}`}>
      ${Array.from({ length: rings }, (_, i) => html`<g key=${i}>
        <circle cx=${c} cy=${c} r=${radius(i + 1)} class="wheel-ring" />
        <text x=${c} y=${c - radius(i + 1) - 4} text-anchor="middle" class="wheel-ring-label">order ${i + 1}</text>
      </g>`)}
      <circle cx=${c} cy=${c} r=${inner} class="wheel-core" />
      <text x=${c} y=${c + 4} text-anchor="middle" class="wheel-goal">${snap.exploration.goal.length > 26 ? snap.exploration.goal.slice(0, 24) + "…" : snap.exploration.goal}</text>
      ${edges}
      ${snap.anchors.map((a) => {
        const [x, y] = pos(a.id, 0);
        return html`<g key=${a.id} class=${`wheel-anchor ${a.kind} ${path.size && !path.has(a.id) ? "faded" : ""}`} onClick=${() => onSelect(a.id)}>
          <rect x=${x - 5} y=${y - 5} width="10" height="10" rx="2" /><title>${a.text}</title></g>`;
      })}
      ${snap.projections.map((p) => {
        const [x, y] = pos(p.id, p.order);
        return html`<g key=${p.id} onClick=${() => onSelect(p.id)}
          class=${`wheel-node ${p.baseline ? "baseline" : ""} ${p.discontinuity ? "discontinuity" : ""} ${p.origin} ${p.stale ? "stale" : ""} ${selectedId === p.id ? "selected" : ""} ${path.size && !path.has(p.id) ? "faded" : ""} ${dimmed(p) ? "dimmed" : ""}`}>
          <circle cx=${x} cy=${y} r=${selectedId === p.id ? 8 : 6} />
          ${labelAll || p.order === 1 || path.has(p.id) ? label(p.statement, x, y) : null}
          <title>${nodeTitle(p)} (${p.window[0]}–${p.window[1]})</title>
        </g>`;
      })}
    </svg>
  </div>`;
}
