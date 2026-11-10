/* The design system's components (#46). Every button, chip, panel, tab set, range
   roller, node card, drawer, toast, switch and empty state in the app (the forecast
   stepper and futures mode) is one of these, styled from tokens only (ui.css, tokens.css), so light and dark,
   phosphor and LCD, apply everywhere at once.

   Motion follows the handscroll: drawers and toasts slide in, the roller slides the
   visible window. Nothing bounces, nothing fades in from nowhere. */

import { h } from "preact";
import { useEffect, useRef } from "preact/hooks";
import { signal } from "@preact/signals";
import htm from "htm";

const html = htm.bind(h);
const cx = (...names) => names.filter(Boolean).join(" ");

/* --- Button --------------------------------------------------------------------
   variant: "primary" (one per area: the main next step), "ghost" (secondary,
   quiet), "danger" (the confirm step of something destructive), or none (default).
   busy swaps in a spinner and busyLabel, and disables it. href renders a link
   that looks like a button (navigation, not an action). */
export function Button({ variant = null, busy = false, busyLabel = null, icon = null, href = null, type = "button", class: cls, children, ...rest }) {
  const c = cx("btn", variant === "danger" ? "danger-active" : variant, cls);
  const inner = html`${busy ? html`<span class="spinner sm" aria-hidden="true"></span>` : icon ? html`<span class="btn-icon" aria-hidden="true">${icon}</span>` : null}${busy && busyLabel ? busyLabel : children}`;
  if (href) return html`<a ...${rest} class=${c} href=${href}>${inner}</a>`;
  return html`<button ...${rest} type=${type} class=${c} disabled=${rest.disabled || busy} aria-busy=${busy ? "true" : undefined}>${inner}</button>`;
}

/* --- Chip ----------------------------------------------------------------------
   A small labelled mark. tone: futures | evidence | neutral | warn | danger | ok.
   size "sm" is the in-card mark. With onClick it becomes a toggle (aria-pressed),
   lit when `on`. */
export function Chip({ tone = "futures", size = null, on = false, onClick = null, class: cls, children, ...rest }) {
  const c = cx("ui-chip", `tone-${tone}`, size, onClick && "toggle", onClick && on && "on", cls);
  if (onClick) return html`<button ...${rest} type="button" class=${c} aria-pressed=${on ? "true" : "false"} onClick=${onClick}>${children}</button>`;
  return html`<span ...${rest} class=${c}>${children}</span>`;
}

/* --- Panel ---------------------------------------------------------------------
   A raised surface. row lays its children out in a line (a toolbar, a status bar);
   flush drops the padding (a table that runs to the edges). */
export function Panel({ title = null, row = false, flush = false, class: cls, children, ...rest }) {
  return html`<section ...${rest} class=${cx("card", "ui-panel", row && "row", flush && "flush", cls)}>
    ${title ? html`<h3 class="ui-panel-title">${title}</h3>` : null}${children}
  </section>`;
}

/* --- Tabs ----------------------------------------------------------------------
   One choice from a few. variant "solid" (the lens bar: lit on the futures hue),
   "soft" (a choice inside a form). Arrow keys, Home and End move and select, as
   in any tablist. items: [{ key, label, hint?, disabled? }]. */
export function Tabs({ items, value, onChange, variant = "solid", size = null, label, class: cls }) {
  const ref = useRef(null);
  const keys = items.filter((it) => !it.disabled).map((it) => it.key);
  const onKey = (ev) => {
    const i = keys.indexOf(value);
    const next = { ArrowRight: i + 1, ArrowDown: i + 1, ArrowLeft: i - 1, ArrowUp: i - 1, Home: 0, End: keys.length - 1 }[ev.key];
    if (next == null) return;
    ev.preventDefault();
    const k = keys[(next + keys.length) % keys.length];
    onChange(k);
    requestAnimationFrame(() => ref.current?.querySelector(`[data-key="${CSS.escape(String(k))}"]`)?.focus());
  };
  return html`<div ref=${ref} role="tablist" aria-label=${label} class=${cx("ui-tabs", variant, size, cls)} onKeyDown=${onKey}>
    ${items.map((it) => {
      const on = it.key === value;
      return html`<button key=${it.key} type="button" role="tab" data-key=${it.key} aria-selected=${on ? "true" : "false"}
        tabindex=${on ? 0 : -1} class=${on ? "on" : ""} title=${it.hint} disabled=${it.disabled}
        onClick=${() => onChange(it.key)}>${it.label}</button>`;
    })}
  </div>`;
}

