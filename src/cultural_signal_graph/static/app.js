/* Cultural Signal Graph — stepper UI.
   Left rail of stages; the canvas shows the active stage. Talk to the JSON API. */

const RAIL_STAGES = [
  { key: "ask", label: "Ask" },
  { key: "sources", label: "Sources" },
  { key: "run", label: "Run" },
  { key: "sign-off", label: "Sign-off" },
  { key: "brief", label: "Brief" },
  { key: "graph", label: "Graph" },
  { key: "metrics", label: "Metrics" },
];

const RUN_STAGES = ["extract", "align", "sign-off", "draft", "brief"];

const state = {
  view: "home",
  runId: null,
  snap: null,
  runs: [],
  busy: false,
  error: null,
  signoffDraft: {}, // edge id -> true(approve) | false(reject), before confirming
};

async function api(path, opts = {}) {
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

/* --- rail ------------------------------------------------------------- */

/* Derive each rail item's state from the run snapshot: done / action (blocks) /
   active / current (you are here) / blocked (upstream not finished). */
function railStates(snap) {
  if (!snap) return Object.fromEntries(RAIL_STAGES.map((s) => [s.key, "blocked"]));
  const st = snap.stages || {};
  const done = (k) => st[k] && st[k].status === "done";
  const pipelineStarted = snap.status !== "created";
  return {
    ask: "done",
    sources: "done",
    run: done("draft") ? "done" : pipelineStarted ? "active" : "blocked",
    "sign-off": done("sign-off")
      ? "done"
      : snap.status === "paused"
        ? "action"
        : done("draft")
          ? "done"
          : "blocked",
    brief: snap.status === "completed" ? "done" : done("draft") ? "active" : "blocked",
    graph: snap.status === "completed" ? "active" : "blocked",
    metrics: snap.status === "completed" ? "active" : "blocked",
  };
}

function renderRail() {
  const rail = document.getElementById("rail");
  const states = railStates(state.snap);
  const firstOpen = RAIL_STAGES.find((s) => states[s.key] !== "done");
  rail.innerHTML = "";
  for (const stage of RAIL_STAGES) {
    const cls = states[stage.key];
    const item = document.createElement("button");
    item.className = `rail-item ${cls}`;
    if (stage.key === firstOpen?.key && cls !== "action") item.classList.add("current");
    if (cls === "action") item.classList.add("current");
    if (cls === "active" || cls === "done") {
      item.addEventListener("click", () => showStage(stage.key));
    }
    const dot = document.createElement("span");
    dot.className = "dot";
    item.append(dot, document.createTextNode(stage.label));
    rail.append(item);
  }
}

function showStage(key) {
  if (!state.snap) return;
  state.view = key;
  state.error = null;
  render();
}

/* --- canvas views ------------------------------------------------------ */

function renderHome() {
  const rows = state.runs
    .map(
      (r) => `<tr data-run="${r.id}">
        <td>${r.id}</td>
        <td>${escapeHtml(r.ask.category)} — ${escapeHtml(r.ask.question)}</td>
        <td><span class="status ${r.status}">${r.status}</span></td>
        <td>${r.created_at.replace("T", " ").slice(0, 16)}</td>
      </tr>`,
    )
    .join("");
  return `
  <div class="canvas-narrow">
    <h1>Forecast runs</h1>
    <p class="lede">Start a forecast by entering an ask — or reopen a past run to
    audit its brief, graph, and metrics.</p>
    <div class="card" style="display:flex; align-items:center; gap:14px">
      <button class="primary" id="btn-new-run">New run</button>
      <span class="hint">Category, question, window, market.</span>
    </div>
    <h2>Past runs</h2>
    <div class="card" style="padding:0">
      <table>
        <thead><tr><th>Run</th><th>Ask</th><th>Status</th><th>Created</th></tr></thead>
        <tbody>${rows || `<tr><td colspan="4" style="color:var(--muted)">No runs yet.</td></tr>`}</tbody>
      </table>
    </div>
  </div>`;
}

function renderAsk() {
  return `
  <div class="canvas-narrow">
    <h1>Ask</h1>
    <p class="lede">What should the forecast cover? The ask drives source discovery
    and selects the sub-ontology to reason over.</p>
    <div class="card">
      <label for="ask-category">Category</label>
      <input id="ask-category" list="categories" value="tech">
      <datalist id="categories">
        <option value="tech"></option>
        <option value="gaming"></option>
      </datalist>
      <div class="hint">An unfamiliar category is backfilled from the live web.</div>

      <label for="ask-question">Question</label>
      <input id="ask-question" placeholder="AI wearables adoption">

      <label>Window</label>
      <div style="display:flex; gap:8px; align-items:center">
        <input id="ask-start" type="date" value="2026-01-01" style="flex:1">
        <span>→</span>
        <input id="ask-end" type="date" value="2026-06-30" style="flex:1">
      </div>

      <label for="ask-market">Market <span style="font-weight:400; color:var(--muted)">(optional)</span></label>
      <input id="ask-market" list="markets" placeholder="SEA">
      <datalist id="markets"><option value="SEA"></option></datalist>

      ${state.error ? `<div class="error">${escapeHtml(state.error)}</div>` : ""}
      <div style="margin-top:16px; text-align:right">
        <button class="primary" id="btn-submit-ask">Run →</button>
      </div>
    </div>
  </div>`;
}

function shortUri(uri) {
  try {
    const u = new URL(uri);
    return u.hostname + (u.pathname.length > 1 ? "/…" : "");
  } catch {
    return uri;
  }
}

function shortType(sourceType) {
  return sourceType.split("#").pop();
}

function renderSources() {
  const s = state.snap;
  const rows = s.sources
    .map(
      (src, i) => `<tr data-index="${i}">
        <td title="${escapeHtml(src.uri)}">${escapeHtml(shortUri(src.uri))}</td>
        <td>${escapeHtml(shortType(src.source_type))}</td>
        <td>${src.credibility}</td>
        <td style="max-width:260px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap">${escapeHtml(src.text)}</td>
        <td><button class="ghost" data-remove="${i}">✕</button></td>
      </tr>`,
    )
    .join("");
  return `
  <div class="canvas-narrow">
    <h1>Sources</h1>
    <p class="lede">Discovered for “${escapeHtml(s.ask.question)}”. Auditable by
    default — expand to review or override before extraction runs.</p>
    <details class="card" ${s.sources.length === 0 ? "open" : ""}>
      <summary>${s.sources.length} source${s.sources.length === 1 ? "" : "s"}</summary>
      <table>
        <thead><tr><th>Source</th><th>Type</th><th>Credibility</th><th>Text</th><th></th></tr></thead>
        <tbody>${rows || `<tr><td colspan="5" style="color:var(--muted)">None — add one below.</td></tr>`}</tbody>
      </table>
      <div style="display:flex; gap:8px; margin-top:12px">
        <input id="add-uri" placeholder="https://… (source URI)" style="flex:2">
        <input id="add-text" placeholder="What it says" style="flex:3">
        <button id="btn-add-source">+ Add</button>
      </div>
    </details>
    ${state.error ? `<div class="error">${escapeHtml(state.error)}</div>` : ""}
    <div style="display:flex; justify-content:space-between; margin-top:14px">
      <button id="btn-reset-sources">Reset to discovered</button>
      <button class="primary" id="btn-start-run" ${s.sources.length === 0 ? "disabled" : ""}>Start run →</button>
    </div>
  </div>`;
}

function stageChip(name, st) {
  const done = st && st.status === "done";
  const paused = st && st.status === "paused";
  const mark = done ? "✓" : paused ? "…" : "·";
  const metric = done ? `${st.tokens} tok · ${fmtDuration(st.latency_ms)}` : "";
  return `<span class="stage-chip ${done ? "done" : paused ? "paused" : ""}">
    ${name} ${mark}${metric ? ` <small>${metric}</small>` : ""}</span>`;
}

function renderRun() {
  const s = state.snap;
  const chips = RUN_STAGES.map((name) => stageChip(name, s.stages[name])).join("");
  if (state.busy) {
    return `
    <div class="canvas-narrow">
      <h1>Run</h1>
      <p class="lede">Extracting signals and proposing cross-domain edges…</p>
      <div class="card run-busy"><span class="spinner"></span> ${chips}</div>
    </div>`;
  }
  return `
  <div class="canvas-narrow">
    <h1>Run</h1>
    <p class="lede">Per-stage tokens and latency, recorded at each stage boundary.</p>
    <div class="card" style="display:flex; gap:8px; flex-wrap:wrap">${chips}</div>
    ${state.error ? `<div class="error">${escapeHtml(state.error)}</div>` : ""}
  </div>`;
}

function renderSignOff() {
  const s = state.snap;
  const undoable = s.status === "completed" && Object.keys(s.decisions || {}).length > 0;
  if (s.status !== "paused" && !undoable) {
    return renderPlaceholder(
      "Sign-off",
      "No cross-domain edges were proposed for this run, so nothing needed a decision.",
    );
  }

  if (undoable) {
    const rows = Object.entries(s.decisions)
      .map(([id, approved]) => {
        const edge = (s.pending || []).find((e) => e.id === id);
        const label = edge ? `${escapeHtml(edge.left)} ≈ ${escapeHtml(edge.right)}` : id;
        return `<div class="edge-card decided">
          <div class="edge-head">${label}</div>
          <div class="edge-verdict ${approved ? "approved" : "rejected"}">
            ${approved ? "✓ approved — asserted as real" : "✕ rejected — dropped"}</div>
        </div>`;
      })
      .join("");
    return `
    <div class="canvas-narrow">
      <h1>Sign-off</h1>
      <p class="lede">Your decision is recorded but stays editable until you export.
      Undoing re-runs the downstream (draft → brief) and parks the run back here.</p>
      ${rows}
      ${state.error ? `<div class="error">${escapeHtml(state.error)}</div>` : ""}
      <div style="margin-top:14px">
        <button id="btn-undo-signoff">Undo sign-off &amp; re-decide</button>
      </div>
    </div>`;
  }

  const decided = state.signoffDraft || {};
  const all = s.pending.every((e) => e.id in decided);
  const cards = s.pending
    .map(
      (e) => `
    <div class="edge-card">
      <div class="edge-head">${escapeHtml(e.left)} <span class="approx">≈</span> ${escapeHtml(e.right)}</div>
      <div class="edge-meta">confidence ${e.confidence} · ${escapeHtml(e.left_category)} ⇄ ${escapeHtml(e.right_category)}</div>
      <div class="edge-actions">
        <button class="${decided[e.id] === true ? "primary" : ""}" data-decide="${e.id}" data-value="true"
          ${decided[e.id] === false ? "disabled" : ""}>✓ Approve</button>
        <button class="${decided[e.id] === false ? "danger-active" : ""}" data-decide="${e.id}" data-value="false"
          ${decided[e.id] === true ? "disabled" : ""}>✕ Reject</button>
        ${e.id in decided ? `<span class="edge-verdict ${decided[e.id] ? "approved" : "rejected"}">your call: ${decided[e.id] ? "real" : "dropped"} — reversible until export</span>` : ""}
      </div>
    </div>`,
    )
    .join("");
  return `
  <div class="canvas-narrow">
    <h1>Sign-off</h1>
    <p class="lede">The run is <b>paused</b> until you decide. Approving asserts a
    cross-domain link as real; rejecting drops it and keeps the categories separate.</p>
    <p class="review-count">◉ Review ${s.pending.length} cross-domain link${s.pending.length === 1 ? "" : "s"}</p>
    ${cards}
    ${state.error ? `<div class="error">${escapeHtml(state.error)}</div>` : ""}
    <div style="margin-top:14px; display:flex; gap:10px; align-items:center">
      <button class="primary" id="btn-confirm-signoff" ${all && !state.busy ? "" : "disabled"}>
        ${state.busy ? "Resuming the run…" : "Confirm sign-off →"}</button>
      ${all ? "" : `<span class="hint">Decide every proposed link to resume the run.</span>`}
    </div>
  </div>`;
}

function renderPlaceholder(title, note) {
  return `<div class="canvas-narrow">
    <h1>${title}</h1>
    <p class="lede">${note}</p>
  </div>`;
}

const VIEWS = {
  home: renderHome,
  ask: renderAsk,
  sources: renderSources,
  run: renderRun,
  "sign-off": renderSignOff,
  brief: () => renderPlaceholder("Brief", "The brief review surface lands with the brief step."),
  graph: () => renderPlaceholder("Graph", "The graph explorer lands with the graph step."),
  metrics: () => renderPlaceholder("Metrics", "Eval scores, cost, and prediction accuracy land with the metrics step."),
};

function render() {
  document.getElementById("btn-runs").hidden = state.view === "home";
  const badge = document.getElementById("mode-badge");
  if (state.snap) {
    badge.hidden = state.snap.mode !== "fixture";
    badge.textContent = "fixture mode";
  } else {
    badge.hidden = true;
  }
  document.getElementById("canvas").innerHTML = (VIEWS[state.view] || renderHome)();
  bind();
  renderRail();
}

function bind() {
  document.getElementById("canvas").querySelectorAll("tr[data-run]").forEach((tr) => {
    tr.addEventListener("click", () => openRun(tr.dataset.run));
  });
  const on = (id, event, handler) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener(event, handler);
  };

  on("btn-new-run", "click", () => {
    state.view = "ask";
    state.error = null;
    render();
  });
  on("btn-submit-ask", "click", submitAsk);
  on("ask-question", "keydown", (e) => {
    if (e.key === "Enter") submitAsk();
  });
  on("btn-add-source", "click", addSource);
  on("btn-reset-sources", "click", async () => {
    try {
      state.snap = await api(`/api/runs/${state.runId}/sources/reset`, { method: "POST" });
      render();
    } catch (err) {
      state.error = String(err.message || err);
      render();
    }
  });
  on("btn-start-run", "click", startRun);
  document.querySelectorAll("button[data-remove]").forEach((btn) => {
    btn.addEventListener("click", () => removeSource(Number(btn.dataset.remove)));
  });
  document.querySelectorAll("button[data-decide]").forEach((btn) => {
    btn.addEventListener("click", () => decide(btn.dataset.decide, btn.dataset.value === "true"));
  });
  on("btn-confirm-signoff", "click", confirmSignoff);
  on("btn-undo-signoff", "click", undoSignoff);
}

