"""The local web app server (issue #20) — FastAPI around the file-backed run store.

One command (`python -m cultural_signal_graph.server`) starts it and opens the
browser; there are no external services. Routes serve the stepper UI's JSON API and
the static shell; run state lives in the `runs/` directory via `RunStore`, never in
a database. Store errors map globally: unknown run -> 404, wrong lifecycle state ->
409 (KeyError/ValueError handlers below).

Sync route functions (not `async`) so the LangGraph runs execute on the threadpool.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .futures.store import ExplorationStore
from .pipeline import forecast_run_from_state
from .runstore import RunStore
from .viz import build_cyto_elements, render_html

_STATIC_DIR = Path(__file__).resolve().parent / "static"

# The exportable, versionable outputs of a run: the batch-path artifacts plus the
# discovery search trail. An allowlist, so run_id/name can't traverse out of runs/.
EXPORT_FILES = (
    "brief.md",
    "brief.json",
    "brief.pptx",
    "graph.ttl",
    "usage.json",
    "discovery.json",
)


class AskIn(BaseModel):
    category: str
    question: str
    window_start: str
    window_end: str
    market: str | None = None


class SourceIn(BaseModel):
    uri: str
    source_type: str
    credibility: float
    category: str
    text: str
    topics: list[str] = []


class SourcesIn(BaseModel):
    sources: list[SourceIn]


class SignoffIn(BaseModel):
    decisions: dict[str, bool]


class NoteIn(BaseModel):
    target_id: str
    target_kind: str = "node"
    text: str
    author: str = "strategist"


class ExplorationIn(BaseModel):
    goal: str
    anchor_ids: list[str]
    horizon: int = 10
    orders: int = 5
    author: str = "strategist"


class ProjectionEditIn(BaseModel):
    statement: str | None = None
    window: list[int] | None = None
    author: str = "strategist"


class ReferenceIn(BaseModel):
    url: str
    excerpt: str
    author: str = "strategist"


class NewReferenceIn(BaseModel):
    url: str
    excerpt: str


class HumanProjectionIn(BaseModel):
    kind: str
    statement: str
    window: list[int]
    parent_id: str | None = None
    reference: NewReferenceIn | None = None
    reference_id: str | None = None
    author: str = "strategist"


class ImportIn(BaseModel):
    log: str
    author: str = "strategist"


class TagIn(BaseModel):
    value: str
    extras: dict = {}
    author: str = "strategist"


class ForkIn(BaseModel):
    hint: str | None = None
    author: str = "strategist"


class AuthorIn(BaseModel):
    author: str = "strategist"


def create_app(
    store: RunStore | None = None,
    futures: ExplorationStore | None = None,
    fixture_delay: float = 0.4,
) -> FastAPI:
    store = store or RunStore()
    futures = futures or ExplorationStore(store.root, mode=store.mode)
    app = FastAPI(title="Cultural Signal Graph")
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.exception_handler(KeyError)
    def unknown_run(request: Request, exc: KeyError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc.args[0] if exc.args else exc)})

    @app.exception_handler(ValueError)
    def wrong_state(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")

    @app.get("/api/runs")
    def list_runs() -> list[dict]:
        return store.list()

    @app.post("/api/runs", status_code=201)
    def create_run(ask: AskIn) -> dict:
        return store.create(
            category=ask.category,
            question=ask.question,
            window_start=ask.window_start,
            window_end=ask.window_end,
            market=ask.market,
        )

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        return store.snapshot(run_id)

    @app.put("/api/runs/{run_id}/sources")
    def edit_sources(run_id: str, body: SourcesIn) -> dict:
        return store.edit_sources(run_id, [s.model_dump() for s in body.sources])

    @app.post("/api/runs/{run_id}/sources/reset")
    def reset_sources(run_id: str) -> dict:
        return store.reset_sources(run_id)

    @app.post("/api/runs/{run_id}/start")
    def start_run(run_id: str) -> dict:
        return store.start(run_id)

    @app.post("/api/runs/{run_id}/signoff")
    def signoff(run_id: str, body: SignoffIn) -> dict:
        return store.signoff(run_id, body.decisions)

    @app.post("/api/runs/{run_id}/signoff/undo")
    def undo_signoff(run_id: str) -> dict:
        return store.undo_signoff(run_id)

    @app.get("/api/runs/{run_id}/metrics")
    def run_metrics(run_id: str) -> dict:
        return store.metrics(run_id)

    @app.get("/api/runs/{run_id}/notes")
    def list_notes(run_id: str) -> list[dict]:
        return store.notes(run_id)

    @app.post("/api/runs/{run_id}/notes", status_code=201)
    def add_note(run_id: str, note: NoteIn) -> dict:
        return store.add_note(
            run_id,
            target_id=note.target_id,
            text=note.text,
            author=note.author,
            target_kind=note.target_kind,
        )

    @app.get("/api/runs/{run_id}/exports/{name}")
    def export(run_id: str, name: str) -> FileResponse:
        if name not in EXPORT_FILES:
            raise HTTPException(status_code=404, detail=f"unknown export: {name}")
        path = store.artifact_path(run_id, name)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="run has no exports yet")
        return FileResponse(path, filename=name)

    # --- futures mode (PRD-futures.md) ----------------------------------------

    @app.get("/futures")
    def futures_page() -> FileResponse:
        return FileResponse(_STATIC_DIR / "futures.html")

    @app.get("/api/runs/{run_id}/futures/anchors")
    def futures_anchors(run_id: str) -> list[dict]:
        return futures.anchors(run_id)

    @app.get("/api/runs/{run_id}/explorations")
    def list_explorations(run_id: str) -> list[dict]:
        return futures.list(run_id)

    @app.post("/api/runs/{run_id}/explorations", status_code=201)
    def create_exploration(run_id: str, body: ExplorationIn) -> dict:
        return futures.create(
            run_id,
            goal=body.goal,
            anchor_ids=body.anchor_ids,
            horizon=body.horizon,
            orders=body.orders,
            author=body.author,
        )

    @app.get("/api/runs/{run_id}/explorations/{exp_id}")
    def get_exploration(run_id: str, exp_id: str) -> dict:
        return futures.snapshot(run_id, exp_id)

    @app.get("/api/runs/{run_id}/explorations/{exp_id}/ops/{seq}")
    def get_exploration_op(run_id: str, exp_id: str, seq: int) -> dict:
        return futures.op(run_id, exp_id, seq)

    @app.post("/api/runs/{run_id}/explorations/{exp_id}/generate")
    def generate_exploration(run_id: str, exp_id: str) -> dict:
        return futures.generate(run_id, exp_id)

    @app.post("/api/runs/{run_id}/explorations/{exp_id}/generate/stream")
    def stream_generation(run_id: str, exp_id: str) -> StreamingResponse:
        """Live fill: one Server-Sent Event per generated order, then `done`. A
        dropped connection ends generation after the current order; the client
        re-syncs from the log (each order is appended exactly once)."""
        futures.snapshot(run_id, exp_id)  # 404 before the stream opens
        if futures.is_generating(exp_id):
            raise ValueError(f"exploration {exp_id} is already generating")

        def events():
            try:
                for snap in futures.generate_iter(run_id, exp_id):
                    yield _sse("order", snap)
                    if futures.mode == "fixture" and fixture_delay:
                        time.sleep(fixture_delay)  # recorded output is instant; pace the fill
                yield _sse("done", futures.snapshot(run_id, exp_id))
            except Exception as exc:  # surfaced to the client; completed orders are kept
                yield _sse("error", {"detail": str(exc)})

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.patch("/api/runs/{run_id}/explorations/{exp_id}/projections/{pid}")
    def edit_projection(run_id: str, exp_id: str, pid: str, body: ProjectionEditIn) -> dict:
        return futures.edit(run_id, exp_id, pid, statement=body.statement, window=body.window, author=body.author)

    @app.delete("/api/runs/{run_id}/explorations/{exp_id}/projections/{pid}")
    def delete_projection(run_id: str, exp_id: str, pid: str, author: str = "strategist") -> dict:
        return futures.delete(run_id, exp_id, pid, author=author)

    @app.post("/api/runs/{run_id}/explorations/{exp_id}/projections/{pid}/regenerate")
    def regenerate_downstream(run_id: str, exp_id: str, pid: str, body: AuthorIn | None = None) -> dict:
        return futures.regenerate(run_id, exp_id, pid, author=(body.author if body else "strategist"))

    @app.post("/api/runs/{run_id}/explorations/{exp_id}/projections/{pid}/fork")
    def fork_projection(run_id: str, exp_id: str, pid: str, body: ForkIn) -> dict:
        return futures.fork(run_id, exp_id, pid, hint=body.hint, author=body.author)

    @app.post("/api/runs/{run_id}/explorations/{exp_id}/references")
    def add_reference(run_id: str, exp_id: str, body: ReferenceIn) -> dict:
        return futures.add_reference(run_id, exp_id, url=body.url, excerpt=body.excerpt, author=body.author)

    @app.post("/api/runs/{run_id}/explorations/{exp_id}/projections")
    def add_projection(run_id: str, exp_id: str, body: HumanProjectionIn) -> dict:
        return futures.add_projection(
            run_id,
            exp_id,
            kind=body.kind,
            statement=body.statement,
            window=body.window,
            parent_id=body.parent_id,
            reference=body.reference.model_dump() if body.reference else None,
            reference_id=body.reference_id,
            author=body.author,
        )

    @app.post("/api/runs/{run_id}/explorations/{exp_id}/lenses/{lens}/classify")
    def classify_lens(run_id: str, exp_id: str, lens: str) -> dict:
        return futures.classify(run_id, exp_id, lens)

    @app.put("/api/runs/{run_id}/explorations/{exp_id}/projections/{pid}/tags/{lens}")
    def set_lens_tag(run_id: str, exp_id: str, pid: str, lens: str, body: TagIn) -> dict:
        tag = {"value": body.value, **body.extras}
        return futures.set_tag(run_id, exp_id, pid, lens, tag, author=body.author)

    @app.get("/api/runs/{run_id}/explorations/{exp_id}/exports/{name}")
    def export_exploration(run_id: str, exp_id: str, name: str) -> Response:
        media = {"json": "application/json", "md": "text/markdown", "jsonl": "application/x-ndjson", "trig": "application/trig"}
        body = futures.export(run_id, exp_id, name)
        return Response(
            body,
            media_type=media[name.rsplit(".", 1)[-1]] + "; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{exp_id}-{name}"'},
        )

    @app.post("/api/runs/{run_id}/explorations/import", status_code=201)
    def import_exploration(run_id: str, body: ImportIn) -> dict:
        return futures.import_log(run_id, body.log, author=body.author)

    @app.get("/api/runs/{run_id}/futures.trig")
    def export_futures_trig(run_id: str) -> Response:
        """The run's RDF: evidence as the default graph, each exploration named."""
        graph_path = store.artifact_path(run_id, "graph.ttl")
        evidence = None
        if graph_path.is_file():
            from rdflib import Graph

            evidence = Graph().parse(graph_path, format="turtle")
        return Response(
            futures.futures_trig(run_id, evidence),
            media_type="application/trig; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{run_id}-futures.trig"'},
        )

    @app.post("/api/runs/{run_id}/explorations/{exp_id}/undo")
    def undo_exploration(run_id: str, exp_id: str) -> dict:
        return futures.undo(run_id, exp_id)

    @app.post("/api/runs/{run_id}/explorations/{exp_id}/redo")
    def redo_exploration(run_id: str, exp_id: str) -> dict:
        return futures.redo(run_id, exp_id)

    @app.post("/api/runs/{run_id}/explorations/{exp_id}/stop")
    def stop_generation(run_id: str, exp_id: str) -> dict:
        return futures.stop(run_id, exp_id)

    @app.get("/runs/{run_id}/graph.html", response_class=HTMLResponse)
    def graph_html(run_id: str, futures_layer: bool = False) -> HTMLResponse:
        """The graph explorer, served for embedding in the Graph tab. Rebuilt from
        the finalized state so it always matches the run's audit artifacts."""
        state_path = store.artifact_path(run_id, "state-final.json")
        if not state_path.is_file():
            raise HTTPException(status_code=404, detail="run has no graph yet")
        elements = build_cyto_elements(
            forecast_run_from_state(json.loads(state_path.read_text(encoding="utf-8")))
        )
        if futures_layer:  # the toggle: projections beside the evidence they grow from
            layer = futures.graph_layer(run_id)
            ids = {n["data"]["id"] for n in elements["nodes"]} | {n["data"]["id"] for n in layer["nodes"]}
            elements = {
                "nodes": elements["nodes"] + layer["nodes"],
                "edges": elements["edges"] + [e for e in layer["edges"] if e["data"]["source"] in ids and e["data"]["target"] in ids],
            }
        usage_path = store.artifact_path(run_id, "usage.json")
        usage = json.loads(usage_path.read_text(encoding="utf-8")) if usage_path.is_file() else None
        return HTMLResponse(
            render_html(elements, usage, notes_url=f"/api/runs/{run_id}/notes")
        )

    return app


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def main() -> None:
    import sys
    import threading
    import webbrowser

    import uvicorn

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    url = f"http://127.0.0.1:{port}/"
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
