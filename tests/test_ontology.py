"""Validate the ontology and SHACL shapes against sample graphs."""

from pathlib import Path

import rdflib
from pyshacl import validate

ONT_DIR = Path(__file__).resolve().parents[1] / "src" / "cultural_signal_graph" / "ontology"

VALID = """
@prefix csg:  <https://cultural-signal-graph.dev/ontology#> .
@prefix tech: <https://cultural-signal-graph.dev/ontology/tech#> .
@prefix ex:   <https://cultural-signal-graph.dev/example#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

ex:iphone17 a tech:Product ;
    tech:madeBy ex:apple .
ex:apple a tech:Brand .
ex:releaseNote1 a tech:ReleaseNote .

ex:signal1 a tech:SpecSignal ;
    csg:about ex:iphone17 ;
    csg:hasSource ex:releaseNote1 ;
    csg:confidence "0.85"^^xsd:decimal ;
    csg:timestamp "2026-01-15T00:00:00Z"^^xsd:dateTime ;
    csg:hasProvenance ex:prov1 .

ex:prov1 a csg:Provenance ;
    csg:sourceURI "https://example.com/release-notes/iphone17"^^xsd:anyURI .
"""

INVALID = """
@prefix csg:  <https://cultural-signal-graph.dev/ontology#> .
@prefix ex:   <https://cultural-signal-graph.dev/example#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

ex:badSignal a csg:Signal ;
    csg:confidence "1.5"^^xsd:decimal ;
    csg:timestamp "2026-01-15T00:00:00Z"^^xsd:dateTime .
"""


def _ontology_graph() -> rdflib.Graph:
    g = rdflib.Graph()
    for name in ("upper.ttl", "tech.ttl"):
        g.parse(ONT_DIR / name, format="turtle")
    return g


def _shapes_graph() -> rdflib.Graph:
    g = rdflib.Graph()
    g.parse(ONT_DIR / "shapes.ttl", format="turtle")
    return g


def _validate(data_turtle: str):
    data = rdflib.Graph()
    data.parse(data=data_turtle, format="turtle")
    return validate(
        data_graph=data,
        shacl_graph=_shapes_graph(),
        ont_graph=_ontology_graph(),
        inference="rdfs",
    )


def test_valid_graph_conforms():
    conforms, _graph, report = _validate(VALID)
    assert conforms, report


def test_invalid_graph_is_rejected():
    conforms, _graph, report = _validate(INVALID)
    assert not conforms
    assert "source" in report.lower()
    assert "confidence" in report.lower()
