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
  metrics: null, // the /metrics report for the open run
  futuresLayer: false, // Graph tab: show exploration projections (hidden by default)
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
  if (key === "metrics" && state.snap && !state.metrics) {
    fetchMetrics();
  }
}

async function fetchMetrics() {
  state.metrics = await api(`/api/runs/${state.runId}/metrics`).catch(() => null);
  if (state.view === "metrics") render();
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
  /* Reopened runs show the recorded ask read-only — a resubmission would start a
     different run, not re-enter this one. New asks come from the runs list. */
  const a = state.snap && state.snap.ask;
  if (a) {
    return `
    <div class="canvas-narrow">
      <h1>Ask</h1>
      <p class="lede">The ask this run answers. To ask again, start a new run from the runs list.</p>
      <div class="card">
        <label>Category</label><div>${escapeHtml(a.category)}</div>
        <label>Question</label><div>${escapeHtml(a.question)}</div>
        <label>Window</label><div>${escapeHtml(a.window.start)} → ${escapeHtml(a.window.end)}</div>
        ${a.market ? `<label>Market</label><div>${escapeHtml(a.market)}</div>` : ""}
      </div>
    </div>`;
  }
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
  const editable = s.status === "created"; // sources lock once the run starts
  const rows = s.sources
    .map(
      (src, i) => `<tr data-index="${i}">
        <td title="${escapeHtml(src.uri)}">${escapeHtml(shortUri(src.uri))}</td>
        <td>${escapeHtml(shortType(src.source_type))}</td>
        <td>${src.credibility}</td>
        <td style="max-width:260px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap">${escapeHtml(src.text)}</td>
        <td>${editable ? `<button class="ghost" data-remove="${i}">✕</button>` : ""}</td>
      </tr>`,
    )
    .join("");
  const trace = s.discovery;
  const traceBlock = trace
    ? `<details class="card">
        <summary>Discovery trace — ${trace.results.length} results examined via ${trace.queries.length} quer${trace.queries.length === 1 ? "y" : "ies"} (${escapeHtml(trace.mode)})</summary>
        <div class="hint" style="margin:6px 0">Queries ${escapeHtml(trace.query_source === "model" ? "generated by the cheap model" : trace.query_source === "given" ? "as given" : "from the ask (model generation unavailable)")}:</div>
        <ul style="margin:4px 0; padding-left:18px">${trace.queries.map((q) => `<li>${escapeHtml(q)}</li>`).join("")}</ul>
        <table style="margin-top:8px">
          <thead><tr><th>Result</th><th>Found by</th><th>Selected</th></tr></thead>
          <tbody>${trace.results
            .map(
              (r) => `<tr>
                <td><a href="${escapeHtml(r.url)}" target="_blank" rel="noopener">${escapeHtml(r.title)}</a></td>
                <td class="hint">“${escapeHtml(r.query)}”</td>
                <td>${trace.selected.some((sel) => sel.uri === r.url) ? "✓ web" : ""}</td>
              </tr>`,
            )
            .join("")}</tbody>
        </table>
      </details>`
    : "";
  return `
  <div class="canvas-narrow">
    <h1>Sources</h1>
    <p class="lede">Discovered for “${escapeHtml(s.ask.question)}”. Auditable by
    default — expand to review${editable ? " or override before extraction runs" : ""}.</p>
    <details class="card" ${s.sources.length === 0 ? "open" : ""}>
      <summary>${s.sources.length} source${s.sources.length === 1 ? "" : "s"}</summary>
      <table>
        <thead><tr><th>Source</th><th>Type</th><th>Credibility</th><th>Text</th><th></th></tr></thead>
        <tbody>${rows || `<tr><td colspan="5" style="color:var(--muted)">None — add one below.</td></tr>`}</tbody>
      </table>
      ${editable ? `
      <div style="display:flex; gap:8px; margin-top:12px">
        <input id="add-uri" placeholder="https://… (source URI)" style="flex:2">
        <input id="add-text" placeholder="What it says" style="flex:3">
        <button id="btn-add-source">+ Add</button>
      </div>` : ""}
    </details>
    ${traceBlock}
    ${s.origin && s.origin.promoted_from ? `<div class="card origin-note">↗ This run was created by promoting a reference from
      <a href="/futures?run=${encodeURIComponent(s.origin.promoted_from.run)}&x=${encodeURIComponent(s.origin.promoted_from.exploration)}">an exploration</a>
      on run ${escapeHtml(s.origin.promoted_from.run)}: <a href="${escapeHtml(s.origin.promoted_from.url)}" target="_blank" rel="noopener">${escapeHtml(shortUri(s.origin.promoted_from.url))}</a>
      is the last source below.</div>` : ""}
    ${state.error ? `<div class="error">${escapeHtml(state.error)}</div>` : ""}
    ${editable ? `
    <div style="display:flex; justify-content:space-between; margin-top:14px">
      <button id="btn-reset-sources">Reset to discovered</button>
      <button class="primary" id="btn-start-run" ${s.sources.length === 0 ? "disabled" : ""}>Start run →</button>
    </div>` : ""}
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
    // pending is empty once the run resumes — resolve names from the brief's
    // gated edges (which carry the display names and the resolved status)
    const gated = Object.fromEntries((s.brief ? s.brief.gated_edges : []).map((g) => [g.id, g]));
    const rows = Object.entries(s.decisions)
      .map(([id, approved]) => {
        const known = (s.pending || []).find((e) => e.id === id) || gated[id];
        const label = known
          ? `${escapeHtml(known.left_entity || known.left)} ≈ ${escapeHtml(known.right_entity || known.right)}`
          : id;
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
    cross-domain equivalence edge as real; rejecting drops it and keeps the categories separate.</p>
    <p class="review-count">◉ Review ${s.pending.length} proposed cross-domain edge${s.pending.length === 1 ? "" : "s"}</p>
    ${cards}
    ${state.error ? `<div class="error">${escapeHtml(state.error)}</div>` : ""}
    <div style="margin-top:14px; display:flex; gap:10px; align-items:center">
      <button class="primary" id="btn-confirm-signoff" ${all && !state.busy ? "" : "disabled"}>
        ${state.busy ? "Resuming the run…" : "Confirm sign-off →"}</button>
      ${all ? "" : `<span class="hint">Decide every proposed edge to resume the run.</span>`}
    </div>
  </div>`;
}

