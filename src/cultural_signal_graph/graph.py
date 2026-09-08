"""Graph construction: extraction + resolved edges -> RDFLib graph (issues #2, #5).

Real plumbing. Each signal becomes a `csg:Signal` node carrying confidence,
temporal validity, and provenance. Cross-domain equivalence edges are reified as
`csg:EquivalenceEdge` nodes; an edge approved at the HITL gate additionally
asserts the `csg:equivalentTo` triple and gets status "real".
"""

from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

from .models import CSG_NS, EX_NS, EquivalenceEdge, Extraction, SourceDoc

CSG = Namespace(CSG_NS)
EX = Namespace(EX_NS)

ONT_DIR = Path(__file__).resolve().parent / "ontology"

_ONTOLOGY_FILES = ("upper.ttl", "tech.ttl", "gaming.ttl")


def _edge_status(edge_id: str, decisions: dict[str, bool]) -> str:
    decision = decisions.get(edge_id)
    if decision is True:
        return "real"
    if decision is False:
        return "rejected"
    return "proposed"


def build_graph(
    extraction: Extraction,
    edges: list[EquivalenceEdge],
    decisions: dict[str, bool],
    sources: list[SourceDoc],
) -> Graph:
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
        graph.add((node, RDFS.label, Literal(signal.text)))
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

    for edge in edges:
        node = EX[edge.id]
        status = _edge_status(edge.id, decisions)
        graph.add((node, RDF.type, CSG.EquivalenceEdge))
        graph.add((node, CSG.leftEntity, EX[edge.left_entity_id]))
        graph.add((node, CSG.rightEntity, EX[edge.right_entity_id]))
        graph.add((node, CSG.confidence, Literal(str(edge.confidence), datatype=XSD.decimal)))
        graph.add((node, CSG.status, Literal(status)))
        if status == "real":
            graph.add((EX[edge.left_entity_id], CSG.equivalentTo, EX[edge.right_entity_id]))

    return graph
