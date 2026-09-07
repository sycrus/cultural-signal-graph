# RDFLib + files for the graph, not a graph database

The knowledge graph lives in RDFLib in memory and is persisted as Turtle/JSON-LD files on disk, rather than in Neo4j/Memgraph. The v1 graph is small enough that n-hop retrieval is instant in memory; "state to files" keeps the system solo-hostable with zero infrastructure; and SHACL validation via pyshacl needs the RDF toolchain anyway. A graph database is deferred until live query latency actually demands it.

**Considered options:** Neo4j/Memgraph (rejected for v1 — adds Docker infra and cost before the reasoning layer is proven).
