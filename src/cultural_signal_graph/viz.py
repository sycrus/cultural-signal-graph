"""Interactive graph explorer — a self-contained HTML file (issue #11).

Serializes the RDF graph into Cytoscape elements (nodes + edges with type, confidence,
temporal validity, provenance) and renders a self-contained `graph.html` using
Cytoscape.js from a CDN — no server, matches the project's zero-infrastructure goal.
Clicking a node highlights its neighborhood (claim -> sources -> provenance); flagged
signals and gated cross-domain edges are visually distinct.

When served by the web app (`notes_url`, issue #25) the detail panel also lists and
accepts notes for the selected node/edge — a pure overlay. The exported artifact
omits it, so the file stays offline and self-contained.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from rdflib.namespace import RDF, RDFS

from .graph import CSG
from .models import CSG_NS, GAMING_NS, TECH_NS, ForecastRun
from .tracing import aggregate_usage

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def _read_cytoscape() -> str:
    """The vendored Cytoscape.js, inlined so graph.html works offline."""
    return (_STATIC_DIR / "cytoscape.min.js").read_text(encoding="utf-8")


def _read_theme() -> tuple[str, str]:
    """The design tokens and the theme switcher (#46), inlined for the same reason:
    the graph's colors come from tokens.css, light or dark, like the rest of the app."""
    tokens = (_STATIC_DIR / "tokens.css").read_text(encoding="utf-8")
    fonts = _STATIC_DIR / "vendor" / "fonts"

    def embed(m: re.Match) -> str:
        data = base64.b64encode((fonts / m.group(1)).read_bytes()).decode("ascii")
        return "data:font/woff2;base64," + data

    tokens = re.sub(r"/static/vendor/fonts/([\w.-]+\.woff2)", embed, tokens)
    return tokens, (_STATIC_DIR / "theme.js").read_text(encoding="utf-8")


_ONTOLOGY_NAMESPACES = (CSG_NS, TECH_NS, GAMING_NS)

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Cultural Signal Graph</title>
<script>__THEME_JS__</script>
<script>__CYTOSCAPE__</script>
<style>__TOKENS_CSS__</style>
<style>
  html, body { margin: 0; height: 100%; overflow: hidden; font-family: var(--font-sans); background: var(--card); color: var(--ink); }
  #cy { width: 100%; height: 100%; display: block; }
  .floating { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius-md); }
  #legend { position: absolute; top: 12px; left: 12px; padding: 10px 12px; font-size: var(--text-sm); display: grid; gap: 6px; max-width: 220px; }
  .legend-title { font-family: var(--font-display); font-size: var(--text-xs); letter-spacing: var(--tracking-label); text-transform: uppercase; color: var(--muted); }
  .chips { display: flex; flex-wrap: wrap; gap: 5px; }
  .chip { padding: 3px 8px; border-radius: var(--radius-sm); border: 1.5px solid; font-size: var(--text-xs); line-height: 1.3; }
  .chip.entity { background: var(--xedge-soft); border-color: var(--graph-entity); color: var(--xedge-ink); font-family: var(--font-display); letter-spacing: var(--tracking-label); text-transform: uppercase; font-weight: 600; }
  .chip.signal { background: var(--evidence-soft); border-color: var(--evidence-line); color: var(--evidence-ink); }
  .chip.flagged { background: var(--warn-soft); border-color: var(--warn); color: var(--warn-ink); }
  .chip.source { background: var(--card); border-color: var(--border); border-style: dashed; color: var(--muted); }
  .chip.projection { background: var(--futures-soft); border-color: var(--futures); color: var(--futures-ink); }
  .lines { display: grid; gap: 3px; font-size: var(--text-xs); color: var(--muted); }
  .line { display: inline-block; width: 22px; vertical-align: middle; margin-right: 6px; border-top: 2px solid var(--graph-about); }
  .line.equiv { border-top-color: var(--graph-equiv); }
  .line.pending { border-top: 2px dashed var(--graph-equiv-pending); }
  .line.grows { border-top: 2px dotted var(--futures-line); }
  #detail { position: absolute; top: 12px; right: 12px; width: 300px; padding: 12px; box-shadow: var(--shadow-md); display: none; }
  #detail a { color: var(--accent); }
  .notes { margin-top: 10px; border-top: 1px solid var(--border-soft); padding-top: 8px; }
  .notes-title { font-size: var(--text-xs); color: var(--muted); text-transform: uppercase; letter-spacing: .4px; margin-bottom: 4px; }
  .note { font-size: var(--text-sm); margin: 4px 0; white-space: pre-wrap; }
  .note-meta { display: block; font-size: 10px; color: var(--faint); }
  .note-form { display: flex; gap: 4px; margin-top: 6px; }
  input, button { font: inherit; color: var(--ink); background: var(--card); border: 1px solid var(--border); }
  .note-form input { font-size: var(--text-xs); padding: 3px 6px; border-radius: 4px; min-width: 0; }
  .note-form button { font-size: var(--text-xs); padding: 3px 8px; border-radius: 4px; cursor: pointer; }
  #toolbar { position: absolute; top: 12px; left: 50%; transform: translateX(-50%);
    display: flex; gap: 6px; align-items: center; }
  #toolbar input { padding: 4px 8px; border-radius: var(--radius-sm); font-size: var(--text-sm); width: 160px; }
  #toolbar button { padding: 4px 8px; border-radius: var(--radius-sm); font-size: var(--text-sm); cursor: pointer; }
  #usage { position: absolute; bottom: 12px; left: 12px; padding: 8px 12px; font-size: var(--text-sm); }
