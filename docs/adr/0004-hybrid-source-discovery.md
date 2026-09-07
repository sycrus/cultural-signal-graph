# Context-dependent source discovery, known-index-first

Sources are selected and pulled per ask, not drawn from a hardcoded list. We use a known source index first and live web search only to backfill on low-confidence/misses, mirroring the ontology-retrieval method (ADR-0005). This keeps source selection context-dependent while bounding token cost — live search fires only when the index cannot cover the ask. v1 ships the known-index half; the live-backfill mechanism is architected but stubbed.

**Considered options:** a hardcoded source catalog (rejected — the operator should not have to know which sources exist); live web search for every ask (rejected — token-expensive and unnecessary when the index covers the domain).