/* --- Roller --------------------------------------------------------------------
   The handscroll's range control: a window over [min, max] with a roller at each
   end. Drag a roller to roll that edge, drag the window to slide it; with focus,
   the arrow keys do the same (Shift for 5 at a time). Children draw inside the
   track (place them with Roller.at). */
export function Roller({ min, max, value, onChange, minSpan = 1, label = "range", class: cls, children, ...rest }) {
  const ref = useRef(null);
  const span = Math.max(max - min, 1);
  const pct = (v) => `${((v - min) / span) * 100}%`;
  const clamp = (v) => Math.min(max, Math.max(min, v));
  const set = (which, v) => {
    const [a, b] = value;
    if (which === "start") onChange([Math.min(clamp(v), b - minSpan), b]);
    else if (which === "end") onChange([a, Math.max(clamp(v), a + minSpan)]);
    else {
      const len = b - a;
      const s = Math.min(max - len, Math.max(min, v));
      onChange([s, s + len]);
    }
  };
  const drag = (which) => (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    const box = ref.current.getBoundingClientRect();
    const toValue = (clientX) => Math.round(min + ((clientX - box.left) / box.width) * span);
    const len = value[1] - value[0];
    const move = (m) => set(which, which === "move" ? toValue(m.clientX) - Math.round(len / 2) : toValue(m.clientX));
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  const keys = (which) => (ev) => {
    const step = ev.shiftKey ? 5 : 1;
    const cur = which === "end" ? value[1] : value[0];
    const next = { ArrowRight: cur + step, ArrowUp: cur + step, ArrowLeft: cur - step, ArrowDown: cur - step, Home: min, End: max }[ev.key];
    if (next == null) return;
    ev.preventDefault();
    ev.stopPropagation();
    set(which, which === "move" && ev.key === "End" ? max - (value[1] - value[0]) : next);
  };
  return html`<div ...${rest} ref=${ref} class=${cx("ui-roller", cls)}>
    ${children}
    <div class="ui-roller-window" style=${{ left: pct(value[0]), width: `calc(${pct(value[1])} - ${pct(value[0])})` }}
      tabindex="0" role="group" aria-label=${`${label}: ${value[0]} to ${value[1]} (arrow keys slide it)`}
      onPointerDown=${drag("move")} onKeyDown=${keys("move")}>
      ${["start", "end"].map((which) => html`<span key=${which} class=${`ui-roller-handle ${which}`} tabindex="0" role="slider"
        aria-label=${`${which === "start" ? "First" : "Last"} ${label}`} aria-valuemin=${min} aria-valuemax=${max}
        aria-valuenow=${which === "start" ? value[0] : value[1]} title="Drag or use the arrow keys to roll"
        onPointerDown=${drag(which)} onKeyDown=${keys(which)}></span>`)}
    </div>
  </div>`;
}
Roller.at = (min, max, v) => `${((v - min) / Math.max(max - min, 1)) * 100}%`;

/* --- NodeCard ------------------------------------------------------------------
   A node on the Scroll: a projection (order, window, marks, statement, window bar)
   or an anchor (evidence; its kind sets the hue). Positioned by the caller; slides
   when the window rolls. Focusable: Enter or Space selects it. */
export function NodeCard({ node, kind = "projection", state = {}, style, onSelect, onPointerDown = null, title, meta = null, barWidth = null }) {
  const onKeyDown = (ev) => {
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      onSelect();
    }
  };
  const flags = Object.entries(state).filter(([, v]) => v).map(([k]) => k);
  if (kind === "anchor") {
    const a = node;
    return html`<div class=${cx("anchor-card", a.kind, a.pending && "pending", a.status === "rejected" && "rejected", ...flags)}
      style=${style} title=${title || a.text} role="button" tabindex="0" aria-pressed=${state.selected ? "true" : "false"}
      onClick=${onSelect} onKeyDown=${onKeyDown}>
      <span class="anchor-kind-dot" aria-hidden="true"></span>${a.text}
    </div>`;
  }
  const p = node;
  return html`<div class=${cx("proj-node", p.baseline && "baseline", p.discontinuity && "discontinuity", p.stale && "stale", p.origin, ...flags)}
    style=${style} title=${title} role="button" tabindex=${state.rolled ? -1 : 0} aria-pressed=${state.selected ? "true" : "false"}
    onPointerDown=${onPointerDown} onClick=${onPointerDown ? null : onSelect} onKeyDown=${onKeyDown}>
    <div class="proj-meta">
      <span class="order-badge" title=${`Order ${p.order}`}>${p.order}</span>
      <span class="years">${p.window[0] === p.window[1] ? p.window[0] : `${p.window[0]}–${p.window[1]}`}</span>
      ${meta}
    </div>
    <div class="proj-text">${p.statement}</div>
    ${barWidth != null ? html`<div class="window-bar" style=${{ width: `${barWidth}px` }}></div>` : null}
  </div>`;
}