</style>
</head>
<body>
<div id="cy"></div>
<div id="toolbar">
  <input id="search" type="text" placeholder="Search nodes…" />
  <button id="btn-fit" title="Fit graph to view">Fit</button>
  <button id="btn-cose" title="Force-directed layout">Cose</button>
  <button id="btn-grid" title="Grid layout">Grid</button>
</div>
<div id="legend" class="floating">
  <div class="legend-title">Key</div>
  <div class="chips">
    <span class="chip entity">Entity</span>
    <span class="chip signal">Signal</span>
    <span class="chip flagged">Flagged signal</span>
    <span class="chip source">source</span>
    <span class="chip projection legend-futures" style="display:none">Projection</span>
  </div>
  <div class="lines">
    <div><span class="line"></span>signal is about an entity</div>
    <div><span class="line equiv"></span>cross-domain link, signed off</div>
    <div><span class="line pending"></span>cross-domain link, awaiting sign-off</div>
    <div class="legend-futures" style="display:none"><span class="line grows"></span>projection grows from</div>
  </div>
</div>
<details id="usage" class="floating">
  <summary>Usage</summary>
  __USAGE__
</details>
<div id="detail" class="floating"></div>
<script>
const data = __DATA__;
const NOTES_URL = "__NOTES_URL__" || null;
let NOTES = [];
if (NOTES_URL) {
  fetch(NOTES_URL).then((r) => r.json()).then((ns) => { NOTES = ns; });
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text == null ? '' : String(text);
  return div.innerHTML;
}

function renderNotes(targetId) {
  const mine = NOTES.filter((n) => n.target_id === targetId);
  const items = mine.map((n) =>
    `<div class="note"><span class="note-meta">${escapeHtml(n.author)} · ${escapeHtml(n.created_at)}</span>${escapeHtml(n.text)}</div>`
  ).join('');
  return `<div class="notes">
    <div class="notes-title">Notes (${mine.length})</div>
    ${items}
    <div class="note-form">
      <input id="note-author" placeholder="Your name" style="width:90px">
      <input id="note-text" placeholder="Add a note…" style="flex:1">
      <button id="note-add">Add</button>
    </div>
  </div>`;
}

function bindNoteForm(targetId, targetKind) {
  const btn = document.getElementById('note-add');
  if (!btn) return;
  btn.onclick = () => {
    const author = document.getElementById('note-author').value.trim() || 'strategist';
    const text = document.getElementById('note-text').value.trim();
    if (!text) return;
    fetch(NOTES_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_id: targetId, target_kind: targetKind, text, author }),
    })
      .then((r) => r.json())
      .then((note) => {
        NOTES.push(note);
        document.getElementById('detail').innerHTML = detailHtml(targetId, targetKind);
        bindNoteForm(targetId, targetKind);
      });
  };
}

if (data.nodes.some((n) => n.data.kind === 'projection')) {
  document.querySelectorAll('.legend-futures').forEach((el) => { el.style.display = ''; });
}

