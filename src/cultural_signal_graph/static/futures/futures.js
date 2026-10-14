/* Futures mode — Preact + htm + signals, vendored ES modules, no build step.
   Explorations list → new exploration form → the exploration view. */

import { h, render } from "preact";
import { useEffect, useState } from "preact/hooks";
import htm from "htm";
import * as S from "./store.js";
import { LensTabs, LensView } from "./lenses.js";
import { DetailPanel } from "./panel.js";
import { HistoryBar, ProjectionActions } from "./actions.js";
import { AddPanel } from "./add.js";
import { Coverage } from "./pestle.js";

const html = htm.bind(h);

const KIND_LABEL = { claim: "claim", signal: "signal", flagged: "flagged", edge: "cross-domain edge", reference: "reference" };

function TopBar() {
  const r = S.run.value;
  return html`<header id="topbar">
    <span class="brand">Cultural Signal Graph</span>
    <span class="mode-switch">
      <a href=${S.runId.value ? `/?run=${S.runId.value}` : "/"}>Forecast</a>
      <span class="active">Futures</span>
    </span>
    ${S.snap.value?.mode === "fixture" || r?.mode === "fixture"
      ? html`<span class="badge" title="Recorded outputs — no model, no network">fixture mode</span>`
      : null}
    <span class="spacer"></span>
    ${S.view.value !== "list" && S.runId.value
      ? html`<button class="ghost" onClick=${S.showList}>← Explorations</button>`
      : null}
  </header>`;
}

function ErrorLine() {
  return S.error.value ? html`<div class="error">${S.error.value}</div>` : null;
}

function ExplorationList() {
  const r = S.run.value;
  const items = S.explorations.value;
  return html`<div class="canvas-narrow">
    <h1>Futures</h1>
    <p class="lede">
      Speculative futures grown from ${r ? html`the evidence of “${r.ask.question}”` : "this run"}.
      Projections carry no probability — only where they came from.
    </p>
    <div class="card" style="display:flex; align-items:center; gap:14px">
      <button class="primary" onClick=${() => S.newExploration()} disabled=${!S.anchors.value.length}>
        New exploration
      </button>
      <span class="hint">Goal, initial anchors, horizon, orders.</span>
      <span class="spacer"></span>
      <label class="import-label" title="Re-open an exported log.jsonl as a new exploration">
        Import log…
        <input type="file" accept=".jsonl,application/x-ndjson" hidden
          onChange=${async (ev) => { const f = ev.target.files[0]; if (f) await S.importExploration(await f.text()); }} />
      </label>
    </div>
    <${ErrorLine} />
    <h2>Explorations</h2>
    <div class="card" style="padding:0">
      <table>
        <thead><tr><th>Goal</th><th>Horizon</th><th>Orders</th><th>Projections</th><th></th></tr></thead>
        <tbody>
          ${items.length
            ? items.map(
                (e) => html`<tr key=${e.id}>
                  <td><a href="#" onClick=${(ev) => { ev.preventDefault(); S.openExploration(e.id); }}>${e.goal}</a></td>
                  <td>${e.horizon} yr</td>
                  <td>${e.orders}</td>
                  <td>${e.projections}</td>
                  <td><button class="ghost" title="Start a new exploration from these settings"
                    onClick=${() => S.newExploration({ goal: e.goal, anchor_ids: e.anchor_ids, horizon: e.horizon, orders: e.orders })}>
                    Duplicate with changes</button></td>
                </tr>`,
              )
            : html`<tr><td colspan="5" class="hint">No explorations yet.</td></tr>`}
        </tbody>
      </table>
    </div>
  </div>`;
}

function AnchorRow({ a, checked, onToggle, reason }) {
  const p = S.anchorPestle.value[a.id];
  return html`<label class=${`anchor-row ${reason ? "suggested" : ""}`}>
    <input type="checkbox" checked=${checked} onChange=${onToggle} />
    <span class=${`anchor-kind ${a.kind}`}>${KIND_LABEL[a.kind]}${a.flag ? ` · ${a.flag}` : ""}${a.pending ? " · pending sign-off" : ""}</span>
    <span class="anchor-text">${a.text}${reason ? html`<div class="hint">✦ ${reason}</div>` : null}</span>
    ${p ? html`<span class="pestle-chip primary" title=${`PESTLE: ${p.value}${p.secondary?.length ? ` (also ${p.secondary.join(", ")})` : ""}`}>${p.value}</span>` : null}
    <span class="hint">${a.entity}</span>
  </label>`;
}

