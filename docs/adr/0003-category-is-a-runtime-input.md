# Category is a runtime input, not a constant

The domain a forecast reasons over is a user-supplied runtime input, not a hardcoded value. Tech is only the v1 fixture for proving the reasoning layer. If category were a constant, the "user can forecast any category" promise would be false and every new domain would need a code change; making it an input means sub-ontologies must auto-seed from grounding sources, which we accept. The tech sub-ontology is hand-authored as the proof category; unfamiliar categories auto-seed on first touch.
