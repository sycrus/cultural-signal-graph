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
import { Button, Chip, EmptyState, List, ListRow, PageHead, Panel, Toasts } from "../ui.js";
import { Fingerprint } from "../shape_glyph.js"; // not "fingerprint.js": privacy blockers block that name
import { AppBar, Crumbs } from "../shell.js";

const html = htm.bind(h);

const KIND_LABEL = { claim: "claim", signal: "signal", flagged: "flagged", edge: "cross-domain edge", reference: "reference" };

function ErrorLine() {
  return S.error.value ? html`<div class="error">${S.error.value}</div>` : null;
}

const dateFmt = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" });
const plural = (n, w, many = `${w}s`) => `${n} ${n === 1 ? w : many}`;

function ExplorationList() {
  const r = S.run.value;
  const items = S.explorations.value;
  const canStart = !!S.anchors.value.length;
  const importLog = html`<label class="btn import-label" title="Re-open an exported log.jsonl as a new exploration">
    Import log…
    <input type="file" accept=".jsonl,application/x-ndjson" hidden
      onChange=${async (ev) => { const f = ev.target.files[0]; if (f) await S.importExploration(await f.text()); }} />
  </label>`;
  return html`<div class="page-list">
    <${PageHead} title="Futures"
      lede=${`${r ? `Speculative futures grown from the evidence of “${r.ask.question}”.` : "Speculative futures, grown from a forecast run's evidence."} Projections carry no probability, only where they came from.`}
      actions=${S.runId.value ? html`${importLog}<${Button} variant="primary" onClick=${() => S.newExploration()} disabled=${!canStart}>New exploration<//>` : null} />
    ${S.runId.value ? html`<${ErrorLine} />` : null}
    ${!S.runId.value
      ? html`<${Panel}><${EmptyState} title="No forecast run open" action=${html`<${Button} href="/">Open a forecast run<//>`}>
          Futures grow from a forecast run's evidence. Open a run, then choose Futures.<//><//>`
      : items.length
      ? html`<${List} label="Explorations">
          ${items.map((e) => html`<${ListRow} key=${e.id} href=${`/futures?run=${encodeURIComponent(S.runId.value)}&x=${encodeURIComponent(e.id)}`}
            onOpen=${() => S.openExploration(e.id)}
            fingerprint=${html`<${Fingerprint} shape=${e.shape} label=${`${e.projections} projections`} />`}
            title=${e.goal}
            scope=${`${e.horizon}-year horizon · ${plural(e.orders, "order")} · ${plural(e.anchor_ids.length, "anchor")}`}
            outcome=${e.projections ? html`<span class="futures">◇ ${plural(e.projections, "projection")}</span>` : "Not generated yet"}
            side=${e.created_at ? html`<span>${dateFmt.format(new Date(e.created_at))}</span>` : null}
            actions=${html`<${Button} variant="ghost" class="bar-button" title="Start a new exploration from these settings"
              onClick=${() => S.newExploration({ goal: e.goal, anchor_ids: e.anchor_ids, horizon: e.horizon, orders: e.orders })}>Duplicate with changes<//>`} />`)}
        <//>`
      : html`<${Panel}><${EmptyState} title="No explorations yet"
          action=${canStart ? html`<${Button} variant="primary" onClick=${() => S.newExploration()}>New exploration<//>` : null}>
          ${canStart
            ? "An exploration grows possible futures from this run's evidence, toward a goal you set."
            : "This run has no evidence to grow from yet. Finish the forecast first."}<//><//>`}
  </div>`;
}

function AnchorRow({ a, checked, onToggle, reason }) {
  const p = S.anchorPestle.value[a.id];
  return html`<label class=${`anchor-row ${reason ? "suggested" : ""}`}>
    <input type="checkbox" checked=${checked} onChange=${onToggle} />
    <span class=${`anchor-kind ${a.kind}`}>${KIND_LABEL[a.kind]}${a.flag ? ` · ${a.flag}` : ""}${a.pending ? " · pending sign-off" : ""}</span>
    <span class="anchor-text">${a.text}${reason ? html`<div class="hint">✦ ${reason}</div>` : null}</span>
    ${p ? html`<${Chip} title=${`PESTLE: ${p.value}${p.secondary?.length ? ` (also ${p.secondary.join(", ")})` : ""}`}>${p.value}<//>` : null}
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
    <${Crumbs} items=${[{ label: "Explorations", href: `/futures?run=${S.runId.value}`, onClick: S.showList }]} />
    <h1>New exploration</h1>
    <p class="lede">The goal steers the generator; the anchors are the evidence it grows from.</p>
    <${Panel}>
      <label for="goal">Goal</label>
      <input id="goal" name="goal" autocomplete="off" value=${goal} onInput=${(e) => setGoal(e.target.value)}
        placeholder="e.g. the direction of AR/VR wearables…" />

      <div class="label-row">
        <label>Initial state — ${picked.size} anchor${picked.size === 1 ? "" : "s"}</label>
        <${Button} variant="ghost" onClick=${suggest} busy=${suggesting} busyLabel="Suggesting…" disabled=${!all.length}>✦ Suggest for this goal<//>
      </div>
      <div class="anchor-list">
        ${all.length
          ? all.map((a) => html`<${AnchorRow} key=${a.id} a=${a} checked=${picked.has(a.id)} onToggle=${() => toggle(a.id)} reason=${reasons[a.id]} />`)
          : html`<${EmptyState} compact title="This run has no evidence yet">Anchors come from the forecast's signed-off claims and signals.<//>`}
      </div>
      <${Coverage} items=${coverageItems} label="anchors" />
      <div class="hint">Flagged signals are allowed: weak or contested evidence can still seed a possible future.</div>

      <div style="display:flex; gap:16px">
        <div style="flex:1">
          <label for="horizon">Horizon (years)</label>
          <input id="horizon" name="horizon" autocomplete="off" inputmode="numeric" type="number" min="1" max="50" value=${horizon} onInput=${(e) => setHorizon(e.target.value)} />
          <div class="hint">The time limit.</div>
        </div>
        <div style="flex:1">
          <label for="orders">Orders</label>
          <input id="orders" name="orders" autocomplete="off" inputmode="numeric" type="number" min="1" max="8" value=${orders} onInput=${(e) => setOrders(e.target.value)} />
          <div class="hint">Causal depth — not time.</div>
        </div>
      </div>
      <${ErrorLine} />
      <div style="margin-top:16px; text-align:right">
        <${Button} variant="primary" onClick=${submit} disabled=${picked.size === 0} busy=${S.busy.value} busyLabel="Generating…">
          Generate<//>
      </div>
    <//>
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
  return html`<div class=${`exploration ${S.selectedId.value || S.adding.value ? "panel-open" : ""}`}>
    <${Crumbs} items=${[{ label: "Explorations", href: `/futures?run=${S.runId.value}`, onClick: () => { S.selectedId.value = null; S.adding.value = null; S.showList(); } }]} />
    <div class="exp-head">
      <h1>${e.goal}</h1>
      <span class="hint">${e.start_year} → ${e.start_year + e.horizon} · ${e.orders} orders · ${s.anchors.length} anchors · ${s.projections.length} projections</span>
      <span class="spacer"></span>
      <${Button} onClick=${() => { S.selectedId.value = null; S.adding.value = { kind: "assumption" }; }}
        disabled=${S.generating.value} title="Add your own assumption, wild card or reference">+ Add<//>
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
      ? html`<${Panel} row class="gen-bar">
          <span class="spinner"></span>
          <span>Generating order ${Math.min(s.orders_generated + 1, e.orders)} of ${e.orders}…</span>
          <span class="spacer"></span>
          <${Button} onClick=${S.stopGeneration} busy=${S.stopping.value} busyLabel="Stopping after this order…">■ Stop<//>
        <//>`
      : s.can_continue
        ? html`<${Panel} row class="gen-bar">
            <${Button} variant="primary" onClick=${S.continueGeneration}>
              ${s.orders_generated ? `Continue from order ${s.orders_generated + 1}` : "Generate"}<//>
            <span class="hint">${s.orders_generated} of ${e.orders} orders generated${s.stopped_at ? " — stopped" : ""}.</span>
          <//>`
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
  return html`<${AppBar} mode="futures" run=${S.run.value ? { ...S.run.value, mode: S.snap.value?.mode || S.run.value.mode } : null} skipTo="futures-canvas" />
    <main id="futures-canvas" tabindex="-1">
      ${v === "new" ? html`<${NewExploration} />` : v === "exploration" ? html`<${ExplorationView} />` : html`<${ExplorationList} />`}
    </main>
    <${Toasts} />`;
}

render(html`<${App} />`, document.getElementById("app"));
S.load();
