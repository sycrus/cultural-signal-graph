"""Sub-ontology auto-seeding for unfamiliar categories (issue #12).

Given a category with no hand-authored ontology, `deepseek-v4-pro` proposes a minimal
sub-ontology (entity/signal/source classes) grounded in the upper ontology. The result
is built as RDF and SHACL-validated so a forecast can run in the new category.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from rdflib import Graph, Literal, Namespace
from rdflib.namespace import OWL, RDF, RDFS, XSD

from .llm import get_client
from .models import CSG_NS, SeedClass, SeedOntology, Usage

logger = logging.getLogger(__name__)

SEEDING_MODEL = "deepseek-v4-pro"

CSG = Namespace(CSG_NS)
ONT_DIR = Path(__file__).resolve().parent / "ontology"
_ONTOLOGY_FILES = ("upper.ttl", "tech.ttl", "gaming.ttl")

_SYSTEM_PROMPT = (
    "You propose a minimal sub-ontology for a domain, grounded in an upper ontology. "
    "Return a single JSON object only — no prose, no markdown fences."
)

_UPPER_CONTEXT = (
    "The upper ontology has csg:Entity (a thing that can trend), csg:Event (subclass of "
    "Entity), csg:Signal (observed evidence), and csg:Source (where a signal came from). "
    "A sub-ontology extends these with domain-specific subclasses. For example, the tech "
    "sub-ontology defines tech:Product and tech:Brand (subclass csg:Entity), "
    "tech:SpecSignal (subclass csg:Signal), and tech:ReleaseNote (subclass csg:Source)."
)


def _build_prompt(category: str) -> str:
    return (
        f'Propose a minimal sub-ontology for the "{category}" domain.\n\n'
        f"{_UPPER_CONTEXT}\n\n"
        'Return JSON: {"classes": [{"name", "kind"}]} where kind is one of '
        '"entity", "signal", "source". Include 2-3 entity classes, 1-2 signal classes, '
        "and 1-2 source classes. Use concise CamelCase names."
    )


def _call_seed_model(category: str) -> tuple[str, Usage]:
    """The seam. Returns (raw model text, usage); monkeypatched in tests."""
    response = get_client().messages.create(
        model=SEEDING_MODEL,
        max_tokens=4000,
        thinking={"type": "disabled"},
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_prompt(category)}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    input_tokens = response.usage.input_tokens or 0
    output_tokens = response.usage.output_tokens or 0
    usage = Usage(
        model=SEEDING_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
    )
    return text, usage


def parse_seed_ontology(raw_json: str) -> list[SeedClass]:
    """Parse + validate a model's JSON into a list of seed classes."""
    data = json.loads(raw_json)
    if not isinstance(data, dict):
        raise ValueError("seed JSON must be a top-level object")
    classes: list[SeedClass] = []
    for item in data.get("classes", []):
        name = item.get("name")
        kind = item.get("kind")
        if not name or kind not in ("entity", "signal", "source"):
            raise ValueError(f"invalid seed class: {item!r}")
        classes.append(SeedClass(name=name, kind=kind))
    return classes


def seed_ontology(category: str) -> SeedOntology:
    """Seed a sub-ontology for an unfamiliar category via the premium model."""
    text, usage = _call_seed_model(category)
    logger.info(
        "seeding model call: model=%s input_tokens=%d output_tokens=%d total_tokens=%d",
        usage.model,
        usage.input_tokens,
        usage.output_tokens,
        usage.total_tokens,
    )
    return SeedOntology(category=category, classes=parse_seed_ontology(text))


def _category_namespace(category: str) -> Namespace:
    return Namespace(f"https://cultural-signal-graph.dev/ontology/{category.lower()}#")


def build_sub_ontology(category: str, seed: SeedOntology) -> Graph:
    """Build the seeded sub-ontology as RDF (each class subclasses the upper schema)."""
    ns = _category_namespace(category)
    parent = {"entity": CSG.Entity, "signal": CSG.Signal, "source": CSG.Source}
    graph = Graph()
    graph.bind(category.lower(), ns)
    graph.bind("csg", CSG)
    for cls in seed.classes:
        graph.add((ns[cls.name], RDF.type, OWL.Class))
        graph.add((ns[cls.name], RDFS.subClassOf, parent[cls.kind]))
        graph.add((ns[cls.name], RDFS.label, Literal(cls.name)))
    return graph


def validate_sub_ontology(sub_ontology: Graph) -> tuple[bool, str]:
    """SHACL-validate the seeded sub-ontology via a sample signal instance."""
    from pyshacl import validate

    ont = Graph()
    for name in _ONTOLOGY_FILES:
        ont.parse(ONT_DIR / name, format="turtle")
    ont += sub_ontology

    shapes = Graph()
    shapes.parse(ONT_DIR / "shapes.ttl", format="turtle")

    signal_cls = next(sub_ontology.subjects(RDFS.subClassOf, CSG.Signal), None)
    if signal_cls is None:
        return False, "seeded ontology has no signal subclass"

    data = Graph()
    data.parse(
        data=(
            "@prefix csg: <https://cultural-signal-graph.dev/ontology#> .\n"
            "@prefix ex: <https://cultural-signal-graph.dev/example#> .\n"
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
            f"ex:sample a <{signal_cls}> ;\n"
            "    csg:hasSource ex:src ;\n"
            '    csg:confidence "0.8"^^xsd:decimal ;\n'
            '    csg:timestamp "2026-01-01T00:00:00Z"^^xsd:dateTime ;\n'
            "    csg:hasProvenance ex:prov .\n"
            "ex:src a csg:Source .\n"
            "ex:prov a csg:Provenance ;\n"
            '    csg:sourceURI "https://example.com/fashion"^^xsd:anyURI .\n'
        ),
        format="turtle",
    )

    conforms, _graph, report = validate(
        data_graph=data, shacl_graph=shapes, ont_graph=ont, inference="rdfs"
    )
    return bool(conforms), str(report) if not conforms else ""
