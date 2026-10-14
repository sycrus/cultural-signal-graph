"""Source discovery — model-guided web search + known index (issues #4, #10, #28).

Given an ask (category + question + window + market), select the contextually
relevant sources. The web search is *model-guided*: one cheap-model call turns the
ask into 2-3 search queries (far better than token-matching the raw question), and
the results are pooled and deduplicated. Every category gets a bounded web top-up —
the known index contributes high-credibility sources when it has coverage, but
discovery no longer depends on it.

Discovery is itself auditable: `discover_with_trace` returns the queries used, the
raw results examined, and what was selected (index vs web), for the run's
`discovery.json`. The cheap-model call is a thin seam (`_call_query_model`) so tests
inject queries directly; when generation fails (no key, API hiccup) discovery falls
back to the question-derived query and keeps going.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request

from .config import brave_api_key
from .extraction import EXTRACTION_MODEL
from .llm import call_model, extract_json
from .models import CSG_NS, GAMING_NS, TECH_NS, Ask, SourceDoc, Usage
from .tracing import get_tracer, model_span, record_usage

logger = logging.getLogger(__name__)

# Bound the selection so a category with many sources returns a focused subset
# ("not all"), while a known category always yields at least one ("not none").
MAX_SOURCES = 3

# Live web search: bounded results per query (the cost cap — free API, capped
# requests), a bounded take when augmenting an indexed category, and a bounded
# number of generated queries.
MAX_WEB_BACKFILL = 5
MAX_WEB_SOURCES = 3
MAX_QUERIES = 3
_WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
_BRAVE_API = "https://api.search.brave.com/res/v1/web/search"
_WEB_SOURCE_CREDIBILITY = 0.6

QUERY_MODEL = EXTRACTION_MODEL  # the cheap tier — a handful of queries, not prose

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


def _rank(ask: Ask):
    """Rank index candidates by ask-topic overlap, then credibility."""

    def rank(source: SourceDoc) -> tuple[int, float]:
        return (len(set(source.topics) & _tokenize(ask.question)), source.credibility)

    return rank


# --- model-guided queries (issue #28) ----------------------------------------


def _fallback_queries(ask: Ask) -> list[str]:
    """The deterministic query when generation fails: the ask itself."""
    return [ask.question if not ask.market else f"{ask.question} {ask.market}"]


def _parse_queries(raw: str) -> list[str]:
    """Parse + validate a model's JSON response into 2-3 search queries."""
    data = json.loads(extract_json(raw))
    if not isinstance(data, list):
        raise ValueError("query JSON must be a top-level array")
    queries: list[str] = []
    for q in data:
        if isinstance(q, str) and q.strip() and q.strip() not in queries:
            queries.append(q.strip())
    if not queries:
        raise ValueError("no usable queries in the model response")
    return queries[:MAX_QUERIES]


def _build_prompt(ask: Ask) -> str:
    lines = [
        "Write web search queries to find sources for a trend forecast: recent news,",
        "industry coverage, and cultural chatter — not encyclopedia definitions.",
        "",
        f"Category: {ask.category}",
        f"Question: {ask.question}",
        f"Window: {ask.window.start} to {ask.window.end}",
    ]
    if ask.market:
        lines.append(f"Market: {ask.market}")
    lines += ["", 'Return a JSON array like ["query one", "query two"].']
    return "\n".join(lines)


def _call_query_model(ask: Ask) -> tuple[str, Usage]:
    """The seam. Returns (raw model text, usage); monkeypatched in tests."""
    system_prompt = (
        "You write web search queries for a trend-forecast source search. "
        "Return a single JSON array of 2-3 short query strings only — no prose, "
        "no markdown fences."
    )
    return call_model(QUERY_MODEL, system_prompt, _build_prompt(ask), max_tokens=1000)


def _queries_with_source(ask: Ask, given: list[str] | None) -> tuple[list[str], str]:
    """The queries to search with, and where they came from (the trace label)."""
    if given is not None:
        return list(given), "given"
    try:
        with get_tracer().start_as_current_span("discover_queries") as span:
            text, usage = _call_query_model(ask)
            record_usage(span, usage)
        return _parse_queries(text), "model"
    except Exception as exc:
        logger.warning("query generation failed (%s); falling back to the ask", exc)
        return _fallback_queries(ask), "fallback"


def search_queries(ask: Ask) -> list[str]:
    """2-3 search queries for an ask; falls back to the ask when generation fails."""
    return _queries_with_source(ask, None)[0]


# --- web search ---------------------------------------------------------------


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _fetch_wikipedia_results(query: str, limit: int) -> list[dict]:
    """Search Wikipedia full-text for a query. The no-key fallback: encyclopedic
    AND-match on keywords — usable coverage, weak as sole evidence for news."""
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
            "backend": "wikipedia",
        }
        for r in results
    ]


