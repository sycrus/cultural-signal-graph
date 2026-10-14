/* The Scroll — the base view of an exploration (PRD-futures.md §4).

   x = time; the Present column on the left holds the anchors. A minimap below with
   two rollers picks the visible years; an order filter picks causal depth. Projections
   outside the window roll up at the edges with a count. Cards slide (CSS transitions)
   as the window moves — the handscroll governs transitions, not textures. */

import { h } from "preact";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "preact/hooks";
import htm from "htm";
import { layoutLanes, lineage } from "./layout.js";

const html = htm.bind(h);
const d3 = window.d3;

const PRESENT_W = 236;
const CARD_W = 196;
const CARD_H = 58;
const LANE_H = 76;
const TOP = 34; // the year axis
const MINI_H = 46;

function useWidth(ref) {
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    // measure before first paint, so cards don't slide in from a guessed width
    setWidth(ref.current.getBoundingClientRect().width);
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return width;
}

export function Scroll({ snap, selectedId, onSelect, laneKey = null, laneLabel = null, dimmed = () => false, onLaneDrop = null, chips = null }) {
  const ref = useRef(null);
  const width = useWidth(ref);
  const e = snap.exploration;
  const first = e.start_year;
  const last = e.start_year + e.horizon;
  const orders = [...new Set(snap.projections.map((p) => p.order))].sort((a, b) => a - b);

  const [range, setRange] = useState([first, last]);
  const [shownOrders, setShownOrders] = useState(null); // null = all
  const [drag, setDrag] = useState(null); // {id, dy} while moving a card between swimlanes
  useEffect(() => setRange([first, last]), [e.id]);

  const trackW = Math.max(width - PRESENT_W - CARD_W - 24, 200);
  const { lane, count, bands } = useMemo(
    () => layoutLanes(snap, { pxPerYear: trackW / Math.max(e.horizon, 1), cardW: CARD_W, laneKey }),
    [snap, trackW, laneKey],
  );

  const span = Math.max(range[1] - range[0], 1);
  const x = (year) => PRESENT_W + 12 + ((year - range[0]) / span) * trackW;
  const y = (l) => TOP + l * LANE_H;

  const orderShown = (p) => !shownOrders || shownOrders.has(p.order);
  const inRange = (p) => p.window[1] >= range[0] && p.window[0] <= range[1];
  const rolledLeft = snap.projections.filter((p) => orderShown(p) && p.window[1] < range[0]).length;
  const rolledRight = snap.projections.filter((p) => orderShown(p) && p.window[0] > range[1]).length;
  const visible = new Set(snap.projections.filter((p) => orderShown(p) && inRange(p)).map((p) => p.id));
  const path = lineage(snap, selectedId);
  const anchorIds = new Set(snap.anchors.map((a) => a.id));

  const link = d3.linkHorizontal();
  const edges = [];
  for (const p of snap.projections) {
    if (!visible.has(p.id)) continue;
    for (const src of [...p.parents, ...p.anchors]) {
      const fromAnchor = anchorIds.has(src);
      if (!fromAnchor && !visible.has(src)) continue;
      const srcP = snap.projections.find((q) => q.id === src);
      const sx = fromAnchor ? PRESENT_W - 6 : x(srcP.window[0]) + CARD_W;
      const sy = y(lane[src]) + CARD_H / 2;
      const tx = x(p.window[0]);
      const ty = y(lane[p.id]) + CARD_H / 2;
      edges.push({
        key: `${src}>${p.id}`,
        d: link({ source: [sx, sy], target: [tx, ty] }),
        baseline: p.baseline && (fromAnchor || srcP.baseline),
        lit: path.has(src) && path.has(p.id),
      });
    }
  }

  const years = [];
  const step = span > 14 ? 2 : 1;
  for (let yr = Math.ceil(range[0]); yr <= range[1]; yr += step) years.push(yr);
  const height = TOP + count * LANE_H + 8;

  if (!width) return html`<div class="scroll" ref=${ref}></div>`;
  return html`<div class="scroll" ref=${ref}>
    <div class="scroll-tools">
      <span class="hint">orders</span>
      ${orders.map(
        (o) => html`<button key=${o} class=${`chip ${!shownOrders || shownOrders.has(o) ? "on" : ""}`}
          onClick=${() => {
            const next = new Set(shownOrders || orders);
            next.has(o) ? next.delete(o) : next.add(o);
            setShownOrders(next.size === orders.length ? null : next);
          }}>${o}</button>`,
      )}
      <span class="spacer"></span>
      <span class="hint">${range[0]}–${range[1]}</span>
      ${range[0] !== first || range[1] !== last
        ? html`<button class="ghost" onClick=${() => setRange([first, last])}>Unroll all</button>`
        : null}
    </div>
    <div class="scroll-stage" style=${{ height: `${height}px` }}>
      <div class="present-col" style=${{ width: `${PRESENT_W}px` }}>
        <div class="axis-label">Present</div>
      </div>
      ${bands
        ? bands.map(
            (b) => html`<div key=${b.key} class="band" style=${{ top: `${y(b.from) - 6}px`, height: `${(b.to - b.from) * LANE_H}px`, left: `${PRESENT_W}px` }}>
              <span class="band-label">${laneLabel ? laneLabel(b.key) : b.key}</span></div>`,
          )
        : null}
      ${years.map(
        (yr) => html`<div key=${yr} class="tick" style=${{ left: `${x(yr)}px` }}><span>${yr}</span></div>`,
      )}
      <svg class="edges" width=${width} height=${height}>
        ${edges.map(
          (ed) => html`<path key=${ed.key} d=${ed.d} class=${`edge ${ed.baseline ? "baseline" : ""} ${ed.lit ? "lit" : ""} ${path.size && !ed.lit ? "faded" : ""}`} />`,
        )}
      </svg>
      ${snap.anchors.map(
        (a) => html`<div key=${a.id} class=${`anchor-card ${a.kind} ${a.pending ? "pending" : ""} ${a.status === "rejected" ? "rejected" : ""} ${path.size && !path.has(a.id) ? "faded" : ""}`}
          style=${{ top: `${y(lane[a.id])}px`, width: `${PRESENT_W - 18}px`, height: `${CARD_H}px` }}
          title=${a.text} onClick=${() => onSelect(a.id)}>
          <span class="anchor-kind-dot"></span>${a.text}
        </div>`,
      )}
      ${snap.projections.map((p) => {
        const shown = visible.has(p.id);
        const left = shown ? x(p.window[0]) : p.window[1] < range[0] ? PRESENT_W : width;
        const barW = Math.max(((p.window[1] + 1 - p.window[0]) / span) * trackW, 6);
        const top = y(lane[p.id]) + (drag?.id === p.id ? drag.dy : 0);
        const laneDrag = bands && onLaneDrop
          ? (ev) => {
              ev.preventDefault();
              const y0 = ev.clientY;
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
                const target = Math.round((y(lane[p.id]) + u.clientY - y0 - TOP) / LANE_H);
                const band = bands.find((b) => target >= b.from && target < b.to) || (target < 0 ? bands[0] : bands[bands.length - 1]);
                if (band && band.key !== laneKey(p)) onLaneDrop(p, band.key);
              };
              window.addEventListener("pointermove", move);
              window.addEventListener("pointerup", up);
            }
          : null;
        return html`<div key=${p.id}
          class=${`proj-node ${p.baseline ? "baseline" : ""} ${p.discontinuity ? "discontinuity" : ""} ${p.stale ? "stale" : ""} ${p.origin} ${selectedId === p.id ? "selected" : ""} ${path.size && !path.has(p.id) ? "faded" : ""} ${dimmed(p) ? "dimmed" : ""} ${shown ? "" : "rolled"}`}
          style=${{ left: `${left}px`, top: `${top}px`, width: `${CARD_W}px`, height: `${CARD_H}px`, ...(drag?.id === p.id ? { transition: "none", zIndex: 4, cursor: "grabbing" } : {}) }}
          onPointerDown=${laneDrag} onClick=${laneDrag ? null : () => onSelect(p.id)} title=${p.statement}>
          <div class="proj-meta">
            <span class="order-badge">${p.order}</span>
            <span class="years">${p.window[0] === p.window[1] ? p.window[0] : `${p.window[0]}–${p.window[1]}`}</span>
            ${p.timing_conflict ? html`<span class="warn-mark" title="Timing conflict: starts before what it grows from">⚠</span>` : null}
            ${p.stale ? html`<span class="stale-mark" title="Stale: an ancestor or anchor changed after this was generated">stale</span>` : null}
            ${p.parents.length + p.anchors.length > 1 ? html`<span class="converge-mark" title="Convergence">⋈</span>` : null}
            ${chips ? chips(p) : null}
          </div>
          <div class="proj-text">${p.statement}</div>
          <div class="window-bar" style=${{ width: `${Math.min(barW, CARD_W)}px` }}></div>
        </div>`;
      })}
      ${rolledLeft ? html`<div class="rolled-count left" style=${{ left: `${PRESENT_W + 2}px` }}>◀ ${rolledLeft}</div>` : null}
      ${rolledRight ? html`<div class="rolled-count right">${rolledRight} ▶</div>` : null}
    </div>
    <${Minimap} snap=${snap} lane=${lane} count=${count} range=${range} setRange=${setRange} width=${width} />
  </div>`;
}

