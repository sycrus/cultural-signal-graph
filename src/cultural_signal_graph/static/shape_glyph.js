/* A run's or exploration's fingerprint (list rows): its graph drawn small, without
   labels, in the same layered grammar as the Graph tab — source | signal & reference |
   entity | projections by order — so every fingerprint reads left to right and they
   differ by density and width, not by random shape. Without a graph yet, it shows the
   pipeline's seven steps, filled up to where the run is. Colors are tokens (ui.css). */

import { h } from "preact";
import htm from "htm";

const html = htm.bind(h);
const STEPS = ["ask", "sources", "extract", "align", "sign-off", "draft", "brief"];

/* Columns and rows, 0..1 within each column, ordered so links run as flat as they can. */
export function layoutShape(shape) {
  const { nodes, edges } = shape;
  const kind = Object.fromEntries(nodes.map((n) => [n.id, n.kind]));
  const grows = edges.filter((e) => e.kind === "growsFrom");
  const depth = {};
  const projDepth = (id, seen = new Set()) => {
    if (depth[id] != null) return depth[id];
    if (seen.has(id)) return 1;
    seen.add(id);
    const from = grows.filter((e) => e.target === id && kind[e.source] === "projection").map((e) => e.source);
    return (depth[id] = 1 + Math.max(0, ...from.map((s) => projDepth(s, seen))));
  };
  const col = (n) => ({ source: 0, signal: 1, reference: 1, entity: 2 }[n.kind] ?? 2 + projDepth(n.id));
  const cols = {};
  for (const n of nodes) (cols[col(n)] ||= []).push(n);
  const keys = Object.keys(cols).map(Number).sort((a, b) => a - b);
  const neighbours = {};
  for (const e of edges) {
    (neighbours[e.source] ||= []).push(e.target);
    (neighbours[e.target] ||= []).push(e.source);
  }
  const pos = {};
  keys.forEach((k, i) => {
    const list = cols[k];
    if (i) {
      const at = (n) => {
        const ys = (neighbours[n.id] || []).map((m) => pos[m]?.y).filter((y) => y != null);
        return ys.length ? ys.reduce((s, y) => s + y, 0) / ys.length : 0.5;
      };
      list.sort((a, b) => at(a) - at(b));
    }
    list.forEach((n, j) => (pos[n.id] = { x: i, y: (j + 0.5) / list.length }));
  });
  return { pos, columns: keys.length };
}

export function Fingerprint({ shape = null, stages = null, height = 44, label = null }) {
  if (!shape || !shape.nodes.length) {
    return html`<svg class="fp fp-steps" viewBox="0 0 140 20" style=${{ height: `${height}px` }} role="img"
      aria-label=${label || "Pipeline progress"}>
      ${STEPS.map((k, i) => html`<g key=${k}>
        ${i ? html`<line x1=${i * 20 - 12} y1="10" x2=${i * 20 + 2} y2="10" class="fp-edge" />` : null}
        <circle cx=${i * 20 + 7} cy="10" r="5" class=${`fp-step ${stages?.[k] || "pending"}`} />
      </g>`)}
    </svg>`;
  }
  const { pos, columns } = layoutShape(shape);
  const W = Math.max(columns - 1, 1) * 40 + 24;
  const H = 60;
  const X = (x) => 12 + x * 40;
  const Y = (y) => 4 + y * (H - 8);
  return html`<svg class="fp" viewBox=${`0 0 ${W} ${H}`} style=${{ height: `${height}px` }} role="img"
    aria-label=${label || `Graph shape: ${shape.nodes.length} nodes`}>
    ${shape.edges.map((e, i) => (pos[e.source] && pos[e.target]
      ? html`<line key=${i} x1=${X(pos[e.source].x)} y1=${Y(pos[e.source].y)} x2=${X(pos[e.target].x)} y2=${Y(pos[e.target].y)} class=${`fp-edge ${e.kind}`} />`
      : null))}
    ${shape.nodes.map((n) => html`<rect key=${n.id} x=${X(pos[n.id].x) - 7} y=${Y(pos[n.id].y) - 2.5} width="14" height="5" rx="1.5"
      class=${`fp-node ${n.flagged ? "flagged" : n.kind}`} />`)}
  </svg>`;
}
