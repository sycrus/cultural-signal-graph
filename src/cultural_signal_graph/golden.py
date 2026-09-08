"""The golden set — held-out corpora with known-expected outcomes (issue #8).

The seed corpus already embodies both PRD demo scenarios, so it anchors three named
eval cases: the full `SEED_CASE`, plus the two demo cases (#9) that gate flag recall
and gate correctness respectively. Expected outcomes are hand-authored here, independent
of the pipeline, so a regression in the code drops the score rather than the golden.
"""

from __future__ import annotations

from .eval import EvalCase
from .fixtures import SEED_CORPUS

_EXPECTED_ENTITIES = frozenset({"ai_wearables", "ai_headset"})
_EXPECTED_SIGNALS = frozenset(
    {"sig-release-note", "sig-search-spike", "sig-viral-fad", "sig-gaming-chatter"}
)
_EXPECTED_FLAGS = frozenset({"sig-viral-fad"})
_EXPECTED_EDGES = frozenset({"edge-ai-headset-wearables"})
_GATED_EDGES = frozenset({"edge-ai-headset-wearables"})


def _seed_case(name: str) -> EvalCase:
    return EvalCase(
        name=name,
        corpus=SEED_CORPUS,
        category="tech",
        expected_entity_ids=_EXPECTED_ENTITIES,
        expected_signal_ids=_EXPECTED_SIGNALS,
        expected_flag_ids=_EXPECTED_FLAGS,
        expected_edge_ids=_EXPECTED_EDGES,
        gated_edge_ids=_GATED_EDGES,
    )


SEED_CASE = _seed_case("seed")
CATCH_CASE = _seed_case("catch")
CROSS_DOMAIN_CASE = _seed_case("cross-domain-overconfidence")

EVAL_CASES = [CATCH_CASE, CROSS_DOMAIN_CASE]