function Minimap({ snap, lane, count, range, setRange, width }) {
  const e = snap.exploration;
  const first = e.start_year;
  const last = e.start_year + e.horizon;
  const left = PRESENT_W;
  const w = Math.max(width - left - 12, 100);
  const mx = (year) => left + ((year - first) / Math.max(last - first, 1)) * w;
  const toYear = (px) => Math.round(first + ((px - left) / w) * (last - first));
  const ref = useRef(null);

  const drag = (which) => (ev) => {
    ev.preventDefault();
    const box = ref.current.getBoundingClientRect();
    const move = (m) => {
      const yr = Math.min(last, Math.max(first, toYear(m.clientX - box.left)));
      setRange((r) => {
        if (which === "start") return [Math.min(yr, r[1] - 1), r[1]];
        if (which === "end") return [r[0], Math.max(yr, r[0] + 1)];
        const len = r[1] - r[0];
        const s = Math.min(last - len, Math.max(first, yr - Math.round(len / 2)));
        return [s, s + len];
      });
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  return html`<div class="minimap" ref=${ref} style=${{ height: `${MINI_H}px` }}>
    <span class="hint minimap-label">visible years</span>
    ${snap.projections.map(
      (p) => html`<span key=${p.id} class=${`mini-dot ${p.baseline ? "baseline" : ""}`}
        style=${{ left: `${mx(p.window[0])}px`, top: `${6 + (lane[p.id] / Math.max(count, 1)) * (MINI_H - 14)}px` }}></span>`,
    )}
    <div class="mini-window" style=${{ left: `${mx(range[0])}px`, width: `${mx(range[1]) - mx(range[0])}px` }}
      onPointerDown=${drag("move")}>
      <span class="roller start" onPointerDown=${(ev) => { ev.stopPropagation(); drag("start")(ev); }} title="Drag to roll"></span>
      <span class="roller end" onPointerDown=${(ev) => { ev.stopPropagation(); drag("end")(ev); }} title="Drag to roll"></span>
    </div>
  </div>`;
}