// Every color comes from tokens.css; restyled when the theme switches.
// Nodes are panels with their words inside, like the cards in futures mode:
// the fill and border say what kind of thing it is, the text says which one.
const tok = (name) => window.csgTheme.token(name);
const glowOn = () => Number(tok('--glow-on')) || 0;
const PANEL_W = { entity: 190, signal: 220, source: 150, projection: 220, reference: 210 };
const FONT = { entity: 12.5, source: 10.5 };
const BODY = 12;
const SHOUT = 28; // entity names up to this long are set as uppercase labels
const panelW = (n) => {
  const max = PANEL_W[n.data('kind')] || 160;
  const size = FONT[n.data('kind')] || BODY;
  const len = (n.data('label') || '').length;
  const caps = n.data('kind') === 'entity' && len <= SHOUT ? 1.25 : 1;
  return Math.max(64, Math.min(max, len * size * 0.56 * caps + 22));
};
const panelH = (n) => {
  const size = FONT[n.data('kind')] || BODY;
  const perLine = Math.max(1, Math.floor((panelW(n) - 18) / (size * 0.56)));
  const lines = Math.min(4, Math.ceil(((n.data('label') || '').length || 1) / perLine));
  return lines * size * 1.3 + 16;
};
function graphStyle() {
  const glow = glowOn();
  return [
    { selector: 'node', style: {
      'label': 'data(label)', 'shape': 'round-rectangle', 'corner-radius': 6,
      'width': panelW, 'height': panelH, 'text-valign': 'center', 'text-halign': 'center',
      'text-wrap': 'wrap', 'text-max-width': (n) => panelW(n) - 16, 'text-justification': 'left',
      'font-size': (n) => FONT[n.data('kind')] || BODY, 'line-height': 1.3,
      'font-family': tok('--font-sans'), 'color': tok('--ink'),
      'background-color': tok('--card'), 'border-width': 1.5, 'border-color': tok('--border'),
      'underlay-padding': 5, 'underlay-opacity': 0, 'underlay-shape': 'round-rectangle',
      'transition-property': 'opacity, underlay-opacity', 'transition-duration': 150,
    }},
    { selector: 'node[kind = "entity"]', style: {
      'background-color': tok('--xedge-soft'), 'border-color': tok('--graph-entity'), 'border-width': 2,
      'color': tok('--xedge-ink'), 'font-weight': 600, 'text-justification': 'center',
      'font-family': (n) => ((n.data('label') || '').length <= SHOUT ? tok('--font-display') : tok('--font-sans')),
      'text-transform': (n) => ((n.data('label') || '').length <= SHOUT ? 'uppercase' : 'none'),
      'underlay-color': tok('--graph-entity'), 'underlay-opacity': glow * 0.18,
    }},
    { selector: 'node[kind = "signal"]', style: {
      'background-color': tok('--evidence-soft'), 'border-color': tok('--evidence-line'), 'color': tok('--evidence-ink'),
    }},
    { selector: 'node[kind = "signal"][flagged = "true"]', style: {
      'background-color': tok('--warn-soft'), 'border-color': tok('--warn'), 'color': tok('--warn-ink'),
    }},
    { selector: 'node[kind = "source"]', style: {
      'border-style': 'dashed', 'color': tok('--muted'), 'text-justification': 'center',
    }},
    { selector: 'node[kind = "projection"]', style: {
      'background-color': tok('--futures-soft'), 'border-color': tok('--futures'), 'color': tok('--futures-ink'),
    }},
    { selector: 'node[kind = "reference"]', style: {
      'border-style': 'dashed', 'border-color': tok('--evidence'), 'color': tok('--evidence-ink'),
    }},
    { selector: 'node:selected', style: {
      'border-width': 2.5, 'underlay-color': tok('--accent'), 'underlay-opacity': 0.25 + glow * 0.15,
    }},
    { selector: 'edge', style: { 'curve-style': 'bezier', 'width': 1.5, 'line-color': tok('--graph-edge'), 'target-arrow-shape': 'triangle', 'target-arrow-color': tok('--graph-edge'), 'arrow-scale': 0.8 } },
    { selector: 'edge[kind = "about"]', style: { 'line-color': tok('--graph-about'), 'target-arrow-color': tok('--graph-about'), 'width': 2 } },
    { selector: 'edge[kind = "equivalence"]', style: { 'line-color': tok('--graph-equiv'), 'target-arrow-color': tok('--graph-equiv'), 'width': 2.5 } },
    { selector: 'edge[kind = "equivalence"][status != "real"]', style: { 'line-style': 'dashed', 'line-color': tok('--graph-equiv-pending'), 'target-arrow-color': tok('--graph-equiv-pending') } },
    { selector: 'edge[kind = "growsFrom"]', style: { 'line-color': tok('--futures-line'), 'target-arrow-color': tok('--futures-line'), 'line-style': 'dotted', 'width': 1.5 } },
    { selector: '.dimmed', style: { 'opacity': 0.12 } },
  ];
}

