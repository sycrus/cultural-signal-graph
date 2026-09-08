"""Source discovery — known index + context-dependent selection + live backfill (#4, #10).

Given an ask (category + question + window), select the contextually relevant
sources from a known index. When the index has no coverage for the ask's category,
backfill from the live web (Wikipedia search — free, keyless) with a bounded result
cap (ADR-0004; enabled in v2 by #10).
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

from .models import CSG_NS, GAMING_NS, TECH_NS, Ask, SourceDoc

# Bound the selection so a category with many sources returns a focused subset
# ("not all"), while a known category always yields at least one ("not none").
MAX_SOURCES = 3

# Live backfill: bounded Wikipedia results per run (the cost cap — free API, capped requests).
MAX_WEB_BACKFILL = 5
_WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
_WEB_SOURCE_CREDIBILITY = 0.6

SOURCE_INDEX: list[SourceDoc] = [
    # Tech
    SourceDoc(
        uri="https://example.com/release-notes/ai-wearables",
        source_type=TECH_NS + "ReleaseNote",
        credibility=0.9,
        category="tech",
        text="AI wearables now ship with on-device models, no phone required.",
        topics=("ai", "wearables", "hardware"),
    ),
    SourceDoc(
        uri="https://example.com/commerce/search-ai-wearables",
        source_type=TECH_NS + "SearchIndex",
        credibility=0.8,
        category="tech",
        text="Searches for AI wearables up 3x this quarter.",
        topics=("ai", "wearables", "commerce"),
    ),
    SourceDoc(
        uri="https://example.com/social/ai-wearables-fad",
        source_type=TECH_NS + "SocialPost",
        credibility=0.2,
        category="tech",
        text="AI wearables are a passing fad — no one wants another gadget.",
        topics=("ai", "wearables", "social"),
    ),
    SourceDoc(
        uri="https://example.com/release-notes/cloud-infra",
        source_type=TECH_NS + "ReleaseNote",
        credibility=0.85,
        category="tech",
        text="Managed cloud infrastructure adds a new region and lower egress.",
        topics=("cloud", "infrastructure"),
    ),
    SourceDoc(
        uri="https://example.com/commerce/edge-compute",
        source_type=TECH_NS + "SearchIndex",
        credibility=0.7,
        category="tech",
        text="Edge compute interest rises as latency budgets shrink.",
        topics=("edge", "compute"),
    ),
    # Gaming
    SourceDoc(
        uri="https://example.com/forum/ai-headset-hype",
        source_type=GAMING_NS + "ForumPost",
        credibility=0.5,
        category="gaming",
        text="AI headset chatter surging across gaming communities.",
        topics=("headset", "peripheral"),
    ),
    SourceDoc(
        uri="https://example.com/forum/cloud-gaming",
        source_type=GAMING_NS + "ForumPost",
        credibility=0.75,
        category="gaming",
        text="Cloud gaming latency improves with the new streaming stack.",
        topics=("cloud", "streaming"),
    ),
    SourceDoc(
        uri="https://example.com/forum/esports-viewership",
        source_type=GAMING_NS + "ForumPost",
        credibility=0.65,
        category="gaming",
        text="Esports viewership sets a new record this season.",
        topics=("esports", "viewership"),
    ),
    SourceDoc(
        uri="https://example.com/forum/controller-ergonomics",
        source_type=GAMING_NS + "ForumPost",
        credibility=0.6,
        category="gaming",
        text="Long threads on controller ergonomics and hand strain.",
        topics=("controller", "peripheral"),
    ),
]


def _tokenize(question: str) -> set[str]:
    return {
        word.strip(".,?!;:'\"()").lower()
        for word in question.split()
        if word.strip(".,?!;:'\"()")
    }


def discover_sources(ask: Ask, index: list[SourceDoc] = SOURCE_INDEX) -> list[SourceDoc]:
    """Select the sources relevant to the ask (category, then topic + credibility);
    backfill from the web when the index has no coverage for the category."""
    candidates = [source for source in index if source.category == ask.category]
    if not candidates:
        return _web_backfill(ask)[:MAX_SOURCES]
    tokens = _tokenize(ask.question)

    def rank(source: SourceDoc) -> tuple[int, float]:
        return (len(set(source.topics) & tokens), source.credibility)

    ranked = sorted(candidates, key=rank, reverse=True)
    return ranked[:MAX_SOURCES]


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _fetch_search_results(query: str, limit: int) -> list[dict]:
    """Search the web (Wikipedia) for a query. Returns [{title, url, snippet}]. The seam."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": str(limit),
    }
    url = _WIKIPEDIA_API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "cultural-signal-graph/0.1"})
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    results = payload.get("query", {}).get("search", [])
    return [
        {
            "title": r["title"],
            "url": "https://en.wikipedia.org/wiki/"
            + urllib.parse.quote(r["title"].replace(" ", "_")),
            "snippet": _strip_html(r.get("snippet", "")),
        }
        for r in results
    ]


def _web_backfill(ask: Ask, limit: int = MAX_WEB_BACKFILL) -> list[SourceDoc]:
    """Backfill relevant sources from the live web when the known index has none."""
    query = ask.question if not ask.market else f"{ask.question} {ask.market}"
    results = _fetch_search_results(query, limit)
    topics = tuple(sorted(_tokenize(ask.question)))
    return [
        SourceDoc(
            uri=r["url"],
            source_type=CSG_NS + "Source",
            credibility=_WEB_SOURCE_CREDIBILITY,
            category=ask.category,
            text=r["snippet"],
            topics=topics,
        )
        for r in results[:limit]
    ]