function renderPlaceholder(title, note) {
  return `<div class="canvas-narrow">
    <h1>${title}</h1>
    <p class="lede">${note}</p>
  </div>`;
}

function renderBrief() {
  const b = state.snap && state.snap.brief;
  if (!b) {
    return renderPlaceholder(
      "Brief",
      "The brief appears once the run resolves sign-off and drafting finishes.",
    );
  }
  const claims = b.claims
    .map(
      (c, i) => `
    <div class="claim-card">
      <div class="claim-head">
        <span class="claim-num">${i + 1}.</span>
        <span class="claim-statement">${escapeHtml(c.statement)}</span>
        <span class="conf-chip" title="Confidence — how much we trust this, not a calibrated probability">${c.confidence}</span>
      </div>
      <div class="claim-valid">valid ${escapeHtml(c.temporal_validity.valid_from.slice(0, 10))}
        → ${escapeHtml(c.temporal_validity.valid_until.slice(0, 10))}</div>
      <details><summary>▸ reasoning</summary><p>${escapeHtml(c.reasoning)}</p></details>
      <details><summary>▸ sources (${c.sources.length})</summary>
        <ul>${c.sources
          .map(
            (src) => `<li><a href="${escapeHtml(src.uri)}" target="_blank" rel="noopener">${escapeHtml(shortUri(src.uri))}</a>
            <span class="hint">(${escapeHtml(shortType(src.source_type))}, credibility ${src.credibility})</span></li>`,
          )
          .join("")}</ul>
      </details>
    </div>`,
    )
    .join("");
  const flags = b.flags.length
    ? b.flags
        .map(
          (f) => `
    <div class="flag-card">
      <span class="reason-chip ${f.reason === "conflict" ? "conflict" : "low"}">${f.reason}</span>
      <span>${escapeHtml(f.statement)}</span>
      <span class="hint">confidence ${f.confidence} · <a href="${escapeHtml(f.source_uri)}" target="_blank" rel="noopener">source</a></span>
    </div>`,
        )
        .join("")
    : `<div class="hint" style="margin:6px 0">None.</div>`;
  const gated = b.gated_edges.length
    ? b.gated_edges
        .map(
          (g) => `
    <div class="gated-row">
      <span class="gated-edge">⛓ ${escapeHtml(g.left_entity)} ≈ ${escapeHtml(g.right_entity)}</span>
      <span class="hint">confidence ${g.confidence}</span>
      <span class="status ${g.status}">${g.status}</span>
      <button class="ghost" data-goto="sign-off">review</button>
    </div>`,
        )
        .join("")
    : `<div class="hint" style="margin:6px 0">No cross-domain edges were proposed.</div>`;
  const exports = ["brief.md", "brief.json", "brief.pptx", "graph.ttl", "usage.json"]
    .map((name) => `<a class="export-link" href="/api/runs/${state.runId}/exports/${name}" download>${name}</a>`)
    .join(" ");
  return `
  ${tabsHtml("brief")}
  <div class="canvas-narrow">
    <div style="display:flex; align-items:baseline; gap:12px; flex-wrap:wrap">
      <h1>Forecast brief — ${escapeHtml(b.category)}</h1>
      <span class="hint">as of ${escapeHtml(b.as_of)}</span>
    </div>
    <p class="lede">${b.claims.length} claim${b.claims.length === 1 ? "" : "s"}, ${b.flags.length} flagged.
    Exports: ${exports}</p>

    <h2>Trends</h2>
    ${claims || `<div class="hint">No confident trends.</div>`}

    <h2>⚠ Flagged signals</h2>
    <p class="hint" style="margin-top:0">Surfaced, never averaged away — they stay in the graph but are not claims.</p>
    ${flags}

    <h2>⛓ Gated cross-domain edges</h2>
    ${gated}
  </div>`;
}

