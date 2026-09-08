"""Issue #11 acceptance tests for the interactive graph explorer."""

from cultural_signal_graph.fixtures import (
    ALIGNED_EDGES,
    DRAFTED_REASONING,
    EXTRACTED,
    SEED_CORPUS,
)
from cultural_signal_graph.pipeline import run
from cultural_signal_graph.viz import build_cyto_elements, render_html


def _forecast():
    return run(
        SEED_CORPUS,
        category="tech",
        extract_fn=lambda _: EXTRACTED,
        align_fn=lambda _: ALIGNED_EDGES,
        draft_fn=lambda extraction, category: DRAFTED_REASONING,
    )


def test_build_cyto_elements_has_nodes_and_edges():
    elements = build_cyto_elements(_forecast())
    kinds = {n["data"]["kind"] for n in elements["nodes"]}
    assert {"entity", "signal", "source"} <= kinds

    edge_kinds = {e["data"]["kind"] for e in elements["edges"]}
    assert {"about", "hasSource", "equivalence"} <= edge_kinds


def test_conflict_signal_is_flagged_and_gated_edge_is_distinct():
    elements = build_cyto_elements(_forecast())
    flagged = [n for n in elements["nodes"] if n["data"].get("flagged") == "true"]
    assert flagged, "expected the conflict signal to be visually distinct"

    equivalence = [e for e in elements["edges"] if e["data"]["kind"] == "equivalence"]
    assert equivalence
    assert equivalence[0]["data"]["status"] != "real"  # gated -> dashed in the UI


def test_render_html_embeds_the_graph_data():
    elements = build_cyto_elements(_forecast())
    html = render_html(elements)
    assert "cytoscape" in html
    assert "ai_wearables" in html  # entity id embedded in the data blob
    assert '"kind": "signal"' in html


def test_graph_html_is_offline_with_controls():
    html = render_html(build_cyto_elements(_forecast()))
    assert "unpkg.com" not in html  # Cytoscape is inlined, no CDN
    assert 'id="search"' in html  # search box
    assert "btn-cose" in html  # layout controls
