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
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .pipeline import forecast_run_from_state
from .runstore import RunStore
from .viz import build_cyto_elements, render_html

_STATIC_DIR = Path(__file__).resolve().parent / "static"

# The exportable, versionable outputs of a finalized run (the same artifacts the
# batch path writes). An allowlist, so run_id/name can't traverse out of runs/.
EXPORT_FILES = ("brief.md", "brief.json", "brief.pptx", "graph.ttl", "usage.json")


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


def create_app(store: RunStore | None = None) -> FastAPI:
    store = store or RunStore()
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

    @app.get("/runs/{run_id}/graph.html", response_class=HTMLResponse)
    def graph_html(run_id: str) -> HTMLResponse:
        """The graph explorer, served for embedding in the Graph tab. Rebuilt from
        the finalized state so it always matches the run's audit artifacts."""
        state_path = store.artifact_path(run_id, "state-final.json")
        if not state_path.is_file():
            raise HTTPException(status_code=404, detail="run has no graph yet")
        elements = build_cyto_elements(
            forecast_run_from_state(json.loads(state_path.read_text(encoding="utf-8")))
        )
        usage_path = store.artifact_path(run_id, "usage.json")
        usage = json.loads(usage_path.read_text(encoding="utf-8")) if usage_path.is_file() else None
        return HTMLResponse(
            render_html(elements, usage, notes_url=f"/api/runs/{run_id}/notes")
        )

    return app


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
