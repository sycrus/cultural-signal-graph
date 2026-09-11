"""The local web app server (issue #20) — FastAPI around the file-backed run store.

One command (`python -m cultural_signal_graph.server`) starts it and opens the
browser; there are no external services. Routes serve the stepper UI's JSON API and
the static shell; run state lives in the `runs/` directory via `RunStore`, never in
a database.

Sync route functions (not `async`) so the LangGraph runs execute on the threadpool.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .runstore import RunStore

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


def create_app(store: RunStore | None = None) -> FastAPI:
    store = store or RunStore()
    app = FastAPI(title="Cultural Signal Graph")
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

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
        try:
            return store.snapshot(run_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown run: {run_id}") from None

    @app.put("/api/runs/{run_id}/sources")
    def edit_sources(run_id: str, body: SourcesIn) -> dict:
        try:
            return store.edit_sources(run_id, [s.model_dump() for s in body.sources])
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown run: {run_id}") from None
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None

    @app.post("/api/runs/{run_id}/sources/reset")
    def reset_sources(run_id: str) -> dict:
        try:
            return store.reset_sources(run_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown run: {run_id}") from None
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None

    @app.post("/api/runs/{run_id}/start")
    def start_run(run_id: str) -> dict:
        try:
            return store.start(run_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown run: {run_id}") from None
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None

    @app.post("/api/runs/{run_id}/signoff")
    def signoff(run_id: str, body: SignoffIn) -> dict:
        try:
            return store.signoff(run_id, body.decisions)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown run: {run_id}") from None
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None

    @app.post("/api/runs/{run_id}/signoff/undo")
    def undo_signoff(run_id: str) -> dict:
        try:
            return store.undo_signoff(run_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown run: {run_id}") from None
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None

    @app.get("/api/runs/{run_id}/exports/{name}")
    def export(run_id: str, name: str) -> FileResponse:
        if name not in EXPORT_FILES:
            raise HTTPException(status_code=404, detail=f"unknown export: {name}")
        path = store.root / run_id / name
        if not path.is_file():
            raise HTTPException(status_code=404, detail="run has no exports yet")
        return FileResponse(path, filename=name)

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