// Panels need room: strong repulsion and a large overlap penalty keep them apart.
const COSE = { name: 'cose', fit: true, padding: 40, nodeRepulsion: 40000, idealEdgeLength: 170, nodeOverlap: 60,
  componentSpacing: 120, gravity: 0.6, numIter: 2500 };
// Never fit so far out that the words in the panels can't be read: past that,
// sit at a readable zoom on the busiest entity and let the viewer pan.
const READABLE = 0.8;
// The force layout discourages overlap but doesn't forbid it; panels that still
// touch are pushed apart along the shorter axis until none do (or 60 passes).
const GAP = 14;
function separate() {
  const ns = cy.nodes(':visible').toArray();
  for (let pass = 0; pass < 60; pass++) {
    let moved = false;
    for (let i = 0; i < ns.length; i++) {
      for (let j = i + 1; j < ns.length; j++) {
        const a = ns[i].position(), b = ns[j].position();
        const ox = (ns[i].width() + ns[j].width()) / 2 + GAP - Math.abs(a.x - b.x);
        const oy = (ns[i].height() + ns[j].height()) / 2 + GAP - Math.abs(a.y - b.y);
        if (ox <= 0 || oy <= 0) continue;
        moved = true;
        if (ox < oy) {
          const d = (ox / 2) * (a.x <= b.x ? -1 : 1);
          ns[i].position({ x: a.x + d, y: a.y }); ns[j].position({ x: b.x - d, y: b.y });
        } else {
          const d = (oy / 2) * (a.y <= b.y ? -1 : 1);
          ns[i].position({ x: a.x, y: a.y + d }); ns[j].position({ x: b.x, y: b.y - d });
        }
      }
    }
    if (!moved) break;
  }
}
function readableFit() {
  separate();
  cy.fit(undefined, 40);
  if (cy.zoom() >= READABLE) return;
  const hub = cy.nodes('[kind = "entity"]').max((n) => n.degree()).ele || cy.nodes()[0];
  cy.zoom(READABLE);
  if (hub) cy.center(hub);
}

const cy = cytoscape({
  container: document.getElementById('cy'),
  elements: data,
  style: graphStyle(),
  layout: { ...COSE, animate: false },
});

function detailHtml(id, kind) {
  const el = cy.getElementById(id);
  const d = el.data();
  let html = '<b>' + escapeHtml(d.kind) + '</b><br>' + escapeHtml(d.statement || d.label);
  if (d.kind === 'source') html += '<br><a href="' + escapeHtml(d.id) + '" target="_blank" rel="noopener">' + escapeHtml(d.id) + ' &#8599;</a>';
  if (d.confidence) html += '<br>confidence: ' + escapeHtml(d.confidence);
  if (d.valid) html += '<br>valid: ' + escapeHtml(d.valid);
  if (d.credibility) html += '<br>source credibility: ' + escapeHtml(d.credibility);
  if (d.status) html += '<br>gate status: ' + escapeHtml(d.status);
  if (NOTES_URL) html += renderNotes(id);
  return html;
}

function showDetail(ele) {
  const d = ele.data();
  document.getElementById('detail').innerHTML = detailHtml(d.id, d.kind);
  document.getElementById('detail').style.display = 'block';
  bindNoteForm(d.id, d.kind);
}

cy.on('tap', 'node, edge', (evt) => {
  const ele = evt.target;
  cy.elements().addClass('dimmed');
  ele.closedNeighborhood().removeClass('dimmed');
  showDetail(ele);
});

cy.on('tap', (evt) => {
  if (evt.target === cy) {
    cy.elements().removeClass('dimmed');
    document.getElementById('detail').style.display = 'none';
  }
});

document.getElementById('search').addEventListener('input', (e) => {
  const q = e.target.value.trim().toLowerCase();
  cy.elements().removeClass('dimmed');
  if (!q) return;
  cy.nodes().addClass('dimmed');
  cy.nodes().filter(n => (n.data('label') || '').toLowerCase().includes(q)).removeClass('dimmed');
});

window.addEventListener('csg-theme', () => cy.style(graphStyle()));