function tabsHtml(active) {
  return `<div class="tabs">${[["brief", "Brief"], ["graph", "Graph"], ["metrics", "Metrics"]]
    .map(
      ([key, label]) =>
        `<button class="tab ${key === active ? "active" : ""}" data-tab="${key}">${label}</button>`,
    )
    .join("")}</div>`;
}

function reviewPlaceholder(tab, note) {
  return `${tabsHtml(tab)}${renderPlaceholder(tab === "graph" ? "Graph" : "Metrics", note)}`;
}

function renderGraph() {
  if (!state.snap || state.snap.status !== "completed") {
    return reviewPlaceholder("graph", "The graph explorer appears once the run completes.");
  }
  return `
  ${tabsHtml("graph")}
  <label class="futures-toggle" title="Projections from this run's explorations, beside the evidence they grow from. Never part of the brief.">
    <input type="checkbox" id="toggle-futures" ${state.futuresLayer ? "checked" : ""}> Show futures layer
  </label>
  <iframe class="graph-frame" src="/runs/${state.runId}/graph.html${state.futuresLayer ? "?futures_layer=true" : ""}"
    title="Graph explorer — search, layout, click-to-trace"></iframe>`;
}

function renderMetrics() {
  if (!state.metrics) {
    return reviewPlaceholder("metrics", "Loading metrics…");
  }
  const m = state.metrics;
  const usage = m.usage || { total_tokens: 0, input_tokens: 0, output_tokens: 0, calls: [] };
  const calls = (usage.calls || [])
    .map(
      (c) => `<tr><td>${escapeHtml(c.model)}</td><td>${c.input_tokens}</td><td>${c.output_tokens}</td><td>${c.total_tokens}</td></tr>`,
    )
    .join("");
  const stageRows = Object.entries(m.stages || {})
    .filter(([name]) => RUN_STAGES.includes(name))
    .map(([name, st]) => `<tr><td>${name}</td><td>${st.tokens} tok</td><td>${fmtDuration(st.latency_ms)}</td></tr>`)
    .join("");

  let evalHtml;
  const ev = m.eval;
  if (!ev) {
    evalHtml = `<div class="hint">Eval scores appear once the run is finalized.</div>`;
  } else if (ev.scores == null) {
    evalHtml = `<div class="hint">${escapeHtml(ev.reason)}</div>`;
  } else {
    const below = new Set(ev.below_threshold || []);
    const scores = Object.entries(ev.scores)
      .map(
        ([metric, score]) =>
          `<span class="score-chip ${below.has(metric) ? "low" : "ok"}">${metric} ${score}${below.has(metric) ? " ⚠" : ""}</span>`,
      )
      .join("");
    evalHtml = `<div>${scores}</div>
      <p class="hint">Scored against the golden case “${escapeHtml(ev.case)}” ${escapeHtml(ev.scored_at || "at finalize")}
      — the pipeline's correctness before your sign-off decisions. Below-threshold metrics are the regression gate.</p>`;
  }

  const acc = m.accuracy;
  let accHtml;
  if (!acc) {
    accHtml = `<div class="hint">Appears once the run is finalized.</div>`;
  } else if (acc.accuracy == null) {
    accHtml = `<div class="hint">${acc.trends_total} trends recorded, ${acc.checked} checked — accuracy is
      lagging telemetry: it fills in as each trend is marked materialized later. Reported, never gating.</div>`;
  } else {
    accHtml = `<div class="metric-big">${Math.round(acc.accuracy * 100)}%</div>
      <div class="hint">${acc.materialized} of ${acc.checked} checked trends materialized (${acc.trends_total} recorded).</div>`;
  }

  return `
  ${tabsHtml("metrics")}
  <div class="canvas-narrow">
    <h1>Metrics</h1>
    <p class="lede">Cost and latency are live-run measurements; eval scores gate regressions;
    prediction accuracy is soft, lagging telemetry.</p>

    <h2>Cost &amp; latency</h2>
    <div class="card">
      <div class="metric-big">${usage.total_tokens} <small>tokens</small></div>
      <div class="hint">${usage.input_tokens} in / ${usage.output_tokens} out across ${(usage.calls || []).length} model calls</div>
      ${calls ? `<table style="margin-top:10px"><thead><tr><th>Model</th><th>In</th><th>Out</th><th>Total</th></tr></thead><tbody>${calls}</tbody></table>` : ""}
      ${stageRows ? `<table style="margin-top:14px"><thead><tr><th>Stage</th><th>Tokens</th><th>Latency</th></tr></thead><tbody>${stageRows}</tbody></table>` : ""}
    </div>

    <h2>Eval scores</h2>
    <div class="card">${evalHtml}</div>

    <h2>Prediction accuracy</h2>
    <div class="card">${accHtml}</div>
  </div>`;
}

