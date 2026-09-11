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


class AskIn(BaseModel):
    category: str
    question: str
    window_start: str
    window_end: str
    market: str | None = None


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
