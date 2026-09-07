# Hybrid ontology retrieval: embedding-first, LLM on miss

Ontology discovery uses embedding search first and recursive LLM navigation only on low-confidence misses, validated against SHACL constraints — never dumping full ontologies into context. Dumping the ontology would be a token cliff and would lose the record of what was considered; embedding-first bounds cost, and LLM-on-miss preserves recall for unfamiliar matches. Ontology/taxonomy embeddings are cached once, not computed per call.