/* --- actions ------------------------------------------------------------ */

async function submitAsk() {
  const body = {
    category: val("ask-category") || "tech",
    question: val("ask-question"),
    window_start: val("ask-start") || "2026-01-01",
    window_end: val("ask-end") || "2026-06-30",
    market: val("ask-market") || null,
  };
  if (!body.question.trim()) {
    state.error = "Enter a question for the forecast.";
    render();
    return;
  }
  try {
    state.snap = await api("/api/runs", { method: "POST", body });
    state.runId = state.snap.id;
    state.view = "sources";
    state.error = null;
  } catch (err) {
    state.error = String(err.message || err);
  }
  render();
}

async function addSource() {
  const uri = val("add-uri").trim();
  const text = val("add-text").trim();
  if (!uri || !text) return;
  const sources = state.snap.sources.concat([
    {
      uri,
      text,
      source_type: "https://cultural-signal-graph.dev/ontology#Source",
      credibility: 0.6,
      category: state.snap.ask.category,
      topics: [],
    },
  ]);
  await putSources(sources);
}

async function removeSource(index) {
  const sources = state.snap.sources.filter((_, i) => i !== index);
  await putSources(sources);
}

async function putSources(sources) {
  try {
    state.snap = await api(`/api/runs/${state.runId}/sources`, {
      method: "PUT",
      body: { sources },
    });
    state.error = null;
  } catch (err) {
    state.error = String(err.message || err);
  }
  render();
}

