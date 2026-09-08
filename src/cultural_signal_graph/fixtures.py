"""The fixed seed corpus and the extraction fixture for the thin slice (issue #2).

`SEED_CORPUS` is the deterministic input. `EXTRACTED` is what the (stubbed)
extraction stage returns — hand-authored here, replaced by the cheap model in
issue #3. Together they encode both PRD demo scenarios in one run:

- the "catch": a viral-but-low-credibility post *refutes* a trend that two
  corroborating sources *support*, so flag logic surfaces a conflict; and
- the "cross-domain overconfidence": gaming-community chatter about a headset
  is proposed as equivalent to the tech "AI wearables" entity at low
  confidence, so the gate holds it as "proposed", never "real".
"""

from .models import (
    CSG_NS,
    EX_NS,
    GAMING_NS,
    TECH_NS,
    Entity,
    EquivalenceEdge,
    Extraction,
    Signal,
    SourceDoc,
)

SEED_CORPUS: list[SourceDoc] = [
    SourceDoc(
        uri="https://example.com/release-notes/ai-wearables",
        source_type=TECH_NS + "ReleaseNote",
        credibility=0.9,
        category="tech",
        text="AI wearables now ship with on-device models, no phone required.",
    ),
    SourceDoc(
        uri="https://example.com/commerce/search-ai-wearables",
        source_type=TECH_NS + "SearchIndex",
        credibility=0.8,
        category="tech",
        text="Searches for AI wearables up 3x this quarter.",
    ),
    SourceDoc(
        uri="https://example.com/social/ai-wearables-fad",
        source_type=TECH_NS + "SocialPost",
        credibility=0.2,
        category="tech",
        text="AI wearables are a passing fad — no one wants another gadget.",
    ),
    SourceDoc(
        uri="https://example.com/forum/ai-headset-hype",
        source_type=GAMING_NS + "ForumPost",
        credibility=0.5,
        category="gaming",
        text="AI headset chatter surging across gaming communities.",
    ),
]

_ENTITIES: list[Entity] = [
    Entity(
        id="ai_wearables",
        name="AI wearables",
        category="tech",
        entity_type=TECH_NS + "Product",
    ),
    Entity(
        id="ai_headset",
        name="AI headset",
        category="gaming",
        entity_type=GAMING_NS + "Peripheral",
    ),
]

_SIGNALS: list[Signal] = [
    Signal(
        id="sig-release-note",
        text="AI wearables now ship with on-device models",
        about_entity_id="ai_wearables",
        source_uri=SEED_CORPUS[0].uri,
        confidence=0.85,
        timestamp="2026-01-15T00:00:00Z",
        valid_from="2026-01-15T00:00:00Z",
        valid_until="2026-07-15T00:00:00Z",
        polarity="support",
    ),
    Signal(
        id="sig-search-spike",
        text="Searches for AI wearables up 3x this quarter",
        about_entity_id="ai_wearables",
        source_uri=SEED_CORPUS[1].uri,
        confidence=0.8,
        timestamp="2026-02-01T00:00:00Z",
        valid_from="2026-02-01T00:00:00Z",
        valid_until="2026-08-01T00:00:00Z",
        polarity="support",
    ),
    Signal(
        id="sig-viral-fad",
        text="AI wearables are a passing fad",
        about_entity_id="ai_wearables",
        source_uri=SEED_CORPUS[2].uri,
        confidence=0.55,
        timestamp="2026-02-10T00:00:00Z",
        valid_from="2026-02-10T00:00:00Z",
        valid_until="2026-03-10T00:00:00Z",
        polarity="refute",
    ),
    Signal(
        id="sig-gaming-chatter",
        text="AI headset chatter surging in gaming communities",
        about_entity_id="ai_headset",
        source_uri=SEED_CORPUS[3].uri,
        confidence=0.6,
        timestamp="2026-02-05T00:00:00Z",
        valid_from="2026-02-05T00:00:00Z",
        valid_until="2026-04-05T00:00:00Z",
        polarity="support",
    ),
]

