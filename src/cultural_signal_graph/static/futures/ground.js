/* Ground this: the one agent in futures mode. A bounded search for evidence FOR
   and AGAINST a projection. What it finds comes back as proposals — never added
   on its own; the strategist accepts one and it lands in the Present column as a
   futures-scoped reference recording which projection it grounds and whether it
   supports or contradicts. */

import { h } from "preact";
import { useEffect, useState } from "preact/hooks";
import htm from "htm";
import * as S from "./store.js";

const html = htm.bind(h);

export const STANCE_MARK = { support: "✓", contradict: "✗" };

export function GroundButton({ p }) {
  const busy = S.groundingPid.value != null;
  return html`<button onClick=${() => S.groundProjection(p.id)} disabled=${S.busy.value || busy}
    title="Search for evidence that supports or contradicts this projection">
    ${S.groundingPid.value === p.id ? "Grounding…" : "⌖ Ground this"}</button>`;
}

function Trail({ seq }) {
  /* The full trail — every model step's input and raw output — from the op log,
     so the in-app panel works offline like the rest of the provenance. */
  const [op, setOp] = useState(null);
  useEffect(() => {
    S.fetchOp(seq).then(setOp);
  }, [seq]);
  if (!op) return null;
  return html`${(op.steps || []).map(
    (s) => html`<details key=${s.step}>
      <summary>${s.step} · ${s.model}${s.temperature != null ? ` · temp ${s.temperature}` : ""}</summary>
      <pre>${s.input.prompt}</pre><pre>${s.output}</pre>
    </details>`,
  )}`;
}

export function GroundSection({ p }) {
  const g = S.snap.value.grounding?.[p.id];
  const busy = S.groundingPid.value === p.id;
  if (!g && !busy) return null;
  const accepted = new Set(
    S.snap.value.anchors.filter((a) => a.grounds === p.id).map((a) => a.source_uri),
  );
  const open = (g?.proposals || []).filter((pr) => !accepted.has(pr.url));
  return html`<div class="grounding">
    <h4>Ground this</h4>
    ${busy ? html`<div class="hint"><span class="spinner"></span> Searching for evidence, for and against…</div>` : null}
    ${g
      ? html`<div class="hint">
          ${g.queries.length} quer${g.queries.length === 1 ? "y" : "ies"}, ${g.examined} result${g.examined === 1 ? "" : "s"} examined.${g.errors?.length ? ` ${g.errors.length} search error${g.errors.length === 1 ? "" : "s"}.` : ""}
          <details class="ground-trail"><summary>trail</summary>
            <div class="ground-queries">${g.queries.map((q) => html`<div key=${q}>“${q}”</div>`)}</div>
            ${(g.errors || []).map(
              (e) => html`<div key=${e.query} class="ground-error" title=${e.error}>⚠ “${e.query}” — ${e.error}</div>`,
            )}
            <${Trail} seq=${g.op} />
          </details>
        </div>
        ${open.map(
          (pr) => html`<div key=${pr.url} class="ground-proposal">
            <div class="ground-proposal-head">
              <span class=${`stance ${pr.stance}`}>${STANCE_MARK[pr.stance]} ${pr.stance}</span>
              <a href=${pr.url} target="_blank" rel="noopener">${pr.title}</a>
              ${pr.backend && pr.backend !== "wikipedia" ? html`<span class="hint">${pr.backend}</span>` : null}
            </div>
            <blockquote>“${pr.excerpt}”</blockquote>
            ${pr.why ? html`<div class="hint">${pr.why}</div>` : null}
            <div class="row right">
              <button onClick=${() => S.addReference(pr.url, pr.excerpt, { stance: pr.stance, grounds: p.id })}
                disabled=${S.busy.value} title="Add to the Present column as a futures-scoped reference">
                Accept as reference</button>
            </div>
          </div>`,
        )}
        ${!open.length && g.proposals.length
          ? html`<div class="hint">Every proposal is already accepted.</div>`
          : !open.length && !busy
            ? html`<div class="hint">${g.errors?.length
                ? `The search${g.errors.length === 1 ? " failed" : "es failed"} — see the trail. Run it again.`
                : "Nothing usable came back — run it again; the queries differ each time."}</div>`
            : null}
        <div class="actions">
          <button onClick=${() => S.groundProjection(p.id)} disabled=${S.busy.value || S.groundingPid.value != null}
            title="Search again for evidence for and against this projection">↻ Search again</button>
        </div>`
      : null}
  </div>`;
}
