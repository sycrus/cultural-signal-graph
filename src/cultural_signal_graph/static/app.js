/* Cultural Signal Graph — the forecast stepper. Preact + htm + signals, vendored,
   no build step (ADR-0011), built from the shared components in ui.js like futures
   mode. Left rail of stages; the canvas shows the active stage. Talks to the JSON API. */

import { h, render } from "preact";
import { useState } from "preact/hooks";
import { signal } from "@preact/signals";
import htm from "htm";
import { Button, Chip, EmptyState, Panel, Tabs, Toasts, Toggle, toast } from "./ui.js";
import { AppBar, Crumbs } from "./shell.js";

const html = htm.bind(h);

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

/* --- state: one signal; set() merges, every view re-renders from it --------- */

const state = signal({
  view: "home",
  runId: null,
  snap: null,
  runs: [],
  busy: false,
  error: null,
  signoffDraft: {}, // edge id -> true(approve) | false(reject), before confirming
  metrics: null, // the /metrics report for the open run
  futures: null, // {explorations, projections} on the open run, for the Graph tab's futures layer
  futuresLayer: false, // Graph tab: show exploration projections (hidden by default)
  graphView: null, // {zoom, focus} carried across the futures-layer reload
});
const get = () => state.value;
const set = (patch) => {
  state.value = { ...state.value, ...patch };
  syncUrl();
};

/* The address reflects what is on screen: / (runs), /?new (a new ask), or
   /?run=<id>&step=<step>. Moving around pushes history, so Back and refresh work
   and any step can be linked; popstate routes back from the address. */
let routing = false; // true while applying the address, so it is not pushed again
function urlFor({ view, runId }) {
  if (runId && view !== "home") return `/?run=${encodeURIComponent(runId)}&step=${encodeURIComponent(view)}`;
  return view === "ask" ? "/?new" : "/";
}
function syncUrl() {
  if (routing) return;
  const url = urlFor(get());
  if (url !== location.pathname + location.search) history.pushState(null, "", url);
}
async function route() {
  const q = new URLSearchParams(location.search);
  routing = true;
  try {
    if (q.get("run")) {
      if (q.get("run") !== get().runId) await openRun(q.get("run"), q.get("step"));
      else if (q.get("step")) showStage(q.get("step"));
    } else if (q.has("new")) {
      set({ view: "ask", snap: null, runId: null, error: null });
    } else {
      await goHome();
    }
  } finally {
    routing = false;
  }
  // settle the address (a bare ?run=, or a step the run cannot show yet)
  history.replaceState(null, "", urlFor(get()));
}
window.addEventListener("popstate", route);
const fail = (err) => set({ error: String(err.message || err) });

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

/* --- navigation & loading -------------------------------------------------- */

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

function currentStage(snap) {
  if (snap.status === "created") return "sources"; // not started: review sources, then run
  const states = railStates(snap);
  const action = RAIL_STAGES.find((s) => states[s.key] === "action");
  if (action) return action.key;
  const firstOpen = RAIL_STAGES.find((s) => states[s.key] === "active");
  return firstOpen ? firstOpen.key : "brief";
}

function showStage(key) {
  const snap = get().snap;
  if (!snap) return;
  const st = railStates(snap)[key];
  if (st !== "done" && st !== "active" && st !== "action") key = currentStage(snap); // not reachable yet
  set({ view: key, error: null });
  if (key === "metrics" && !get().metrics) fetchMetrics();
  if (key === "graph" && !get().futures) fetchFutures();
}

async function fetchFutures() {
  const runId = get().runId;
  const list = await api(`/api/runs/${runId}/explorations`).catch(() => null);
  if (get().runId !== runId || !list) return;
  set({ futures: { explorations: list.length, projections: list.reduce((n, e) => n + (e.projections || 0), 0) } });
}

async function fetchMetrics() {
  const runId = get().runId;
  const metrics = await api(`/api/runs/${runId}/metrics`).catch(() => null);
  if (get().runId === runId) set({ metrics });
}

async function openRun(runId, step = null) {
  try {
    const snap = await api(`/api/runs/${runId}`);
    const st = step && railStates(snap)[step];
    const view = st === "done" || st === "active" || st === "action" ? step : currentStage(snap);
    set({ snap, runId, signoffDraft: {}, metrics: null, futures: null, graphView: null, error: null, view });
    if (get().view === "metrics") fetchMetrics();
    if (get().view === "graph") fetchFutures();
  } catch (err) {
    fail(err);
  }
}