function NewExploration() {
  const d = S.draft.value || {};
  const all = S.anchors.value;
  const [goal, setGoal] = useState(d.goal || "");
  const [picked, setPicked] = useState(new Set(d.anchor_ids || all.filter((a) => a.kind !== "flagged").map((a) => a.id)));
  const [horizon, setHorizon] = useState(d.horizon || 10);
  const [orders, setOrders] = useState(d.orders || 5);
  const [reasons, setReasons] = useState({});
  const [suggesting, setSuggesting] = useState(false);
  useEffect(() => {
    S.loadAnchorPestle();
  }, []);
  const suggest = async () => {
    if (!goal.trim()) {
      S.error.value = "Write the goal first: suggestions are for that goal.";
      return;
    }
    setSuggesting(true);
    try {
      const out = await S.suggestAnchors(goal);
      setPicked(new Set(out.anchor_ids));
      setReasons(out.reasons || {});
      S.error.value = null;
    } catch (err) {
      S.error.value = String(err.message || err);
    }
    setSuggesting(false);
  };
  const coverageItems = all.filter((a) => picked.has(a.id)).map((a) => ({ tags: { pestle: S.anchorPestle.value[a.id] } }));
  const toggle = (id) => {
    const next = new Set(picked);
    next.has(id) ? next.delete(id) : next.add(id);
    setPicked(next);
  };
  const submit = () => {
    if (!goal.trim()) {
      S.error.value = "Give the exploration a goal.";
      return;
    }
    S.createAndGenerate({
      goal,
      anchor_ids: all.filter((a) => picked.has(a.id)).map((a) => a.id),
      horizon: Number(horizon),
      orders: Number(orders),
    });
  };
  return html`<div class="canvas-narrow">
    <h1>New exploration</h1>
    <p class="lede">The goal steers the generator; the anchors are the evidence it grows from.</p>
    <div class="card">
      <label for="goal">Goal</label>
      <input id="goal" value=${goal} onInput=${(e) => setGoal(e.target.value)}
        placeholder="the direction of AR/VR wearables" />

      <div class="label-row">
        <label>Initial state — ${picked.size} anchor${picked.size === 1 ? "" : "s"}</label>
        <button class="ghost" onClick=${suggest} disabled=${suggesting}>${suggesting ? "Suggesting…" : "✦ Suggest for this goal"}</button>
      </div>
      <div class="anchor-list">
        ${all.map((a) => html`<${AnchorRow} key=${a.id} a=${a} checked=${picked.has(a.id)} onToggle=${() => toggle(a.id)} reason=${reasons[a.id]} />`)}
      </div>
      <${Coverage} items=${coverageItems} label="anchors" />
      <div class="hint">Flagged signals are allowed: weak or contested evidence can still seed a possible future.</div>

      <div style="display:flex; gap:16px">
        <div style="flex:1">
          <label for="horizon">Horizon (years)</label>
          <input id="horizon" type="number" min="1" max="50" value=${horizon} onInput=${(e) => setHorizon(e.target.value)} />
          <div class="hint">The time limit.</div>
        </div>
        <div style="flex:1">
          <label for="orders">Orders</label>
          <input id="orders" type="number" min="1" max="8" value=${orders} onInput=${(e) => setOrders(e.target.value)} />
          <div class="hint">Causal depth — not time.</div>
        </div>
      </div>
      <${ErrorLine} />
      <div style="margin-top:16px; text-align:right">
        <button class="primary" onClick=${submit} disabled=${S.busy.value || picked.size === 0}>
          ${S.busy.value ? "Generating…" : "Generate →"}
        </button>
      </div>
    </div>
  </div>`;
}

function ExplorationView() {
  const s = S.snap.value;
  if (!s) return null;
  const e = s.exploration;
  const select = (id) => {
    S.adding.value = null;
    S.selectedId.value = S.selectedId.value === id ? null : id;
  };
  return html`<div class="exploration">
    <div class="exp-head">
      <h1>${e.goal}</h1>
      <span class="hint">${e.start_year} → ${e.start_year + e.horizon} · ${e.orders} orders · ${s.anchors.length} anchors · ${s.projections.length} projections</span>
      <span class="spacer"></span>
      <button onClick=${() => { S.selectedId.value = null; S.adding.value = { kind: "assumption" }; }}
        disabled=${S.generating.value}>+ Add</button>
      <${HistoryBar} />
      <details class="export-menu">
        <summary>Export</summary>
        <div>${["exploration.md", "exploration.json", "log.jsonl", "exploration.trig"].map(
          (n) => html`<a key=${n} href=${`/api/runs/${S.runId.value}/explorations/${e.id}/exports/${n}`} download>${n}</a>`,
        )}</div>
      </details>
    </div>
    <${ErrorLine} />
    ${S.generating.value
      ? html`<div class="card gen-bar">
          <span class="spinner"></span>
          <span>Generating order ${Math.min(s.orders_generated + 1, e.orders)} of ${e.orders}…</span>
          <span class="spacer"></span>
          <button onClick=${S.stopGeneration} disabled=${S.stopping.value}>
            ${S.stopping.value ? "Stopping after this order…" : "■ Stop"}</button>
        </div>`
      : s.can_continue
        ? html`<div class="card gen-bar">
            <button class="primary" onClick=${S.continueGeneration}>
              ${s.orders_generated ? `Continue from order ${s.orders_generated + 1} →` : "Generate →"}</button>
            <span class="hint">${s.orders_generated} of ${e.orders} orders generated${s.stopped_at ? " — stopped" : ""}.</span>
          </div>`
        : null}
    <div class="exp-body">
      <div class="exp-main">
        <${LensTabs} />
        <${LensView} snap=${s} selectedId=${S.selectedId.value} onSelect=${select} />
      </div>
      ${S.adding.value
        ? html`<${AddPanel} key=${JSON.stringify(S.adding.value)} />`
        : S.selectedId.value
        ? html`<${DetailPanel} id=${S.selectedId.value} onSelect=${select} onClose=${() => (S.selectedId.value = null)}
            actions=${S.projectionsById.value[S.selectedId.value]
              ? html`<${ProjectionActions} p=${S.projectionsById.value[S.selectedId.value]} />`
              : null} />`
        : null}
    </div>
  </div>`;
}

function App() {
  const v = S.view.value;
  return html`<${TopBar} />
    <main id="futures-canvas">
      ${v === "new" ? html`<${NewExploration} />` : v === "exploration" ? html`<${ExplorationView} />` : html`<${ExplorationList} />`}
    </main>`;
}

render(html`<${App} />`, document.getElementById("app"));
S.load();
