/* Futures mode state: one signal-backed store every view reads from (PRD-futures.md).
   The server's exploration snapshot is the single source of truth; actions call the
   JSON API and replace the snapshot. */

import { signal, computed } from "@preact/signals";

export const runId = signal(new URLSearchParams(location.search).get("run"));
export const run = signal(null); // the forecast run snapshot (ask, status)
export const anchors = signal([]); // the run's available anchors
export const explorations = signal([]); // this run's explorations (summaries)
export const snap = signal(null); // the open exploration's snapshot
export const view = signal("list"); // "list" | "new" | "exploration"
export const busy = signal(false);
export const error = signal(null);
export const draft = signal(null); // prefill for the new-exploration form
export const selectedId = signal(null); // the projection open in the detail panel

export const projectionsById = computed(() =>
  Object.fromEntries((snap.value?.projections || []).map((p) => [p.id, p])),
);
export const anchorsById = computed(() =>
  Object.fromEntries((snap.value?.anchors || anchors.value).map((a) => [a.id, a])),
);

export async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

const base = () => `/api/runs/${runId.value}`;

function setUrl(expId) {
  const q = new URLSearchParams({ run: runId.value });
  if (expId) q.set("x", expId);
  history.replaceState(null, "", `/futures?${q}`);
}

async function guarded(fn) {
  busy.value = true;
  error.value = null;
  try {
    await fn();
  } catch (err) {
    error.value = String(err.message || err);
  } finally {
    busy.value = false;
  }
}

export async function load() {
  if (!runId.value) {
    error.value = "Open Futures from a forecast run.";
    return;
  }
  await guarded(async () => {
    run.value = await api(base());
    anchors.value = await api(`${base()}/futures/anchors`);
    explorations.value = await api(`${base()}/explorations`);
    const expId = new URLSearchParams(location.search).get("x");
    if (expId) await openExploration(expId);
  });
}

export async function openExploration(expId) {
  snap.value = await api(`${base()}/explorations/${expId}`);
  selectedId.value = null;
  view.value = "exploration";
  setUrl(expId);
}

export function showList() {
  view.value = "list";
  snap.value = null;
  setUrl(null);
  guarded(async () => {
    explorations.value = await api(`${base()}/explorations`);
  });
}

export function newExploration(prefill = null) {
  draft.value = prefill;
  error.value = null;
  view.value = "new";
}

export const generating = signal(false);
export const stopping = signal(false);

async function streamGeneration(expId) {
  /* Live fill: one SSE event per order, read from a POST response stream. If the
     connection drops, the log already holds every finished order — re-sync. */
  generating.value = true;
  stopping.value = false;
  error.value = null;
  try {
    const res = await fetch(`${base()}/explorations/${expId}/generate/stream`, { method: "POST" });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `${res.status} ${res.statusText}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let cut;
      while ((cut = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, cut);
        buffer = buffer.slice(cut + 2);
        const event = /^event: (.*)$/m.exec(block)?.[1];
        const data = JSON.parse(/^data: (.*)$/m.exec(block)?.[1] || "{}");
        if (event === "error") error.value = data.detail;
        else if (snap.value?.exploration.id === expId) snap.value = data;
      }
    }
  } catch (err) {
    error.value = String(err.message || err);
  } finally {
    generating.value = false;
    stopping.value = false;
    if (snap.value?.exploration.id === expId) {
      snap.value = await api(`${base()}/explorations/${expId}`).catch(() => snap.value);
    }
  }
}

export async function createAndGenerate(body) {
  await guarded(async () => {
    const created = await api(`${base()}/explorations`, { method: "POST", body });
    snap.value = created;
    view.value = "exploration";
    setUrl(created.exploration.id);
  });
  if (snap.value) await streamGeneration(snap.value.exploration.id);
}

export async function continueGeneration() {
  await streamGeneration(snap.value.exploration.id);
}

export async function stopGeneration() {
  stopping.value = true;
  try {
    await api(`${base()}/explorations/${snap.value.exploration.id}/stop`, { method: "POST" });
  } catch (err) {
    error.value = String(err.message || err);
  }
}

export async function fetchOp(seq) {
  return api(`${base()}/explorations/${snap.value.exploration.id}/ops/${seq}`);
}
