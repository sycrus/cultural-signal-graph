/* Scroll layout: x is time (each projection at its window start), y is a lane.

   Lanes are packed greedily so a projection sits as close as possible to the mean
   lane of what it grows from (a barycenter heuristic: crossings are minimized, not
   eliminated). Lanes are computed once against the *full* horizon, so they stay put
   while the strategist slides the visible window — zooming in only adds room. */

export function lineage(snap, id) {
  /* A projection's ancestors and descendants (plus itself): the path to highlight. */
  if (!id) return new Set();
  const byId = Object.fromEntries(snap.projections.map((p) => [p.id, p]));
  const children = {};
  for (const p of snap.projections) {
    for (const src of [...p.parents, ...p.anchors]) (children[src] ||= []).push(p.id);
  }
  const out = new Set([id]);
  const up = [id];
  while (up.length) {
    const p = byId[up.pop()];
    if (!p) continue;
    for (const src of [...p.parents, ...p.anchors]) {
      if (!out.has(src)) {
        out.add(src);
        up.push(src);
      }
    }
  }
  const down = [id];
  while (down.length) {
    for (const c of children[down.pop()] || []) {
      if (!out.has(c)) {
        out.add(c);
        down.push(c);
      }
    }
  }
  return out;
}

export function layoutLanes(snap, { pxPerYear, cardW, gap = 14, laneKey = null }) {
  /* -> { lane: {id: laneIndex}, count }. `laneKey(p)` optionally groups projections
     into swimlanes (e.g. PESTLE primary); lanes are then packed within each group. */
  const lane = {};
  snap.anchors.forEach((a, i) => (lane[a.id] = i));
  const occupied = []; // lane -> [[x0, x1], ...]
  const free = (l, x0, x1) => !(occupied[l] || []).some(([a, b]) => x0 < b + gap && a < x1 + gap);
  const order = [...snap.projections].sort(
    (a, b) => a.window[0] - b.window[0] || a.order - b.order || (a.id < b.id ? -1 : 1),
  );
  const start = snap.exploration.start_year;
  for (const p of order) {
    const sources = [...p.parents, ...p.anchors].filter((s) => s in lane);
    const desired = sources.length
      ? Math.round(sources.reduce((sum, s) => sum + lane[s], 0) / sources.length)
      : 0;
    const x0 = (p.window[0] - start) * pxPerYear;
    const x1 = x0 + cardW;
    let chosen = null;
    for (let d = 0; chosen === null; d++) {
      for (const l of d === 0 ? [desired] : [desired + d, desired - d]) {
        if (l >= 0 && free(l, x0, x1)) {
          chosen = l;
          break;
        }
      }
    }
    (occupied[chosen] ||= []).push([x0, x1]);
    lane[p.id] = chosen;
  }
  const count = Math.max(snap.anchors.length, ...Object.values(lane).map((l) => l + 1), 1);
  if (laneKey) return groupLanes(snap, lane, laneKey);
  return { lane, count };
}

function groupLanes(snap, lane, laneKey) {
  /* Swimlanes: each group gets a band; within a band, keep the packed relative order. */
  const groups = {};
  for (const p of snap.projections) (groups[laneKey(p)] ||= []).push(p);
  const out = {};
  snap.anchors.forEach((a, i) => (out[a.id] = i));
  const bands = [];
  let next = 0;
  for (const key of Object.keys(groups).sort()) {
    const ps = groups[key].sort((a, b) => lane[a.id] - lane[b.id]);
    const distinct = [...new Set(ps.map((p) => lane[p.id]))];
    for (const p of ps) out[p.id] = next + distinct.indexOf(lane[p.id]);
    bands.push({ key, from: next, to: next + distinct.length });
    next += distinct.length;
  }
  return { lane: out, count: Math.max(next, snap.anchors.length, 1), bands };
}
