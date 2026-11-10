# Workshops are a second surface on the futures engine, not a fork

Futures mode was designed for a strategist working alone or in a small agency team: evidence first, the model generates, human-only ideas are greyed, and multi-user collaboration and client-facing output are non-goals (`PRD-futures.md`). Agencies also run **workshops**: with internal or external stakeholders, or across disciplines, to gather perspectives. There, participants' ideas are the primary material and the model's job is to **propose**: ideas mixed in with theirs, and especially new connections between them. That is a different primary user with different affordances, but it needs the same core: the operation log (author per op, undo/redo, replay), provenance, the projection DAG with forks and convergence, lenses, and Ground this.

So the repo keeps **one futures engine with two surfaces**:

- the **strategist surface** (today's Futures mode, `PRD-futures.md`), unchanged;
- the **workshop surface** (`PRD-workshop.md`): facilitator and participants, ideas from people, model output as proposals, multi-stage (inspire → envision → prototype).

Each surface has its own PRD and its own affordances and non-goals. Engine changes the workshop needs (participant authorship, a proposed state for model output and connections, unplaced ideas) are made in the engine so both surfaces can use them. The strategist surface keeps its defaults unless its PRD is changed, though the same capabilities serve small strategist teams too.

**Considered options:** forking the repo for a workshop product (rejected: the shared core would drift and every replay, lens or provenance fix would be made twice; a fork only pays off if workshops never touch forecast runs or move to a different owner); turning Futures mode itself into the workshop tool (rejected: it would overturn the strategist PRD's evidence-first stance and its non-goals for the user it was built for); a workshop tab inside the strategist surface (rejected: the differences are in the defaults, who writes and how model output arrives, not in one more view).

**Revisit if** workshops turn out never to start from a forecast run, or the workshop product gets a separate owner or release cycle.