const VIEWS = {
  home: renderHome,
  ask: renderAsk,
  sources: renderSources,
  run: renderRun,
  "sign-off": renderSignOff,
  brief: renderBrief,
  graph: renderGraph,
  metrics: renderMetrics,
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
  // Futures mode opens once extraction has run (the run paused at the gate or finished)
  const futures = document.getElementById("btn-futures");
  futures.hidden = !state.snap || !["paused", "completed"].includes(state.snap.status);
  if (state.snap) futures.href = `/futures?run=${encodeURIComponent(state.snap.id)}`;
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
  on("toggle-futures", "change", (e) => {
    state.futuresLayer = e.target.checked;
    render();
  });
  on("btn-undo-signoff", "click", undoSignoff);
  document.querySelectorAll("[data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => showStage(btn.dataset.tab));
  });
  document.querySelectorAll("[data-goto]").forEach((btn) => {
    btn.addEventListener("click", () => showStage(btn.dataset.goto));
  });
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
  state.metrics = null;
  state.view = currentStage(state.snap);
  render();
  if (state.view === "metrics") fetchMetrics();
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
  if (snap.status === "created") return "sources"; // not started: review sources, then run
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
goHome().then(() => {
  // deep link from Futures mode back to its run
  const linked = new URLSearchParams(location.search).get("run");
  if (linked) openRun(linked);
});

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