async function goHome() {
  const runs = await api("/api/runs").catch(() => []);
  set({ runs, view: "home", snap: null, runId: null, error: null });
}

/* --- shared bits ----------------------------------------------------------- */

// Readable full URI: drop the scheme and "www.", decode %-escapes (Wikipedia
// titles), keep the whole path so the source is identifiable at a glance.
function shortUri(uri) {
  try {
    const u = new URL(uri);
    let path = u.pathname + u.search;
    try { path = decodeURIComponent(path); } catch {}
    return u.hostname.replace(/^www\./, "") + (path === "/" ? "" : path);
  } catch {
    return uri;
  }
}
const shortType = (sourceType) => sourceType.split("#").pop();
// A claim's validity window; either end may be open (null) in the brief.
function validity(tv) {
  const day = (d) => (d ? String(d).slice(0, 10) : null);
  const from = day(tv?.valid_from);
  const until = day(tv?.valid_until);
  if (!from && !until) return "no stated window";
  return `valid ${from || "…"} → ${until || "open"}`;
}
const plural = (n, word, many = `${word}s`) => `${n} ${n === 1 ? word : many}`;

const ErrorLine = () => (get().error ? html`<div class="error">${get().error}</div>` : null);

// Run and edge statuses as chips: the same tone means the same thing everywhere.
const STATUS_TONE = { completed: "ok", real: "ok", paused: "warn", proposed: "warn", running: "futures", rejected: "danger", failed: "danger" };
const StatusChip = ({ status }) => html`<${Chip} tone=${STATUS_TONE[status] || "neutral"} class="status-chip">${status}<//>`;

function Placeholder({ title, note }) {
  return html`<div class="canvas-narrow">
    <h1>${title}</h1>
    <${Panel}><${EmptyState} title=${`No ${title.toLowerCase()} yet`}>${note}<//><//>
  </div>`;
}

const REVIEW_TABS = [{ key: "brief", label: "Brief" }, { key: "graph", label: "Graph" }, { key: "metrics", label: "Metrics" }];
const ReviewTabs = ({ active }) => html`<${Tabs} class="review-tabs" label="Review" value=${active} onChange=${showStage} items=${REVIEW_TABS} />`;

/* --- rail ---------------------------------------------------------------- */