def _fetch_brave_results(query: str, limit: int) -> list[dict]:
    """Search Brave's independent index for a query; the same response usually
    carries a news bucket, merged in (deduped) — the evidence class grounding
    asks for. Returns [{title, url, snippet, backend}] with backend="brave"."""
    request = urllib.request.Request(
        _BRAVE_API + "?" + urllib.parse.urlencode({"q": query, "count": str(limit)}),
        headers={"Accept": "application/json", "X-Subscription-Token": brave_api_key()},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    buckets = (payload.get("web", {}) or {}).get("results") or []
    buckets += (payload.get("news", {}) or {}).get("results") or []
    records, seen = [], set()
    for r in buckets:
        record = {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": _strip_html(r.get("description", "")),
            "backend": "brave",
        }
        if record["url"] and record["url"] not in seen:
            seen.add(record["url"])
            records.append(record)
    return records


def _fetch_search_results(query: str, limit: int) -> list[dict]:
    """Search the web for a query. Returns [{title, url, snippet, backend}]. The seam:
    Brave when BRAVE_API_KEY is set, else Wikipedia full-text."""
    if brave_api_key():
        return _fetch_brave_results(query, limit)
    return _fetch_wikipedia_results(query, limit)


def _search_records(
    queries: list[str], limit: int = MAX_WEB_BACKFILL, errors: list[dict] | None = None
) -> list[dict]:
    """Run every query and pool the results, deduplicated by URL, each attributed
    to the query that found it. A failing query is skipped, not fatal; when `errors`
    is a list, each failure is appended as {query, error} so the caller can show
    why a round came back empty."""
    records: list[dict] = []
    seen: set[str] = set()
    for query in queries:
        try:
            results = _fetch_search_results(query, limit)
        except Exception as exc:
            logger.warning("web search failed for %r: %s", query, exc)
            if errors is not None:
                errors.append({"query": query, "error": str(exc)})
            continue
        for record in results:
            if record["url"] in seen:
                continue
            seen.add(record["url"])
            records.append({**record, "query": query})
    return records


def _record_to_source(record: dict, ask: Ask) -> SourceDoc:
    return SourceDoc(
        uri=record["url"],
        source_type=CSG_NS + "Source",
        credibility=_WEB_SOURCE_CREDIBILITY,
        category=ask.category,
        text=record["snippet"],
        topics=tuple(sorted(_tokenize(ask.question))),
    )


def _web_backfill(
    ask: Ask, queries: list[str] | None = None, limit: int = MAX_WEB_BACKFILL
) -> list[SourceDoc]:
    """Backfill relevant sources from the live web. `queries=None` searches for the
    ask itself (the deterministic, offline-testable path)."""
    used = queries if queries is not None else _fallback_queries(ask)
    records = _search_records(used, limit)
    return [_record_to_source(record, ask) for record in records[:limit]]


# --- selection ----------------------------------------------------------------


def discover_sources(ask: Ask, index: list[SourceDoc] = SOURCE_INDEX) -> list[SourceDoc]:
    """Select the sources relevant to the ask from a known index (ask-dependent
    ranking); backfill from the web when the index has no coverage for the
    category. The offline-compatible path — see `discover_with_trace` for the
    model-guided, audited variant the run store uses."""
    candidates = [source for source in index if source.category == ask.category]
    if not candidates:
        return _web_backfill(ask)[:MAX_SOURCES]
    return sorted(candidates, key=_rank(ask), reverse=True)[:MAX_SOURCES]


def discover_with_trace(
    ask: Ask, index: list[SourceDoc] = SOURCE_INDEX, queries: list[str] | None = None
) -> dict:
    """Discover the sources for an ask with the full search trail attached.

    Returns {"sources", "queries", "query_source", "results", "selected", "mode"}:
    the selected corpus (index selection plus a bounded web top-up, or web-only for
    unindexed categories), the queries actually searched, every unique result
    examined, and per-source origin — the payload for `discovery.json`.
    """
    candidates = [source for source in index if source.category == ask.category]
    index_selected = sorted(candidates, key=_rank(ask), reverse=True)[:MAX_SOURCES]

    used, query_source = _queries_with_source(ask, queries)
    records = _search_records(used)

    index_uris = {source.uri for source in index_selected}
    web_sources: list[SourceDoc] = []
    for record in records:
        if record["url"] in index_uris:
            continue
        web_sources.append(_record_to_source(record, ask))
        if len(web_sources) >= MAX_WEB_SOURCES:
            break

    sources = index_selected + web_sources if candidates else web_sources
    mode = "web" if not candidates else ("index+web" if web_sources else "index")
    selected = [
        {"uri": source.uri, "credibility": source.credibility, "origin": "web" if source not in index_selected else "index"}
        for source in sources
    ]
    return {
        "sources": sources,
        "queries": used,
        "query_source": query_source,
        "results": records,
        "selected": selected,
        "mode": mode,
    }
