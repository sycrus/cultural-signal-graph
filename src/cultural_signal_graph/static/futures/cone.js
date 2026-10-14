/* The Cone lens (Voros): nested classes opening from the present — projected ⊂
   plausible ⊂ possible, with preposterous outside — and "preferable" as a separate
   overlay (★), judged against the exploration's goal. x is time, as on the Scroll;
   each class is a band around the centre line. Drag a node into another band to
   override the model's class: the override is an attributed op. */

import { h } from "preact";
import { useLayoutEffect, useRef, useState } from "preact/hooks";
import htm from "htm";
import { lineage } from "./layout.js";
import { marksText } from "./hints.js";
import * as S from "./store.js";

const html = htm.bind(h);

export const CONE_CLASSES = ["projected", "plausible", "possible", "preposterous"];
const NODE_W = 150;
const NODE_H = 30;
const LANE = 38;
const LEFT = 120;

function packBands(snap, x) {
  /* Each class gets lanes alternating above / below the centre line; within a class
     a projection takes the first lane where it doesn't overlap a neighbour. */
  const lanes = { projected: [], plausible: [], possible: [], preposterous: [] };
  const place = {};
  const sorted = [...snap.projections].sort((a, b) => a.window[0] - b.window[0]);
  for (const p of sorted) {
    const cls = p.tags.cone?.value || "plausible";
    const x0 = x(p.window[0]);
    const band = lanes[cls];
    let i = band.findIndex((occ) => occ.every(([a, b]) => x0 > b + 8 || x0 + NODE_W < a - 8));
    if (i < 0) i = band.push([]) - 1;
    band[i].push([x0, x0 + NODE_W]);
    place[p.id] = { cls, lane: i };
  }
  return { lanes, place };
}

export function Cone({ snap, selectedId, onSelect, onRetag }) {
  const ref = useRef(null);
  const [width, setWidth] = useState(0);
  const [drag, setDrag] = useState(null); // {id, dy}
  useLayoutEffect(() => {
    setWidth(ref.current.getBoundingClientRect().width);
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  if (!width) return html`<div class="cone" ref=${ref}></div>`;

  const e = snap.exploration;
  const first = e.start_year;
  const last = e.start_year + e.horizon;
  const trackW = (width - LEFT - NODE_W - 30) * S.spread.value;
  const stageW = Math.ceil(width * S.spread.value);
  const x = (year) => LEFT + ((year - first) / Math.max(last - first, 1)) * trackW;
  const { lanes, place } = packBands(snap, x);

  // band extents (in lanes from the centre, per side): projected sits on the line
  const half = (cls) => Math.ceil(lanes[cls].length / 2);
  const ext = {};
  let acc = Math.max(lanes.projected.length, 1) / 2;
  ext.projected = [0, acc];
  for (const cls of ["plausible", "possible", "preposterous"]) {
    const start = acc + 0.35;
    acc = start + Math.max(half(cls), 1);
    ext[cls] = [start, acc];
  }
  const height = Math.max(acc * 2 * LANE + 60, 260);
  const cy = height / 2;
  const laneY = (cls, i) => {
    if (cls === "projected") return cy + (i - (lanes.projected.length - 1) / 2) * LANE;
    const [start] = ext[cls];
    const k = Math.floor(i / 2);
    const side = i % 2 === 0 ? -1 : 1;
    return cy + side * (start + k + 0.5) * LANE;
  };
  const bandOf = (y) => {
    const d = Math.abs(y - cy) / LANE;
    return CONE_CLASSES.find((cls) => d <= ext[cls][1]) || "preposterous";
  };
  const path = lineage(snap, selectedId);

  const posOf = {};
  for (const p of snap.projections) {
    const { cls, lane } = place[p.id];
    posOf[p.id] = [x(p.window[0]), laneY(cls, lane) + (drag?.id === p.id ? drag.dy : 0)];
  }
  // the cone: wedges from a narrow mouth at the present to each band's outer edge
  const wedge = (cls) => {
    const r = ext[cls][1] * LANE;
    const x0 = LEFT - 40;
    const x1 = stageW - 10;
    return `M${x0},${cy - r * 0.25} L${x1},${cy - r} L${x1},${cy + r} L${x0},${cy + r * 0.25} Z`;
  };

  const startDrag = (p) => (ev) => {
    ev.preventDefault();
    const y0 = ev.clientY;
    const baseY = laneY(place[p.id].cls, place[p.id].lane);
    let moved = false;
    const move = (m) => {
      if (Math.abs(m.clientY - y0) > 4) moved = true;
      setDrag({ id: p.id, dy: m.clientY - y0 });
    };
    const up = (u) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      setDrag(null);
      if (!moved) return onSelect(p.id);
      const target = bandOf(baseY + (u.clientY - y0));
      if (target !== (p.tags.cone?.value || "plausible")) onRetag(p, { value: target, extras: { preferable: !!p.tags.cone?.preferable } });
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  return html`<div class="cone" ref=${ref}>
    <svg width=${stageW} height=${height}>
      ${["preposterous", "possible", "plausible"].map((cls) => html`<path key=${cls} d=${wedge(cls)} class=${`cone-wedge ${cls}`} />`)}
      <line x1=${LEFT - 40} y1=${cy} x2=${stageW - 10} y2=${cy} class="cone-axis" />
      ${CONE_CLASSES.slice(1).map((cls) => html`<text key=${cls} x=${stageW - 16} y=${cy - ext[cls][1] * LANE + 14} text-anchor="end" class="cone-label">${cls}</text>`)}
      <text x=${stageW - 16} y=${cy - 6} text-anchor="end" class="cone-label">projected</text>
      <text x=${LEFT - 44} y=${cy + 4} text-anchor="end" class="cone-label present">present</text>
      ${snap.projections.flatMap((p) =>
        p.parents.filter((q) => posOf[q]).map((q) => {
          const [x1, y1] = posOf[q];
          const [x2, y2] = posOf[p.id];
          return html`<path key=${`${q}>${p.id}`} d=${`M${x1 + NODE_W},${y1} C${x1 + NODE_W + 30},${y1} ${x2 - 30},${y2} ${x2},${y2}`}
            class=${`edge ${path.has(q) && path.has(p.id) ? "lit" : path.size ? "faded" : ""}`} />`;
        }),
      )}
    </svg>
    ${snap.projections.map((p) => {
      const [nx, ny] = posOf[p.id];
      const tag = p.tags.cone;
      const marks = marksText(p);
      return html`<div key=${p.id}
        class=${`cone-node ${tag?.value || "untagged"} ${p.origin} ${selectedId === p.id ? "selected" : ""} ${path.size && !path.has(p.id) ? "faded" : ""} ${drag?.id === p.id ? "dragging" : ""}`}
        style=${{ left: `${nx}px`, top: `${ny - NODE_H / 2}px`, width: `${NODE_W}px`, height: `${NODE_H}px` }}
        onPointerDown=${startDrag(p)} title=${`${marks ? marks + "\n" : ""}${p.statement}\n${tag ? `${tag.value}${tag.source === "human" ? " (set by you)" : ""}` : "untagged"} — drag to another band to re-class`}>
        ${tag?.preferable ? html`<span class="pref" title="Preferable: serves the goal">★</span>` : null}
        ${tag?.source === "human" ? html`<span class="by-you" title="Set by you">✎</span>` : null}
        <span class="cone-text">${p.statement}</span>
      </div>`;
    })}
  </div>`;
}