async function startRun() {
  state.view = "run";
  state.busy = true;
  state.error = null;
  state.signoffDraft = {};
  render();
  try {
    state.snap = await api(`/api/runs/${state.runId}/start`, { method: "POST" });
    state.busy = false;
    state.view = currentStage(state.snap);
  } catch (err) {
    state.busy = false;
    state.error = String(err.message || err);
  }
  render();
}

async function openRun(runId) {
  state.snap = await api(`/api/runs/${runId}`);
  state.runId = runId;
  state.signoffDraft = {};
  state.view = currentStage(state.snap);
  render();
}

/* --- sign-off ------------------------------------------------------------ */

function decide(edgeId, approved) {
  state.signoffDraft = { ...state.signoffDraft, [edgeId]: approved };
  render();
}

async function confirmSignoff() {
  state.busy = true;
  state.error = null;
  render();
  try {
    state.snap = await api(`/api/runs/${state.runId}/signoff`, {
      method: "POST",
      body: { decisions: state.signoffDraft },
    });
    state.signoffDraft = {};
    state.view = currentStage(state.snap);
  } catch (err) {
    state.error = String(err.message || err);
  }
  state.busy = false;
  render();
}

async function undoSignoff() {
  try {
    state.snap = await api(`/api/runs/${state.runId}/signoff/undo`, { method: "POST" });
    state.signoffDraft = {};
    state.view = "sign-off";
    state.error = null;
  } catch (err) {
    state.error = String(err.message || err);
  }
  render();
}

function currentStage(snap) {
  const states = railStates(snap);
  const action = RAIL_STAGES.find((s) => states[s.key] === "action");
  if (action) return action.key;
  const firstOpen = RAIL_STAGES.find((s) => states[s.key] === "active");
  return firstOpen ? firstOpen.key : "brief";
}

async function goHome() {
  state.runs = await api("/api/runs");
  state.view = "home";
  state.snap = null;
  state.runId = null;
  state.error = null;
  render();
}

document.getElementById("btn-runs").addEventListener("click", goHome);
goHome();

/* --- helpers ------------------------------------------------------------ */

function val(id) {
  const el = document.getElementById(id);
  return el ? el.value : "";
}

function fmtDuration(ms) {
  if (ms == null) return "";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}