cy.ready(readableFit);
document.getElementById('btn-fit').onclick = () => cy.fit(undefined, 30);
document.getElementById('btn-cose').onclick = () => cy.layout({ ...COSE, animate: false, stop: readableFit }).run();
document.getElementById('btn-grid').onclick = () => cy.layout({ name: 'grid', animate: true, fit: true, padding: 30 }).run();
</script>
</body>
</html>
"""


def _value(graph, subject, predicate):
    obj = graph.value(subject, predicate)
    return str(obj) if obj is not None else None


def _short_uri(uri: str) -> str:
    return uri.rstrip("/").rsplit("/", 1)[-1]


def _shorten(text: str, limit: int = 22) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_cyto_elements(forecast: ForecastRun) -> dict:
    """Build Cytoscape nodes/edges from a forecast's RDF graph + flags."""
    graph = forecast.graph
    flagged = {flag.signal_id for flag in forecast.flags}

    nodes: list[dict] = []
    edges: list[dict] = []

    signal_nodes = set(graph.subjects(RDF.type, CSG.Signal))
    for signal in signal_nodes:
        sid = str(signal)
        local_id = sid.rsplit("#", 1)[-1]
        is_flagged = local_id in flagged
        statement = _value(graph, signal, RDFS.label) or local_id
        nodes.append(
            {
                "data": {
                    "id": sid,
                    "label": _shorten(statement, 72),
                    "statement": statement,
                    "kind": "signal",
                    "confidence": _value(graph, signal, CSG.confidence),
                    "valid": _value(graph, signal, CSG.validFrom)
                    + " -> "
                    + (_value(graph, signal, CSG.validUntil) or ""),
                    "flagged": "true" if is_flagged else "false",
                }
            }
        )
        about = _value(graph, signal, CSG.about)
        if about:
            edges.append(
                {"data": {"id": f"about:{sid}:{about}", "source": sid, "target": about, "kind": "about"}}
            )
        source = _value(graph, signal, CSG.hasSource)
        if source:
            edges.append(
                {"data": {"id": f"hasSource:{sid}:{source}", "source": sid, "target": source, "kind": "hasSource"}}
            )

    for entity in graph.subjects(RDFS.label, None):
        if entity in signal_nodes:
            continue
        if str(entity).startswith(_ONTOLOGY_NAMESPACES):
            continue  # ontology term, not instance data
        nodes.append(
            {
                "data": {
                    "id": str(entity),
                    "label": _value(graph, entity, RDFS.label),
                    "kind": "entity",
                }
            }
        )

    for source in graph.subjects(CSG.credibility, None):
        nodes.append(
            {
                "data": {
                    "id": str(source),
                    "label": _shorten(_short_uri(str(source)), 20),
                    "kind": "source",
                    "credibility": _value(graph, source, CSG.credibility),
                }
            }
        )

    for edge_node in graph.subjects(RDF.type, CSG.EquivalenceEdge):
        edges.append(
            {
                "data": {
                    "id": str(edge_node),
                    "source": _value(graph, edge_node, CSG.leftEntity),
                    "target": _value(graph, edge_node, CSG.rightEntity),
                    "kind": "equivalence",
                    "status": _value(graph, edge_node, CSG.status),
                }
            }
        )

    return {"nodes": nodes, "edges": edges}


def render_html(elements: dict, usage: dict | None = None, notes_url: str | None = None) -> str:
    """Render a self-contained, offline HTML file around the elements.

    `notes_url` opts the page into the annotations overlay (#25); the exported
    artifact passes None so it stays self-contained."""
    tokens_css, theme_js = _read_theme()
    html = _HTML_TEMPLATE.replace("__TOKENS_CSS__", tokens_css).replace("__THEME_JS__", theme_js)
    html = html.replace("__DATA__", json.dumps(elements))
    html = html.replace("__USAGE__", _usage_html(usage) if usage else "")
    html = html.replace("__NOTES_URL__", notes_url or "")
    return html.replace("__CYTOSCAPE__", _read_cytoscape())


def write_graph_html(forecast: ForecastRun, path) -> None:
    """Write the interactive graph explorer HTML for a forecast."""
    usage = aggregate_usage(forecast.usage) if forecast.usage else None
    path.write_text(render_html(build_cyto_elements(forecast), usage), encoding="utf-8")


def _usage_html(usage: dict) -> str:
    if not usage.get("calls"):
        return "<div>no model calls recorded</div>"
    rows = "".join(
        f'<div>{c["model"]}: {c["input_tokens"]} in / {c["output_tokens"]} out</div>'
        for c in usage["calls"]
    )
    return (
        f'<div><b>total: {usage["total_tokens"]} tokens</b> '
        f'({usage["input_tokens"]} in / {usage["output_tokens"]} out)</div>'
        + rows
    )
