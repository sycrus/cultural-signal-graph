# LangGraph for agent orchestration

We orchestrate the multi-agent pipeline with LangGraph rather than CrewAI, Google ADK 2.0, or Microsoft Agent Framework. The product is itself a graph, and the orchestration wants graph-shaped control flow with resumable, auditable state: LangGraph's checkpointing/persistence and first-class human-in-the-loop interrupts map directly onto the governance layer, which is the whole differentiator.

**Considered options:** CrewAI (rejected — role-based and lighter, but weak control over state and checkpoints, which the HITL gates need); Google ADK 2.0 (rejected — newer, more Google-opinionated); Microsoft Agent Framework (rejected — Python support less mature than its .NET/TS roots).
