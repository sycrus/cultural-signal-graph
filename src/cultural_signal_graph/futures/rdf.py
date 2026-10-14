"""Explorations in RDF (ADR-0007): each exploration is a named graph beside the run's
evidence graph, so projections can point at the very signal nodes they grow from
while staying separable (and never part of the forecast's `graph.ttl`)."""

from __future__ import annotations

from rdflib import Dataset, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

from ..models import EX_NS

CSGF = Namespace("https://cultural-signal-graph.dev/futures#")
EX = Namespace(EX_NS)
FUTURES_BASE = "https://cultural-signal-graph.dev/futures/"


def exploration_uri(exp_id: str) -> URIRef:
    return URIRef(f"{FUTURES_BASE}{exp_id}")


def node_uri(state: dict, node_id: str) -> URIRef:
    """Evidence anchors keep their graph URI (`ex:<id>`); projections and
    futures-scoped references live under the exploration."""
    anchor = state["anchors"].get(node_id)
    if anchor is not None and anchor.get("scope") not in ("futures", "promoted"):
        return EX[node_id]
    return URIRef(f"{exploration_uri(state['exploration']['id'])}#{node_id}")


def exploration_graph(state: dict, graph: Graph | None = None) -> Graph:
    g = graph if graph is not None else Graph()
    g.bind("csgf", CSGF)
    g.bind("ex", EX)
    e = state["exploration"]
    exp = exploration_uri(e["id"])
    g.add((exp, RDF.type, CSGF.Exploration))
    g.add((exp, CSGF.goal, Literal(e["goal"])))
    g.add((exp, CSGF.horizonYears, Literal(e["horizon"], datatype=XSD.integer)))
    g.add((exp, CSGF.orders, Literal(e["orders"], datatype=XSD.integer)))
    g.add((exp, CSGF.startYear, Literal(e["start_year"], datatype=XSD.integer)))
    for a in state["anchors"].values():
        if a.get("scope") in ("futures", "promoted"):
            ref = node_uri(state, a["id"])
            g.add((ref, RDF.type, CSGF.Reference))
            g.add((ref, RDFS.label, Literal(a["text"])))
            g.add((ref, CSGF.sourceURI, Literal(a["source_uri"], datatype=XSD.anyURI)))
            g.add((ref, CSGF.inExploration, exp))
        g.add((exp, CSGF.anchor, node_uri(state, a["id"])))
    for p in state["projections"].values():
        node = node_uri(state, p["id"])
        g.add((node, RDF.type, CSGF.Projection))
        g.add((node, RDFS.label, Literal(p["statement"])))
        g.add((node, CSGF.inExploration, exp))
        g.add((node, CSGF.order, Literal(p["order"], datatype=XSD.integer)))
        g.add((node, CSGF.windowStart, Literal(str(p["window"][0]), datatype=XSD.gYear)))
        g.add((node, CSGF.windowEnd, Literal(str(p["window"][1]), datatype=XSD.gYear)))
        g.add((node, CSGF.origin, Literal(p["origin"])))
        if p.get("baseline"):
            g.add((node, CSGF.baseline, Literal(True)))
        if p.get("discontinuity"):
            g.add((node, CSGF.discontinuity, Literal(True)))
        for src in p["parents"] + p["anchors"]:
            if src in state["projections"] or src in state["anchors"]:
                g.add((node, CSGF.growsFrom, node_uri(state, src)))
        for lens, tags in state.get("tags", {}).items():
            if p["id"] in tags:
                g.add((node, CSGF[f"{lens}Tag"], Literal(tags[p["id"]]["value"])))
    return g


def run_dataset(evidence: Graph | None, states: list[dict]) -> Dataset:
    """The run's RDF: the evidence graph as the default graph, one named graph per
    exploration."""
    ds = Dataset()
    ds.bind("csgf", CSGF)
    ds.bind("ex", EX)
    if evidence is not None:
        for triple in evidence:
            ds.default_graph.add(triple)
    for state in states:
        exploration_graph(state, ds.graph(exploration_uri(state["exploration"]["id"])))
    return ds