/* --- Drawer --------------------------------------------------------------------
   The right-hand panel: what is selected, or a form. Slides in from the right;
   ✕ or Escape closes it (Escape in a text field only leaves the field). */
export function Drawer({ kind, kindClass = null, onClose, label = null, class: cls, children }) {
  useEffect(() => {
    const onKey = (ev) => {
      if (ev.key !== "Escape") return;
      if (ev.target.closest?.("input, textarea, select")) return ev.target.blur();
      onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return html`<aside class=${cx("detail-panel", "ui-drawer", cls)} aria-label=${label || (typeof kind === "string" ? kind : null)}>
    <div class="ui-drawer-head">
      <div class=${cx("panel-kind", kindClass)}>${kind}</div>
      <${Button} variant="ghost" class="close" aria-label="Close" title="Close (Esc)" onClick=${onClose}>✕<//>
    </div>
    ${children}
  </aside>`;
}

/* --- Toast ---------------------------------------------------------------------
   A short note that something happened, sliding up from the bottom, gone after a
   few seconds. Optional action (usually Undo). Call toast(); render <Toasts /> once. */
const toasts = signal([]);
let toastSeq = 0;

export function dismissToast(id) {
  toasts.value = toasts.value.filter((t) => t.id !== id);
}

export function toast(text, { action = null, tone = "info", ms = 5000 } = {}) {
  const id = ++toastSeq;
  toasts.value = [...toasts.value.slice(-2), { id, text, action, tone }];
  setTimeout(() => dismissToast(id), ms);
  return id;
}

export function Toasts() {
  return html`<div class="ui-toasts" role="status" aria-live="polite">
    ${toasts.value.map((t) => html`<div key=${t.id} class=${cx("ui-toast", `tone-${t.tone}`)}>
      <span class="ui-toast-text">${t.text}</span>
      ${t.action ? html`<${Button} variant="ghost" class="ui-toast-action"
        onClick=${() => { dismissToast(t.id); t.action.run(); }}>${t.action.label}<//>` : null}
      <${Button} variant="ghost" class="ui-toast-close" aria-label="Dismiss" onClick=${() => dismissToast(t.id)}>✕<//>
    </div>`)}
  </div>`;
}

/* --- Toggle --------------------------------------------------------------------
   An on/off switch for a setting that applies at once (no Save). */
export function Toggle({ checked, onChange, label, disabled = false, title = null, class: cls }) {
  return html`<label class=${cx("ui-toggle", disabled && "disabled", cls)} title=${title}>
    <input type="checkbox" role="switch" checked=${checked} disabled=${disabled}
      onChange=${(ev) => onChange(ev.target.checked)} />
    <span class="ui-toggle-track" aria-hidden="true"><span class="ui-toggle-thumb"></span></span>
    <span class="ui-toggle-label">${label}</span>
  </label>`;
}

/* --- EmptyState ----------------------------------------------------------------
   What an empty area says: what would be here, and the one thing to do about it.
   compact for an empty cell inside something larger. */
export function EmptyState({ title, children = null, action = null, mark = "◇", compact = false, class: cls }) {
  return html`<div class=${cx("ui-empty", compact && "compact", cls)}>
    <span class="ui-empty-mark" aria-hidden="true">${mark}</span>
    <div class="ui-empty-title">${title}</div>
    ${children ? html`<div class="ui-empty-body">${children}</div>` : null}
    ${action ? html`<div class="ui-empty-action">${action}</div>` : null}
  </div>`;
}
