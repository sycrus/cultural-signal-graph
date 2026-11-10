/* The app shell (#46): one top bar and one breadcrumb, rendered by both pages, so
   the forecast stepper and futures mode share the same frame. The bar never changes
   shape: brand (home), the Forecast | Futures switch (always both), the open run's
   question, then who you are and the theme. Going back up a level is the
   breadcrumb's job, at the top of the page, not the bar's. */

import { h } from "preact";
import { useEffect } from "preact/hooks";
import { signal } from "@preact/signals";
import htm from "htm";
import { author, role, setIdentity } from "./identity.js";
import { Button, Chip, toast } from "./ui.js";

const html = htm.bind(h);

/* --- theme: the switch says what the theme is, and what a click does --------- */

const THEMES = {
  system: { mark: "◐", label: "Auto", next: "light" },
  light: { mark: "☀", label: "Light", next: "dark" },
  dark: { mark: "☾", label: "Dark", next: "auto (follow the system)" },
};
const themePref = signal(window.csgTheme ? window.csgTheme.pref() : "system");
window.addEventListener("csg-theme", () => (themePref.value = window.csgTheme.pref()));

function ThemeSwitch() {
  const t = THEMES[themePref.value] || THEMES.system;
  return html`<${Button} variant="ghost" class="bar-button theme-switch" onClick=${() => window.csgTheme.cycle()}
    title=${`Theme: ${t.label.toLowerCase()}. Click for ${t.next}.`} aria-label=${`Theme: ${t.label}. Switch theme`}
    icon=${t.mark}>${t.label}<//>`;
}

/* --- who you are -------------------------------------------------------------- */

function Identity() {
  /* Changes in Futures are recorded under this name + role, and model calls record
     who asked for them. Remembered in this browser, shown on every page. */
  const named = author.value !== "strategist";
  const save = (ev) => {
    ev.preventDefault();
    const f = ev.currentTarget;
    setIdentity(f.elements.name.value, f.elements.role.value);
    f.closest("details").open = false;
    toast(author.value === "strategist"
      ? "Name cleared: changes are recorded as “strategist”."
      : `Your changes are now recorded as ${author.value}${role.value ? ` (${role.value})` : ""}.`);
  };
  return html`<details class="identity">
    <summary class=${`bar-button ${named ? "" : "unset"}`} title="Changes you make in Futures are recorded under this name">
      ${named ? `${author.value}${role.value ? ` · ${role.value}` : ""}` : "Set your name"}
    </summary>
    <form class="identity-form" onSubmit=${save}>
      <label>Name <input name="name" autocomplete="name" value=${named ? author.value : ""} placeholder="e.g. Sam Lee…" /></label>
      <label>Role <input name="role" autocomplete="organization-title" value=${role.value} placeholder="e.g. Strategist…" /></label>
      <div class="hint">Changes you make in Futures are recorded under this name, so teammates can see who wrote what.</div>
      <${Button} type="submit" variant="primary">Save<//>
    </form>
  </details>`;
}

/* --- the bar ------------------------------------------------------------------- */

/* --- logotype ----------------------------------------------------------------------
   A signal trace (a pulse on a flat line: a signal picked out of the noise) and the
   name in lowercase Kode Mono. Chosen from three in a prototype (branch
   prototype/app-bar, logotype C). */
function Logo() {
  return html`<span class="logo" aria-hidden="true">
    <svg viewBox="0 0 28 14" class="logo-trace"><polyline points="0,7 6,7 9,2 13,12 17,4 20,7 28,7" /></svg>
    <span class="logo-word">cultural signal graph</span>
  </span>`;
}

/* mode: "forecast" | "futures" — the page you are on.
   run: the open run's snapshot or summary ({ id, status, ask, mode }), or null.
   skipTo: id of the main content, for the skip link.
   Three zones: the logotype (home) on the left; the open run's question at the top
   centre — it's what the page is about; on the right, the Forecast | Futures switch
   (kept apart from the logotype, in plain sentence case so it can't read as part of
   the name), then who you are and the theme. */
export function AppBar({ mode, run = null, skipTo }) {
  const runId = run?.id || null;
  // Futures grows from extracted evidence: it opens once the run has paused at
  // sign-off or finished. Futures mode itself is always reachable from inside it.
  const futuresReady = mode === "futures" || (run && ["paused", "completed"].includes(run.status));
  const forecastHref = runId ? `/?run=${encodeURIComponent(runId)}` : "/";
  const futuresHref = runId ? `/futures?run=${encodeURIComponent(runId)}` : "/futures";
  const why = runId ? "Futures opens once this run's evidence is extracted (at sign-off)." : "Open a forecast run to explore its futures.";
  useEffect(() => {
    document.documentElement.dataset.mode = mode;
  }, [mode]);
  return html`<header id="topbar" class="app-bar">
    <a class="skip-link" href=${`#${skipTo}`}>Skip to content</a>
    <div class="bar-left">
      <a class="brand" href="/" title="Cultural Signal Graph — all forecast runs" aria-label="Cultural Signal Graph — all forecast runs"><${Logo} /></a>
      ${run?.mode === "fixture" ? html`<${Chip} tone="warn" title="Recorded outputs — no model, no network">fixture mode<//>` : null}
    </div>
    <div class="bar-center">
      ${run?.ask ? html`<span class="bar-title" title=${run.ask.question}>${run.ask.question}</span>` : null}
    </div>
    <div class="bar-right">
      <nav class="mode-switch" aria-label="Mode">
        <a href=${forecastHref} class=${mode === "forecast" ? "on" : ""} aria-current=${mode === "forecast" ? "page" : undefined}>Forecast</a>
        ${futuresReady
          ? html`<a href=${futuresHref} class=${mode === "futures" ? "on" : ""} aria-current=${mode === "futures" ? "page" : undefined}>Futures</a>`
          : html`<span class="disabled" aria-disabled="true" title=${why}>Futures</span>`}
      </nav>
      <span class="bar-divider" aria-hidden="true"></span>
      <${Identity} />
      <${ThemeSwitch} />
    </div>
  </header>`;
}

/* --- breadcrumb: the way back up, at the top of the page -------------------------
   items: [{ label, href, onClick? }] — each is a level above this page. */
export function Crumbs({ items }) {
  if (!items?.length) return null;
  return html`<nav class="crumbs" aria-label="Breadcrumb"><ol>
    ${items.map((it) => html`<li key=${it.label}>
      <a href=${it.href} onClick=${it.onClick ? (ev) => {
        if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.button) return; // new tab: let the link work
        ev.preventDefault();
        it.onClick();
      } : undefined}>${it.label}</a>
    </li>`)}
  </ol></nav>`;
}
