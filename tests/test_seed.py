"""Issue #12 acceptance tests for sub-ontology auto-seeding."""

from cultural_signal_graph import seed as sd
from cultural_signal_graph.fixtures import RECORDED_SEED_OUTPUT, SEEDED_FASHION
from cultural_signal_graph.models import Entity, Extraction, SeedOntology, Signal, SourceDoc
from cultural_signal_graph.pipeline import run

FASHION_NS = "https://cultural-signal-graph.dev/ontology/fashion#"


def test_parse_seed_matches_golden():
    assert sd.parse_seed_ontology(RECORDED_SEED_OUTPUT) == SEEDED_FASHION


def test_seeded_ontology_is_shacl_valid():
    seed = SeedOntology(category="fashion", classes=SEEDED_FASHION)
    sub_ontology = sd.build_sub_ontology("fashion", seed)
    conforms, report = sd.validate_sub_ontology(sub_ontology)
    assert conforms, report


def test_forecast_runs_in_seeded_category():
    seed = SeedOntology(category="fashion", classes=SEEDED_FASHION)
    sub_ontology = sd.build_sub_ontology("fashion", seed)

    corpus = [
        SourceDoc(
            uri="https://example.com/fashion/trade-press",
            source_type=FASHION_NS + "TradePress",
            credibility=0.6,
            category="fashion",
            text="A fashion trade press piece on an emerging trend.",
        )
    ]
    extraction = Extraction(
        entities=[
            Entity(
                id="fashion_apparel",
                name="Apparel",
                category="fashion",
                entity_type=FASHION_NS + "Apparel",
            )
        ],
        signals=[
            Signal(
                id="s1",
                text="Apparel trend is emerging",
                about_entity_id="fashion_apparel",
                source_uri=corpus[0].uri,
                confidence=0.7,
                timestamp="2026-01-01T00:00:00Z",
                valid_from="2026-01-01T00:00:00Z",
                valid_until="2026-06-01T00:00:00Z",
                polarity="support",
            )
        ],
    )

    forecast = run(
        corpus,
        category="fashion",
        extract_fn=lambda _: extraction,
        align_fn=lambda _: [],
        draft_fn=lambda e, c: {},
        extra_ontology=sub_ontology,
    )
    assert forecast.brief.category == "fashion"
    assert forecast.brief.claims
    assert all(claim.sources for claim in forecast.brief.claims)