ALIGNED_EDGES: list[EquivalenceEdge] = [
    EquivalenceEdge(
        id="edge-ai-headset-wearables",
        left_entity_id="ai_headset",
        right_entity_id="ai_wearables",
        confidence=0.35,
    ),
]

EXTRACTED = Extraction(entities=_ENTITIES, signals=_SIGNALS)


# A recorded model response standing in for one real `deepseek-v4-flash` output.
# Used only by tests: `parse_extraction(RECORDED_MODEL_OUTPUT)` must equal `EXTRACTED`
# (the golden extraction), so extraction is tested against a fixture, not live output.
# entity_type uses CURIEs here, which parse_extraction expands to full ontology IRIs.
RECORDED_MODEL_OUTPUT = """
{
  "entities": [
    {"id": "ai_wearables", "name": "AI wearables", "category": "tech", "entity_type": "tech:Product"},
    {"id": "ai_headset", "name": "AI headset", "category": "gaming", "entity_type": "gaming:Peripheral"}
  ],
  "signals": [
    {"id": "sig-release-note", "text": "AI wearables now ship with on-device models", "about_entity_id": "ai_wearables", "source_uri": "https://example.com/release-notes/ai-wearables", "confidence": 0.85, "timestamp": "2026-01-15T00:00:00Z", "valid_from": "2026-01-15T00:00:00Z", "valid_until": "2026-07-15T00:00:00Z", "polarity": "support"},
    {"id": "sig-search-spike", "text": "Searches for AI wearables up 3x this quarter", "about_entity_id": "ai_wearables", "source_uri": "https://example.com/commerce/search-ai-wearables", "confidence": 0.8, "timestamp": "2026-02-01T00:00:00Z", "valid_from": "2026-02-01T00:00:00Z", "valid_until": "2026-08-01T00:00:00Z", "polarity": "support"},
    {"id": "sig-viral-fad", "text": "AI wearables are a passing fad", "about_entity_id": "ai_wearables", "source_uri": "https://example.com/social/ai-wearables-fad", "confidence": 0.55, "timestamp": "2026-02-10T00:00:00Z", "valid_from": "2026-02-10T00:00:00Z", "valid_until": "2026-03-10T00:00:00Z", "polarity": "refute"},
    {"id": "sig-gaming-chatter", "text": "AI headset chatter surging in gaming communities", "about_entity_id": "ai_headset", "source_uri": "https://example.com/forum/ai-headset-hype", "confidence": 0.6, "timestamp": "2026-02-05T00:00:00Z", "valid_from": "2026-02-05T00:00:00Z", "valid_until": "2026-04-05T00:00:00Z", "polarity": "support"}
  ]
}
"""

# A recorded alignment (deepseek-v4-pro) response: a JSON array of cross-domain edges.
# parse_alignment(RECORDED_ALIGNMENT_OUTPUT) must equal ALIGNED_EDGES (the golden edges).
RECORDED_ALIGNMENT_OUTPUT = """
[
  {"id": "edge-ai-headset-wearables", "left_entity_id": "ai_headset", "right_entity_id": "ai_wearables", "confidence": 0.35}
]
"""

# A recorded drafting (deepseek-v4-pro) response: reasoning per confident signal.
# parse_draft(RECORDED_DRAFT_OUTPUT) must equal DRAFTED_REASONING.
DRAFTED_REASONING = {
    "sig-release-note": (
        "Release note states on-device models ship now; confidence 0.85 through mid-2026."
    ),
    "sig-search-spike": (
        "3x search increase corroborates demand; confidence 0.8 through Aug 2026."
    ),
}

RECORDED_DRAFT_OUTPUT = """
[
  {"signal_id": "sig-release-note", "reasoning": "Release note states on-device models ship now; confidence 0.85 through mid-2026."},
  {"signal_id": "sig-search-spike", "reasoning": "3x search increase corroborates demand; confidence 0.8 through Aug 2026."}
]
"""