function Rail() {
  const { snap, view } = get();
  if (view === "home") return null; // the runs list has no run to step through
  const states = railStates(snap);
  const firstOpen = RAIL_STAGES.find((s) => states[s.key] !== "done");
  return html`<nav id="rail" aria-label="Pipeline stages">
    ${RAIL_STAGES.map((stage) => {
      const cls = states[stage.key];
      const current = cls === "action" || (stage.key === firstOpen?.key);
      const open = cls === "active" || cls === "done";
      return html`<${Button} key=${stage.key} class=${`rail-item ${cls} ${current ? "current" : ""} ${view === stage.key ? "here" : ""}`}
        disabled=${!open} aria-current=${view === stage.key ? "step" : undefined}
        onClick=${open ? () => showStage(stage.key) : undefined}>
        <span class="dot" aria-hidden="true"></span>${stage.label}<//>`;
    })}
  </nav>`;
}

/* --- canvas views ---------------------------------------------------------- */

function Home() {
  const { runs } = get();
  return html`<div class="canvas-narrow">
    <h1>Forecast runs</h1>
    <p class="lede">Start a forecast by entering an ask — or reopen a past run to
    audit its brief, graph, and metrics.</p>
    <${Panel} row>
      <${Button} variant="primary" onClick=${() => set({ view: "ask", error: null })}>New run<//>
      <span class="hint">Category, question, window, market.</span>
    <//>
    <h2>Past runs</h2>
    <${Panel} flush>
      ${runs.length
        ? html`<table>
            <thead><tr><th>Run</th><th>Ask</th><th>Status</th><th>Created</th></tr></thead>
            <tbody>${runs.map((r) => html`<tr key=${r.id} class="row-link" tabindex="0"
                onClick=${() => openRun(r.id)} onKeyDown=${(e) => e.key === "Enter" && openRun(r.id)}>
                <td>${r.id}</td>
                <td>${r.ask.category} — ${r.ask.question}</td>
                <td><${StatusChip} status=${r.status} /></td>
                <td>${r.created_at.replace("T", " ").slice(0, 16)}</td>
              </tr>`)}</tbody>
          </table>`
        : html`<${EmptyState} title="No runs yet"
            action=${html`<${Button} variant="primary" onClick=${() => set({ view: "ask", error: null })}>New run<//>`}>
            A run answers one ask: it discovers sources, extracts signals and drafts a brief you sign off.<//>`}
    <//>
  </div>`;
}

function AskRecorded({ a }) {
  /* Reopened runs show the recorded ask read-only — a resubmission would start a
     different run, not re-enter this one. New asks come from the runs list. */
  return html`<div class="canvas-narrow">
    <h1>Ask</h1>
    <p class="lede">The ask this run answers. To ask again, start a new run from the runs list.</p>
    <${Panel} class="ask-recorded">
      <dl>
        <dt>Category</dt><dd>${a.category}</dd>
        <dt>Question</dt><dd>${a.question}</dd>
        <dt>Window</dt><dd>${a.window.start} → ${a.window.end}</dd>
        ${a.market ? html`<dt>Market</dt><dd>${a.market}</dd>` : null}
      </dl>
    <//>
  </div>`;
}

function Ask() {
  const a = get().snap?.ask;
  const [form, setForm] = useState({ category: "tech", question: "", start: "2026-01-01", end: "2026-06-30", market: "" });
  const [busy, setBusy] = useState(false);
  if (a) return html`<${AskRecorded} a=${a} />`;
  const field = (key) => ({ value: form[key], onInput: (e) => setForm({ ...form, [key]: e.target.value }) });
  const submit = async () => {
    if (!form.question.trim()) return set({ error: "Enter a question for the forecast." });
    setBusy(true);
    try {
      const snap = await api("/api/runs", { method: "POST", body: {
        category: form.category || "tech", question: form.question,
        window_start: form.start || "2026-01-01", window_end: form.end || "2026-06-30", market: form.market || null,
      } });
      set({ snap, runId: snap.id, view: "sources", error: null, signoffDraft: {}, metrics: null, futures: null });
    } catch (err) {
      fail(err);
    }
    setBusy(false);
  };
  return html`<div class="canvas-narrow">
    <h1>Ask</h1>
    <p class="lede">What should the forecast cover? The ask drives source discovery
    and selects the sub-ontology to reason over.</p>
    <${Panel}>
      <label for="ask-category">Category</label>
      <input id="ask-category" name="category" autocomplete="off" list="categories" ...${field("category")} />
      <datalist id="categories"><option value="tech"></option><option value="gaming"></option></datalist>
      <div class="hint">An unfamiliar category is backfilled from the live web.</div>

      <label for="ask-question">Question</label>
      <input id="ask-question" name="question" autocomplete="off" placeholder="e.g. AI wearables adoption…" ...${field("question")}
        onKeyDown=${(e) => e.key === "Enter" && submit()} />

      <label>Window</label>
      <div class="row">
        <input id="ask-start" name="window_start" type="date" aria-label="Window start" ...${field("start")} />
        <span>→</span>
        <input id="ask-end" name="window_end" type="date" aria-label="Window end" ...${field("end")} />
      </div>

      <label for="ask-market">Market <span class="optional">(optional)</span></label>
      <input id="ask-market" name="market" autocomplete="off" list="markets" placeholder="e.g. SEA, Japan, LATAM — or any market…" ...${field("market")} />
      <datalist id="markets">${MARKETS.map((m) => html`<option key=${m} value=${m}></option>`)}</datalist>

      <${ErrorLine} />
      <div class="row right">
        <${Button} variant="primary" onClick=${submit} busy=${busy} busyLabel="Discovering sources…">Discover sources<//>
      </div>
    <//>
  </div>`;
}

// Market suggestions for the Ask form: region blocs first, then every country.
// Suggestions only — the market is free text end to end (it shapes search
// queries and the seeded ontology), so anything typed is accepted.
const MARKET_REGIONS = [
  "Global", "SEA", "APAC", "East Asia", "South Asia", "Central Asia", "Oceania", "ANZ",
  "North America", "LATAM", "Caribbean", "EMEA", "Europe", "Western Europe", "Eastern Europe",
  "Nordics", "DACH", "Benelux", "MENA", "GCC", "Sub-Saharan Africa",
];
const MARKET_COUNTRIES = [
  "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina",
  "Armenia", "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados",
  "Belarus", "Belgium", "Belize", "Benin", "Bhutan", "Bolivia", "Bosnia and Herzegovina", "Botswana",
  "Brazil", "Brunei", "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia", "Cameroon",
  "Canada", "Central African Republic", "Chad", "Chile", "China", "Colombia", "Comoros", "Congo",
  "Costa Rica", "Côte d'Ivoire", "Croatia", "Cuba", "Cyprus", "Czechia",
  "Democratic Republic of the Congo", "Denmark", "Djibouti", "Dominica", "Dominican Republic",
  "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini",
  "Ethiopia", "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany", "Ghana",
  "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti", "Honduras",
  "Hong Kong", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel",
  "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Kosovo", "Kuwait",
  "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein",
  "Lithuania", "Luxembourg", "Macau", "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali",
  "Malta", "Marshall Islands", "Mauritania", "Mauritius", "Mexico", "Micronesia", "Moldova",
  "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia", "Nauru",
  "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea",
  "North Macedonia", "Norway", "Oman", "Pakistan", "Palau", "Palestine", "Panama",
  "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Puerto Rico",
  "Qatar", "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia",
  "Saint Vincent and the Grenadines", "Samoa", "San Marino", "São Tomé and Príncipe",
  "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia",
  "Slovenia", "Solomon Islands", "Somalia", "South Africa", "South Korea", "South Sudan", "Spain",
  "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria", "Taiwan", "Tajikistan",
  "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago", "Tunisia",
  "Türkiye", "Turkmenistan", "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates",
  "United Kingdom", "United States", "Uruguay", "Uzbekistan", "Vanuatu", "Vatican City",
  "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe",
];
const MARKETS = [...MARKET_REGIONS, ...MARKET_COUNTRIES];

async function putSources(sources, note) {
  try {
    const snap = await api(`/api/runs/${get().runId}/sources`, { method: "PUT", body: { sources } });
    set({ snap, error: null });
    if (note) toast(note);
  } catch (err) {
    fail(err);
  }
}

function DiscoveryTrace({ trace }) {
  const via = trace.query_source === "model" ? "generated by the cheap model" : trace.query_source === "given" ? "as given" : "from the ask (model generation unavailable)";
  return html`<${Panel}><details>
    <summary>Discovery trace — ${trace.results.length} results examined via ${plural(trace.queries.length, "query", "queries")} (${trace.mode})</summary>
    <div class="hint">Queries ${via}:</div>
    <ul>${trace.queries.map((q) => html`<li key=${q}>${q}</li>`)}</ul>
    <table>
      <thead><tr><th>Result</th><th>Found by</th><th>Selected</th></tr></thead>
      <tbody>${trace.results.map((r) => html`<tr key=${r.url} class="static">
        <td><a href=${r.url} target="_blank" rel="noopener">${r.title}</a></td>
        <td class="hint">“${r.query}”</td>
        <td>${trace.selected.some((sel) => sel.uri === r.url) ? html`<${Chip} tone="ok">✓ web<//>` : null}</td>
      </tr>`)}</tbody>
    </table>
  </details><//>`;
}

function Sources() {
  const s = get().snap;
  const editable = s.status === "created"; // sources lock once the run starts
  const [uri, setUri] = useState("");
  const [text, setText] = useState("");
  const [starting, setStarting] = useState(false);
  const add = async () => {
    if (!uri.trim() || !text.trim()) return set({ error: "A source needs a URI and what it says." });
    await putSources(s.sources.concat([{
      uri: uri.trim(), text: text.trim(), source_type: "https://cultural-signal-graph.dev/ontology#Source",
      credibility: 0.6, category: s.ask.category, topics: [],
    }]), "Source added.");
    if (!get().error) { setUri(""); setText(""); }
  };
  const remove = (i) => {
    const removed = s.sources[i];
    putSources(s.sources.filter((_, j) => j !== i), null).then(() => {
      if (!get().error) toast(`Removed ${shortUri(removed.uri)}.`, { action: { label: "Undo", run: () => putSources(s.sources, "Source restored.") } });
    });
  };
  const reset = async () => {
    try {
      set({ snap: await api(`/api/runs/${get().runId}/sources/reset`, { method: "POST" }), error: null });
      toast("Sources reset to what discovery found.");
    } catch (err) {
      fail(err);
    }
  };
  const start = async () => {
    setStarting(true);
    set({ view: "run", busy: true, error: null, signoffDraft: {} });
    try {
      const snap = await api(`/api/runs/${get().runId}/start`, { method: "POST" });
      set({ snap, busy: false, view: currentStage(snap) });
    } catch (err) {
      set({ busy: false });
      fail(err);
    }
    setStarting(false);
  };
  const promoted = s.origin?.promoted_from;
  return html`<div class="canvas-narrow">
    <h1>Sources</h1>
    <p class="lede">Discovered for “${s.ask.question}”. Auditable by default — expand to
      review${editable ? " or override before extraction runs" : ""}.</p>
    <${Panel}><details open=${s.sources.length === 0 || editable}>
      <summary>${plural(s.sources.length, "source")}</summary>
      ${s.sources.length
        ? html`<table>
            <thead><tr><th>Source</th><th>Type</th><th>Credibility</th><th>Text</th><th></th></tr></thead>
            <tbody>${s.sources.map((src, i) => html`<tr key=${src.uri + i} class="static">
              <td class="uri"><a href=${src.uri} target="_blank" rel="noopener" title=${src.uri}>${shortUri(src.uri)}</a></td>
              <td>${shortType(src.source_type)}</td>
              <td class="num">${src.credibility}</td>
              <td class="clip" title=${src.text}>${src.text}</td>
              <td>${editable ? html`<${Button} variant="ghost" aria-label=${`Remove ${shortUri(src.uri)}`} title="Remove" onClick=${() => remove(i)}>✕<//>` : null}</td>
            </tr>`)}</tbody>
          </table>`
        : html`<${EmptyState} compact title="No sources">${editable ? "Add one below, or reset to what discovery found." : null}<//>`}
      ${editable
        ? html`<div class="row add-source">
            <input name="uri" type="url" inputmode="url" autocomplete="off" spellcheck="false" placeholder="e.g. https://example.com/report…" aria-label="Source URI" value=${uri} onInput=${(e) => setUri(e.target.value)} />
            <input name="text" autocomplete="off" placeholder="e.g. the claim or quote it supports…" aria-label="What it says" value=${text} onInput=${(e) => setText(e.target.value)}
              onKeyDown=${(e) => e.key === "Enter" && add()} />
            <${Button} onClick=${add}>+ Add<//>
          </div>`
        : null}
    </details><//>
    ${s.discovery ? html`<${DiscoveryTrace} trace=${s.discovery} />` : null}
    ${promoted
      ? html`<${Panel} class="origin-note">↗ This run was created by promoting a reference from
          <a href=${`/futures?run=${encodeURIComponent(promoted.run)}&x=${encodeURIComponent(promoted.exploration)}`}>an exploration</a>
          on run ${promoted.run}: <a href=${promoted.url} target="_blank" rel="noopener">${shortUri(promoted.url)}</a> is the last source below.<//>`
      : null}
    <${ErrorLine} />
    ${editable
      ? html`<div class="row spread">
          <${Button} onClick=${reset}>Reset to discovered<//>
          <${Button} variant="primary" onClick=${start} disabled=${s.sources.length === 0} busy=${starting} busyLabel="Starting…">Start run<//>
        </div>`
      : null}
  </div>`;
}

function StageChip({ name, st }) {
  const done = st?.status === "done";
  const paused = st?.status === "paused";
  return html`<${Chip} tone=${done ? "ok" : paused ? "warn" : "neutral"} class="stage-chip">
    ${name} ${done ? "✓" : paused ? "…" : "·"}<//>`;
}

function Run() {
  const { snap: s, busy } = get();
  const chips = RUN_STAGES.map((name) => html`<${StageChip} key=${name} name=${name} st=${s.stages[name]} />`);
  return html`<div class="canvas-narrow">
    <h1>Run</h1>
    <p class="lede">${busy ? "Extracting signals and proposing cross-domain edges…" : "Where each stage of the pipeline stands."}</p>
    <${Panel} row class="stage-chips">${busy ? html`<span class="spinner"></span>` : null}${chips}<//>
    <${ErrorLine} />
  </div>`;
}

// The sources behind one side of a proposed edge, as links to check before deciding.
// Runs paused before this field existed have no list, so render nothing.
function EdgeEvidence({ name, uris }) {
  if (!uris?.length) return null;
  return html`<div class="edge-meta">Sources for <b>${name}</b>:
    <ul>${uris.map((u) => html`<li key=${u}><a href=${u} target="_blank" rel="noopener" title=${u}>${shortUri(u)}</a></li>`)}</ul>
  </div>`;
}

function SignOff() {
  const { snap: s, signoffDraft: decided, busy } = get();
  const undoable = s.status === "completed" && Object.keys(s.decisions || {}).length > 0;
  if (s.status !== "paused" && !undoable) {
    return html`<${Placeholder} title="Sign-off" note="No cross-domain edges were proposed for this run, so nothing needed a decision." />`;
  }
  if (undoable) {
    // pending is empty once the run resumes — resolve names from the brief's
    // gated edges (which carry the display names and the resolved status)
    const gated = Object.fromEntries((s.brief ? s.brief.gated_edges : []).map((g) => [g.id, g]));
    const undo = async () => {
      try {
        const snap = await api(`/api/runs/${get().runId}/signoff/undo`, { method: "POST" });
        set({ snap, signoffDraft: {}, view: "sign-off", error: null });
        toast("Sign-off reopened: the brief will be redrafted after you decide again.");
      } catch (err) {
        fail(err);
      }
    };
    return html`<div class="canvas-narrow">
      <h1>Sign-off</h1>
      <p class="lede">Your decision is recorded but stays editable until you export.
      Undoing re-runs the downstream (draft → brief) and parks the run back here.</p>
      ${Object.entries(s.decisions).map(([id, approved]) => {
        const known = (s.pending || []).find((e) => e.id === id) || gated[id];
        return html`<${Panel} key=${id} class=${`edge-card decided ${approved ? "approved" : "rejected"}`}>
          <div class="edge-head">${known ? html`${known.left_entity || known.left} <span class="approx">≈</span> ${known.right_entity || known.right}` : id}</div>
          <${Chip} tone=${approved ? "ok" : "danger"}>${approved ? "✓ approved — asserted as real" : "✕ rejected — dropped"}<//>
        <//>`;
      })}
      <${ErrorLine} />
      <div class="row"><${Button} onClick=${undo}>Undo sign-off & re-decide<//></div>
    </div>`;
  }

  const all = s.pending.every((e) => e.id in decided);
  const decide = (id, approved) => set({ signoffDraft: { ...decided, [id]: approved } });
  const confirm = async () => {
    set({ busy: true, error: null });
    try {
      const snap = await api(`/api/runs/${get().runId}/signoff`, { method: "POST", body: { decisions: decided } });
      set({ snap, signoffDraft: {}, view: currentStage(snap), busy: false });
      toast("Sign-off recorded. The brief is drafted.");
    } catch (err) {
      set({ busy: false });
      fail(err);
    }
  };
  return html`<div class="canvas-narrow">
    <h1>Sign-off</h1>
    <p class="lede">The run is <b>paused</b> until you decide. Approving asserts a
    cross-domain equivalence edge as real; rejecting drops it and keeps the categories separate.</p>
    <p class="review-count">◉ Review ${plural(s.pending.length, "proposed cross-domain edge")}</p>
    ${s.pending.map((e) => html`<${Panel} key=${e.id} class="edge-card">
      <div class="edge-head">${e.left} <span class="approx">≈</span> ${e.right}</div>
      <div class="edge-meta">confidence ${e.confidence} · ${e.left_category} ⇄ ${e.right_category}</div>
      <${EdgeEvidence} name=${e.left} uris=${e.left_sources} />
      <${EdgeEvidence} name=${e.right} uris=${e.right_sources} />
      <div class="edge-actions">
        <${Button} variant=${decided[e.id] === true ? "primary" : null} aria-pressed=${decided[e.id] === true ? "true" : "false"}
          onClick=${() => decide(e.id, true)}>✓ Approve<//>
        <${Button} variant=${decided[e.id] === false ? "danger" : null} aria-pressed=${decided[e.id] === false ? "true" : "false"}
          onClick=${() => decide(e.id, false)}>✕ Reject<//>
        ${e.id in decided
          ? html`<${Chip} tone=${decided[e.id] ? "ok" : "danger"}>your call: ${decided[e.id] ? "real" : "dropped"} — reversible until export<//>`
          : null}
      </div>
    <//>`)}
    <${ErrorLine} />
    <div class="row">
      <${Button} variant="primary" onClick=${confirm} disabled=${!all} busy=${busy} busyLabel="Resuming the run…">Confirm sign-off<//>
      ${all ? null : html`<span class="hint">Decide every proposed edge to resume the run.</span>`}
    </div>
  </div>`;
}

function Brief() {
  const { snap, runId } = get();
  const b = snap?.brief;
  if (!b) return html`<${Placeholder} title="Brief" note="The brief appears once the run resolves sign-off and drafting finishes." />`;
  return html`<div class="canvas-narrow">
    <${ReviewTabs} active="brief" />
    <div class="brief-head">
      <h1>Forecast brief — ${b.category}</h1>
      <span class="hint">as of ${b.as_of}</span>
    </div>
    <p class="lede">${plural(b.claims.length, "claim")}, ${b.flags.length} flagged.</p>
    <div class="exports"><span class="hint">Export</span>
      ${["brief.md", "brief.json", "brief.pptx", "graph.ttl"].map(
        (name) => html`<${Button} key=${name} class="export-link" href=${`/api/runs/${runId}/exports/${name}`} download>${name}<//>`,
      )}
    </div>

    <h2>Trends</h2>
    ${b.claims.length
      ? b.claims.map((c, i) => html`<${Panel} key=${i} class="claim-card">
          <div class="claim-head">
            <span class="claim-num">${i + 1}.</span>
            <span class="claim-statement">${c.statement}</span>
            <${Chip} class="conf-chip" title="Confidence — how much we trust this, not a calibrated probability">${c.confidence}<//>
          </div>
          <div class="claim-valid">${validity(c.temporal_validity)}</div>
          <details><summary>reasoning</summary><p>${c.reasoning}</p></details>
          <details><summary>sources (${c.sources.length})</summary>
            <ul>${c.sources.map((src) => html`<li key=${src.uri}><a href=${src.uri} target="_blank" rel="noopener">${shortUri(src.uri)}</a>
              <span class="hint"> (${shortType(src.source_type)}, credibility ${src.credibility})</span></li>`)}</ul>
          </details>
        <//>`)
      : html`<${Panel}><${EmptyState} compact title="No confident trends." /><//>`}

    <h2>⚠ Flagged signals</h2>
    <p class="hint">Surfaced, never averaged away — they stay in the graph but are not claims.</p>
    ${b.flags.length
      ? b.flags.map((f, i) => html`<${Panel} key=${i} row class=${`flag-card ${f.reason === "conflict" ? "conflict" : "low"}`}>
          <${Chip} tone=${f.reason === "conflict" ? "danger" : "warn"}>${f.reason}<//>
          <span class="flag-text">${f.statement}</span>
          <span class="hint">confidence ${f.confidence} · <a href=${f.source_uri} target="_blank" rel="noopener">source</a></span>
        <//>`)
      : html`<${Panel}><${EmptyState} compact title="None flagged." /><//>`}

    <h2>⛓ Gated cross-domain edges</h2>
    ${b.gated_edges.length
      ? b.gated_edges.map((g) => html`<${Panel} key=${g.id} row class="gated-row">
          <span class="gated-edge">⛓ ${g.left_entity} ≈ ${g.right_entity}</span>
          <span class="hint">confidence ${g.confidence}</span>
          <${StatusChip} status=${g.status} />
          <span class="spacer"></span>
          <${Button} variant="ghost" onClick=${() => showStage("sign-off")}>Review<//>
        <//>`)
      : html`<${Panel}><${EmptyState} compact title="No cross-domain edges were proposed." /><//>`}
  </div>`;
}

function GraphView() {
  const { snap, runId, futures: f, futuresLayer, graphView } = get();
  if (!snap || snap.status !== "completed") {
    return html`<${ReviewTabs} active="graph" /><${Placeholder} title="Graph" note="The graph explorer appears once the run completes." />`;
  }
  /* The futures layer adds this run's explorations to the graph; say what it adds,
     and say so plainly when there is nothing to add yet. */
  const none = f && f.projections === 0;
  const toggle = (on) => {
    // Keep the viewer's zoom and centre across the reload the toggle causes.
    let view = null;
    try { view = document.querySelector(".graph-frame")?.contentWindow?.graphView?.() || null; } catch { view = null; }
    set({ futuresLayer: on, graphView: view });
  };
  const hash = graphView?.zoom ? `#zoom=${graphView.zoom.toFixed(3)}${graphView.focus ? `&focus=${encodeURIComponent(graphView.focus)}` : ""}` : "";
  return html`<${ReviewTabs} active="graph" />
    <div class="futures-toggle-row">
      <${Toggle} class="futures-toggle" label="Show futures layer" checked=${futuresLayer && !none} disabled=${!!none} onChange=${toggle}
        title="Projections from this run's explorations, beside the evidence they grow from. Never part of the brief." />
      ${!f ? null : none
        ? html`<span class="hint">No explorations on this run yet. <a href=${`/futures?run=${runId}`}>Start one in Futures →</a></span>`
        : html`<span class="hint">adds ${plural(f.projections, "projection")} from ${plural(f.explorations, "exploration")}</span>`}
    </div>
    <iframe class="graph-frame" src=${`/runs/${runId}/graph.html${futuresLayer && !none ? "?futures_layer=true" : ""}${hash}`}
      title="Graph explorer — search, layout, click-to-trace"></iframe>`;
}

function Metrics() {
  const m = get().metrics;
  if (!m) {
    return html`<div class="canvas-narrow"><${ReviewTabs} active="metrics" /><h1>Metrics</h1><${Panel} row><span class="spinner"></span> Loading metrics…<//></div>`;
  }
  const ev = m.eval;
  const below = new Set(ev?.below_threshold || []);
  const acc = m.accuracy;
  return html`<div class="canvas-narrow">
    <${ReviewTabs} active="metrics" />
    <h1>Metrics</h1>
    <p class="lede">How far to trust this run: eval scores gate regressions; prediction accuracy
    is soft, lagging telemetry.</p>

    <h2>Eval scores</h2>
    <${Panel}>
      ${!ev
        ? html`<${EmptyState} compact title="Eval scores appear once the run is finalized." />`
        : ev.scores == null
          ? html`<div class="hint">${ev.reason}</div>`
          : html`<div class="chips">${Object.entries(ev.scores).map(([metric, score]) => html`<${Chip} key=${metric}
                tone=${below.has(metric) ? "danger" : "ok"} class="score-chip">${metric} ${score}${below.has(metric) ? " ⚠" : ""}<//>`)}</div>
              <p class="hint">Scored against the golden case “${ev.case}” ${ev.scored_at || "at finalize"}
              — the pipeline's correctness before your sign-off decisions. Below-threshold metrics are the regression gate.</p>`}
    <//>

    <h2>Prediction accuracy</h2>
    <${Panel}>
      ${!acc
        ? html`<${EmptyState} compact title="Appears once the run is finalized." />`
        : acc.accuracy == null
          ? html`<div class="hint">${acc.trends_total} trends recorded, ${acc.checked} checked — accuracy is lagging
              telemetry: it fills in as each trend is marked materialized later. Reported, never gating.</div>`
          : html`<div class="metric-big">${Math.round(acc.accuracy * 100)}%</div>
              <div class="hint">${acc.materialized} of ${acc.checked} checked trends materialized (${acc.trends_total} recorded).</div>`}
    <//>
  </div>`;
}

const VIEWS = { home: Home, ask: Ask, sources: Sources, run: Run, "sign-off": SignOff, brief: Brief, graph: GraphView, metrics: Metrics };

/* --- shell ----------------------------------------------------------------- */

function App() {
  const { view, runId, snap } = get();
  const View = VIEWS[view] || Home;
  return html`<${AppBar} mode="forecast" run=${snap} skipTo="canvas" />
    <div id="layout" class=${view === "home" ? "no-rail" : ""}>
      <${Rail} />
      <main id="canvas" tabindex="-1">
        ${view !== "home" ? html`<div class=${`canvas-crumbs ${view === "graph" ? "wide" : ""}`}><${Crumbs} items=${[{ label: "Runs", href: "/", onClick: goHome }]} /></div>` : null}
        <${View} key=${`${view}:${runId}`} />
      </main>
    </div>
    <${Toasts} />`;
}

render(html`<${App} />`, document.getElementById("app"));
// The address says where to start: the runs list, a new ask, or a run's step
// (Futures links back here with ?run=).
route();
