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

const state = { view: "home", runId: null, snap: null, runs: [] };

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
  state.view = state.snap ? key : "home";
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
        <td>${r.created_at.replace("T", " ")}</td>
      </tr>`,
    )
    .join("");
  return `
  <div class="canvas-narrow">
    <h1>Forecast runs</h1>
    <p class="lede">Start a forecast by entering an ask — or reopen a past run to
    audit its brief, graph, and metrics.</p>
    <div class="card">
      <h2 style="margin-top:0">New run</h2>
      <p class="hint">Coming up: the ask form (category, question, window, market).</p>
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

function renderRun() {
  /* Filled in by the Ask -> Sources -> Run flow. */
  return `<div class="canvas-narrow"><h1>${state.runId}</h1>
    <p class="lede">Stage views land with the Ask → Sources → Run flow.</p></div>`;
}

function render() {
  document.getElementById("btn-runs").hidden = state.view === "home";
  const badge = document.getElementById("mode-badge");
  if (state.snap) {
    badge.hidden = state.snap.mode !== "fixture";
    badge.textContent = "fixture mode";
  } else {
    badge.hidden = true;
  }
  document.getElementById("canvas").innerHTML =
    state.view === "home" || !state.snap ? renderHome() : renderRun();
  document.getElementById("canvas").querySelectorAll("tr[data-run]").forEach((tr) => {
    tr.addEventListener("click", () => openRun(tr.dataset.run));
  });
  renderRail();
}

/* --- actions ------------------------------------------------------------ */

async function openRun(runId) {
  state.snap = await api(`/api/runs/${runId}`);
  state.runId = runId;
  state.view = currentStage(state.snap);
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
  render();
}

document.getElementById("btn-runs").addEventListener("click", goHome);
goHome();

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}
