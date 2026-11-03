---
status: accepted — supersedes ADR-0004
---

# Search-first source discovery, with the index as a relevance-gated supplement

Every ask now runs a live web search; the known index no longer gates it. A cheap-model call turns the ask into 2-3 search queries, the results are pooled and deduplicated, and a bounded number (3) join the corpus. Index sources join only when they share a topic with the question, because a category match alone is not relevance: "origami in robots" was getting AI-wearables release notes simply because both were "tech". The search backend is one seam, `_fetch_search_results`: Brave (web + news) when `BRAVE_API_KEY` is set, Wikipedia full-text otherwise, so the app still works with no key. Futures' "Ground this" reuses the same seam rather than having its own search. Every run stores its search trail (queries, results examined, what was selected) as `discovery.json`, so discovery can be audited like any other stage.

ADR-0004's premise, index first with search only on a miss, didn't survive category becoming a runtime input (ADR-0003): no index can cover an arbitrary ask, and the index never grew past a demo set.

**Considered options:** index-first with search only on a miss (ADR-0004; rejected for the reasons above); searching the raw question instead of model-written queries (rejected because token matching finds poor results; kept as the fallback when the query model is unavailable); Wikipedia as the only backend (rejected: it returns encyclopedia definitions, not the news, regulation and forecast evidence that forecasting and grounding need); requiring a Brave key (rejected because it would break the no-key, offline-capable setup); a separate search stack for Ground this (rejected: two seams would drift).
