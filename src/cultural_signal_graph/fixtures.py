"""The seed corpus and its recorded fixtures (issues #2, #3).

`SEED_CORPUS` is the deterministic input with real source URLs. `EXTRACTED` /
`RECORDED_MODEL_OUTPUT` / `ALIGNED_EDGES` / `DRAFTED_REASONING` are the hand-authored
"golden" outputs the (stubbed) stages would return — used by tests so they never hit
the network. Together they encode both PRD demo scenarios in one run:

- the "catch": a skeptical post *refutes* an AI-glasses trend that two corroborating
  sources *support*, so flag logic surfaces a conflict; and
- the "cross-domain overconfidence": gaming-community chatter about a headset is
  proposed as equivalent to the tech "AI wearables" entity at low confidence, so the
  gate holds it as "proposed", never "real".
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
        uri="https://www.business-standard.com/technology/tech-news/alibaba-unveils-quark-ai-glasses-with-dual-displays-and-swappable-batteries-125112800247_1.html",
        source_type=TECH_NS + "ReleaseNote",
        credibility=0.9,
        category="tech",
        text="Alibaba unveils Quark AI glasses powered by its Qwen AI models, with dual displays and swappable batteries.",
    ),
    SourceDoc(
        uri="https://finance.sina.cn/2025-06-12/detail-inezuxsa3682433.d.html",
        source_type=TECH_NS + "SearchIndex",
        credibility=0.8,
        category="tech",
        text="Smart glasses search and transaction volume surged, up 800% year over year.",
    ),
    SourceDoc(
        uri="https://www.techspot.com/news/110489-ai-devices-solutions-looking-problem-logitech-ceo.html",
        source_type=TECH_NS + "SocialPost",
        credibility=0.2,
        category="tech",
        text="Logitech's CEO calls AI devices 'solutions looking for a problem that does not exist.'",
    ),
    SourceDoc(
        uri="https://www.teamblind.com/post/ai-powered-gaming-headsets-next-frontier-or-niche-gadget-ckncukcm",
        source_type=GAMING_NS + "ForumPost",
        credibility=0.5,
        category="gaming",
        text="Gamers debate whether AI-powered gaming headsets are the next frontier or a niche gadget.",
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
        text="Alibaba ships Quark AI glasses running Qwen models on-device",
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
        text="Smart glasses search volume up sharply year over year",
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
        text="AI devices are solutions looking for a problem",
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
        text="Gamers debate whether AI gaming headsets are the next frontier or a niche",
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
# (the golden extraction). entity_type uses CURIEs here, which parse_extraction expands.
RECORDED_MODEL_OUTPUT = """
{
  "entities": [
    {"id": "ai_wearables", "name": "AI wearables", "category": "tech", "entity_type": "tech:Product"},
    {"id": "ai_headset", "name": "AI headset", "category": "gaming", "entity_type": "gaming:Peripheral"}
  ],
  "signals": [
    {"id": "sig-release-note", "text": "Alibaba ships Quark AI glasses running Qwen models on-device", "about_entity_id": "ai_wearables", "source_uri": "https://www.business-standard.com/technology/tech-news/alibaba-unveils-quark-ai-glasses-with-dual-displays-and-swappable-batteries-125112800247_1.html", "confidence": 0.85, "timestamp": "2026-01-15T00:00:00Z", "valid_from": "2026-01-15T00:00:00Z", "valid_until": "2026-07-15T00:00:00Z", "polarity": "support"},
    {"id": "sig-search-spike", "text": "Smart glasses search volume up sharply year over year", "about_entity_id": "ai_wearables", "source_uri": "https://finance.sina.cn/2025-06-12/detail-inezuxsa3682433.d.html", "confidence": 0.8, "timestamp": "2026-02-01T00:00:00Z", "valid_from": "2026-02-01T00:00:00Z", "valid_until": "2026-08-01T00:00:00Z", "polarity": "support"},
    {"id": "sig-viral-fad", "text": "AI devices are solutions looking for a problem", "about_entity_id": "ai_wearables", "source_uri": "https://www.techspot.com/news/110489-ai-devices-solutions-looking-problem-logitech-ceo.html", "confidence": 0.55, "timestamp": "2026-02-10T00:00:00Z", "valid_from": "2026-02-10T00:00:00Z", "valid_until": "2026-03-10T00:00:00Z", "polarity": "refute"},
    {"id": "sig-gaming-chatter", "text": "Gamers debate whether AI gaming headsets are the next frontier or a niche", "about_entity_id": "ai_headset", "source_uri": "https://www.teamblind.com/post/ai-powered-gaming-headsets-next-frontier-or-niche-gadget-ckncukcm", "confidence": 0.6, "timestamp": "2026-02-05T00:00:00Z", "valid_from": "2026-02-05T00:00:00Z", "valid_until": "2026-04-05T00:00:00Z", "polarity": "support"}
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
        "A product announcement confirms on-device Qwen AI glasses shipping now; confidence 0.85."
    ),
    "sig-search-spike": (
        "A sharp rise in smart-glasses search volume corroborates demand; confidence 0.8."
    ),
}

RECORDED_DRAFT_OUTPUT = """
[
  {"signal_id": "sig-release-note", "reasoning": "A product announcement confirms on-device Qwen AI glasses shipping now; confidence 0.85."},
  {"signal_id": "sig-search-spike", "reasoning": "A sharp rise in smart-glasses search volume corroborates demand; confidence 0.8."}
]
"""
