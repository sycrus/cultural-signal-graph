"""Interactive graph explorer — a self-contained HTML file (issue #11).

Serializes the RDF graph into Cytoscape elements (nodes + edges with type, confidence,
temporal validity, provenance) and renders a self-contained `graph.html` using
Cytoscape.js from a CDN — no server, matches the project's zero-infrastructure goal.
Clicking a node highlights its neighborhood (claim -> sources -> provenance); flagged
signals and gated cross-domain edges are visually distinct.
"""

from __future__ import annotations

import json
from pathlib import Path

from rdflib.namespace import RDF, RDFS

from .graph import CSG
from .models import CSG_NS, GAMING_NS, TECH_NS, ForecastRun
from .tracing import aggregate_usage

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def _read_cytoscape() -> str:
    """The vendored Cytoscape.js, inlined so graph.html works offline."""
    return (_STATIC_DIR / "cytoscape.min.js").read_text(encoding="utf-8")

_ONTOLOGY_NAMESPACES = (CSG_NS, TECH_NS, GAMING_NS)

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Cultural Signal Graph</title>
<script>__CYTOSCAPE__</script>
<style>
  html, body { margin: 0; height: 100%; overflow: hidden; font-family: system-ui, sans-serif; }
  #cy { width: 100%; height: 100%; display: block; }
  #legend { position: absolute; top: 12px; left: 12px; background: #fff;
    border: 1px solid #d1d5db; border-radius: 8px; padding: 8px 12px; font-size: 12px; }
  #legend .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 5px; vertical-align: middle; }
  #detail { position: absolute; top: 12px; right: 12px; width: 300px; background: #fff;
    border: 1px solid #d1d5db; border-radius: 8px; padding: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.12); display: none; }
  #toolbar { position: absolute; top: 12px; left: 50%; transform: translateX(-50%);
    display: flex; gap: 6px; align-items: center; }
  #toolbar input { padding: 4px 8px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 12px; width: 160px; }
  #toolbar button { padding: 4px 8px; border: 1px solid #d1d5db; background: #fff; border-radius: 6px; font-size: 12px; cursor: pointer; }
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
<div id="legend">
  <div><span class="dot" style="background:#3b82f6"></span>entity</div>
  <div><span class="dot" style="background:#22c55e"></span>signal (confident)</div>
  <div><span class="dot" style="background:#ef4444"></span>signal (conflict/flag)</div>
  <div><span class="dot" style="background:#9ca3af"></span>source</div>
  <div style="margin-top:4px">dashed purple = gated cross-domain edge</div>
</div>
<details id="usage" style="position:absolute; bottom:12px; left:12px; background:#fff; border:1px solid #d1d5db; border-radius:8px; padding:8px 12px; font-size:12px;">
  <summary>Usage</summary>
  __USAGE__
</details>
<div id="detail"></div>
<script>
const data = __DATA__;

const cy = cytoscape({
  container: document.getElementById('cy'),
  elements: data,
  style: [
    { selector: 'node', style: {
      'label': 'data(label)', 'font-size': 9, 'text-valign': 'bottom', 'text-halign': 'center',
      'text-wrap': 'ellipsis', 'text-max-width': '90px', 'color': '#111827'
    }},
    { selector: 'node[kind = "entity"]', style: { 'background-color': '#3b82f6', 'shape': 'ellipse', 'width': 56, 'height': 56 } },
    { selector: 'node[kind = "signal"]', style: { 'background-color': '#22c55e', 'shape': 'round-rectangle' } },
    { selector: 'node[kind = "signal"][flagged = "true"]', style: { 'background-color': '#ef4444' } },
    { selector: 'node[kind = "source"]', style: { 'background-color': '#9ca3af', 'shape': 'hexagon' } },
    { selector: 'edge', style: { 'curve-style': 'bezier', 'width': 1.5, 'line-color': '#cbd5e1', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#cbd5e1' } },
    { selector: 'edge[kind = "about"]', style: { 'line-color': '#60a5fa', 'target-arrow-color': '#60a5fa', 'width': 2 } },
    { selector: 'edge[kind = "equivalence"]', style: { 'line-color': '#a855f7', 'target-arrow-color': '#a855f7', 'width': 2.5 } },
    { selector: 'edge[kind = "equivalence"][status != "real"]', style: { 'line-style': 'dashed', 'line-color': '#c084fc', 'target-arrow-color': '#c084fc' } },
    { selector: '.dimmed', style: { 'opacity': 0.12 } },
  ],
  layout: { name: 'cose', animate: false, fit: true, padding: 30, nodeRepulsion: 6000, idealEdgeLength: 90 },
});

function showDetail(node) {
  const d = node.data();
  let html = '<b>' + d.kind + '</b><br>' + (d.statement || d.label);
  if (d.kind === 'source') html += '<br><a href="' + d.id + '" target="_blank" rel="noopener">' + d.id + ' &#8599;</a>';
  if (d.confidence) html += '<br>confidence: ' + d.confidence;
  if (d.valid) html += '<br>valid: ' + d.valid;
  if (d.credibility) html += '<br>source credibility: ' + d.credibility;
  document.getElementById('detail').innerHTML = html;
  document.getElementById('detail').style.display = 'block';
}

cy.on('tap', 'node', (evt) => {
  const node = evt.target;
  cy.elements().addClass('dimmed');
  node.closedNeighborhood().removeClass('dimmed');
  showDetail(node);
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

document.getElementById('btn-fit').onclick = () => cy.fit(undefined, 30);
document.getElementById('btn-cose').onclick = () => cy.layout({ name: 'cose', animate: true, fit: true, padding: 30 }).run();
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
                    "label": _shorten(statement),
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
            edges.append({"data": {"source": sid, "target": about, "kind": "about"}})
        source = _value(graph, signal, CSG.hasSource)
        if source:
            edges.append({"data": {"source": sid, "target": source, "kind": "hasSource"}})

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
                    "source": _value(graph, edge_node, CSG.leftEntity),
                    "target": _value(graph, edge_node, CSG.rightEntity),
                    "kind": "equivalence",
                    "status": _value(graph, edge_node, CSG.status),
                }
            }
        )

    return {"nodes": nodes, "edges": edges}


def render_html(elements: dict, usage: dict | None = None) -> str:
    """Render a self-contained, offline HTML file around the elements."""
    html = _HTML_TEMPLATE.replace("__DATA__", json.dumps(elements))
    html = html.replace("__USAGE__", _usage_html(usage) if usage else "")
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
