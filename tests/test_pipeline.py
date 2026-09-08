"""Issue #2 acceptance tests for the thin end-to-end slice."""

from pathlib import Path

import rdflib
from pyshacl import validate
from rdflib import Namespace

from cultural_signal_graph.fixtures import SEED_CORPUS
from cultural_signal_graph.pipeline import run

CSG = Namespace("https://cultural-signal-graph.dev/ontology#")
ONT_DIR = Path(__file__).resolve().parents[1] / "src" / "cultural_signal_graph" / "ontology"


def test_run_is_deterministic():
    first = run(SEED_CORPUS)
    second = run(SEED_CORPUS)
    assert first.brief.to_json() == second.brief.to_json()
    assert first.brief.to_markdown() == second.brief.to_markdown()
    assert set(first.graph) == set(second.graph)


def test_every_claim_has_source_confidence_temporal():
    brief = run(SEED_CORPUS).brief
    assert brief.claims, "expected at least one confident claim"
    for claim in brief.claims:
        assert len(claim.sources) >= 1
        assert isinstance(claim.confidence, float)
        assert 0.0 <= claim.confidence <= 1.0
        assert claim.temporal_validity.valid_from
        assert claim.temporal_validity.valid_until


def test_conflict_signal_is_flagged_not_claimed():
    brief = run(SEED_CORPUS).brief
    claim_text = " ".join(claim.statement for claim in brief.claims)
    assert "passing fad" not in claim_text
    conflict = [flag for flag in brief.flags if "passing fad" in flag.statement]
    assert conflict
    assert conflict[0].reason == "conflict"


def test_low_confidence_cross_domain_edge_is_gated():
    forecast = run(SEED_CORPUS)
    assert forecast.brief.gated_edges
    edge = forecast.brief.gated_edges[0]
    assert edge.status == "proposed"
    assert edge.confidence < 0.5
    # The gate held: no csg:equivalentTo triple was asserted in the graph.
    assert not list(forecast.graph.triples((None, CSG.equivalentTo, None)))


def test_built_graph_conforms_to_shacl():
    ont = rdflib.Graph()
    for name in ("upper.ttl", "tech.ttl", "gaming.ttl"):
        ont.parse(ONT_DIR / name, format="turtle")
    shapes = rdflib.Graph()
    shapes.parse(ONT_DIR / "shapes.ttl", format="turtle")

    forecast = run(SEED_CORPUS)
    conforms, _graph, report = validate(
        data_graph=forecast.graph, shacl_graph=shapes, ont_graph=ont, inference="rdfs"
    )
    assert conforms, report
