"""Graph construction: extracted fixtures -> RDFLib graph.

Real plumbing (issue #2). Each signal becomes a `csg:Signal` node carrying
confidence, temporal validity, and a first-class provenance node. Proposed
cross-domain equivalence edges are reified as `csg:EquivalenceEdge` nodes with
status "proposed" — the `csg:equivalentTo` predicate is deliberately *not*
asserted, which is what the HITL gate holds back until sign-off.
"""

from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

from .models import CSG_NS, EX_NS, Extraction, SourceDoc

CSG = Namespace(CSG_NS)
EX = Namespace(EX_NS)

ONT_DIR = Path(__file__).resolve().parent / "ontology"

_ONTOLOGY_FILES = ("upper.ttl", "tech.ttl", "gaming.ttl")


def build_graph(extraction: Extraction, sources: list[SourceDoc]) -> Graph:
    graph = Graph()
    for name in _ONTOLOGY_FILES:
        graph.parse(ONT_DIR / name, format="turtle")

    for source in sources:
        node = URIRef(source.uri)
        graph.add((node, RDF.type, URIRef(source.source_type)))
        graph.add((node, CSG.credibility, Literal(str(source.credibility), datatype=XSD.decimal)))

    for entity in extraction.entities:
        node = EX[entity.id]
        graph.add((node, RDF.type, URIRef(entity.entity_type)))
        graph.add((node, RDFS.label, Literal(entity.name)))

    for signal in extraction.signals:
        node = EX[signal.id]
        graph.add((node, RDF.type, CSG.Signal))
        graph.add((node, CSG.about, EX[signal.about_entity_id]))
        graph.add((node, CSG.hasSource, URIRef(signal.source_uri)))
        graph.add((node, CSG.confidence, Literal(str(signal.confidence), datatype=XSD.decimal)))
        graph.add((node, CSG.timestamp, Literal(signal.timestamp, datatype=XSD.dateTime)))
        graph.add((node, CSG.validFrom, Literal(signal.valid_from, datatype=XSD.dateTime)))
        graph.add((node, CSG.validUntil, Literal(signal.valid_until, datatype=XSD.dateTime)))

        provenance = EX[f"prov-{signal.id}"]
        graph.add((node, CSG.hasProvenance, provenance))
        graph.add((provenance, RDF.type, CSG.Provenance))
        graph.add((provenance, CSG.sourceURI, Literal(signal.source_uri, datatype=XSD.anyURI)))

    for edge in extraction.proposed_edges:
        node = EX[edge.id]
        graph.add((node, RDF.type, CSG.EquivalenceEdge))
        graph.add((node, CSG.leftEntity, EX[edge.left_entity_id]))
        graph.add((node, CSG.rightEntity, EX[edge.right_entity_id]))
        graph.add((node, CSG.confidence, Literal(str(edge.confidence), datatype=XSD.decimal)))
        graph.add((node, CSG.status, Literal("proposed")))
        # NOTE: no CSG.equivalentTo triple — the gate holds it back until sign-off.

    return graph
