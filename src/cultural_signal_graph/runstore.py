"""File-backed run store for the local web app (issues #20–#22).

A run is a directory under `runs/`: `run.json` (the ask, the editable sources, stage
status with per-stage tokens/latency, sign-off state), the LangGraph SQLite checkpoint
(#14), and — once finalized — the export artifacts (brief.md/json, graph.ttl,
graph.html, usage.json, trends.json). Reopening a run is reading these files back;
there is no database.

The lifecycle mirrors the pipeline's interrupt: `start` runs extract → align and
*pauses* at the gate; `signoff(decisions)` resumes via the file-backed checkpoint and
finalizes; `undo_signoff` rewinds to the pre-gate state (persisted at the pause
boundary) so the decision can be re-made and the downstream re-runs.

Stage functions are the same seams the pipeline uses: the live DeepSeek stages when
DEEPSEEK_API_KEY is set, fixture stages otherwise, so the whole loop runs offline.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from langgraph.types import Command

from .checkpoint import dump_state, file_checkpointer
from .config import load_dotenv
from .discovery import SOURCE_INDEX, discover_sources
from .eval import DEFAULT_THRESHOLDS, check, evaluate
from .fixtures import ALIGNED_EDGES, DRAFTED_REASONING, EXTRACTED, SEED_CORPUS
from .golden import SEED_CASE
from .models import (
    Ask,
    Extraction,
    SourceDoc,
    TimeWindow,
    extraction_from_dict,
    source_doc_from_dict,
    source_doc_to_dict,
)
from .pipeline import build_forecast_graph, forecast_run_from_state, initial_state
from .slides import write_presentation
from .tracking import record_trends, report_accuracy
from .tracing import get_usage
from .viz import write_graph_html

load_dotenv()

# The stepper's stages, in rail order. "sign-off" is the gate that pauses the run.
STAGES = ("ask", "sources", "extract", "align", "sign-off", "draft", "brief")

StateFns = tuple  # (extract_fn, align_fn, draft_fn)


def fixture_stage_fns() -> StateFns:
    """Fixture-backed stages: the recorded golden outputs, no model, no network.

    Extraction filters the fixture signals to those whose source survived source
    edits, so the demo stays consistent when the strategist overrides sources.
    """
    def extract(corpus: list[SourceDoc]) -> Extraction:
        uris = {s.uri for s in corpus}
        return Extraction(
            entities=list(EXTRACTED.entities),
            signals=[s for s in EXTRACTED.signals if s.source_uri in uris],
        )

    return (
        extract,
        lambda _extraction: list(ALIGNED_EDGES),
        lambda _extraction, _category: dict(DRAFTED_REASONING),
    )


def live_stage_fns() -> StateFns:
    """The real model stages (DeepSeek via its Anthropic-compatible endpoint)."""
    from .alignment import align
    from .draft import draft
    from .extraction import extract

    return extract, align, draft


def default_stage_fns() -> StateFns:
    """Live stages when an API key is configured, fixture stages otherwise."""
    if os.environ.get("DEEPSEEK_API_KEY"):
        return live_stage_fns()
    return fixture_stage_fns()


class RunStore:
    """Creates, advances, and reopens forecast runs backed by the `runs/` directory."""

    def __init__(
        self,
        root: str | Path = "runs",
        stage_fns: StateFns | None = None,
        index: list[SourceDoc] | None = None,
    ):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        if stage_fns is None:
            stage_fns = default_stage_fns()
        self._extract_fn, self._align_fn, self._draft_fn = stage_fns
        # mode records which stages a run will actually execute (function identity,
        # since live_stage_fns() hands back the module-level functions).
        self.mode = "live" if stage_fns == live_stage_fns() else "fixture"
        self._index = index if index is not None else SOURCE_INDEX

    # --- lifecycle ---------------------------------------------------------

    def create(
        self,
        category: str,
        question: str,
        window_start: str,
        window_end: str,
        market: str | None = None,
    ) -> dict:
        """A new run: record the ask, run source discovery, park at 'created'."""
        run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        ask = Ask(
            category=category,
            question=question,
            window=TimeWindow(start=window_start, end=window_end),
            market=market or None,
        )
        sources = self._select_sources(ask)
        run = {
            "id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": self.mode,
            "ask": {
                "category": ask.category,
                "question": ask.question,
                "window": asdict(ask.window),
                "market": ask.market,
            },
            "sources": [source_doc_to_dict(s) for s in sources],
            "status": "created",
            "stages": {name: {"status": "pending"} for name in STAGES},
            "pending": [],
            "decisions": {},
            "usage_calls": [],
            "thread_gen": 0,
        }
        run["stages"]["ask"] = {"status": "done"}
        run["stages"]["sources"] = {"status": "done"}
        self._save(run)
        return self.snapshot(run_id)

    def start(self, run_id: str) -> dict:
        """Run extract → align; pause at the sign-off gate (or finish if no edges)."""
        run = self._require(run_id, "created")
        run["status"] = "running"
        self._save(run)
        try:
            graph = build_forecast_graph(
                *self._timed_fns(run), checkpointer=self._checkpointer(run_id)
            )
            config = {"configurable": {"thread_id": self._thread(run)}}
            corpus = [source_doc_from_dict(s) for s in run["sources"]]
            result = graph.invoke(initial_state(corpus, run["ask"]["category"]), config)
            state = graph.get_state(config)
        except Exception:
            run["status"] = "created"  # failed before any stage boundary; retryable
            self._save(run)
            raise

        values = state.values
        if interrupts := result.get("__interrupt__"):
            payload = interrupts[0].value["sign_off"]
            dump_state(dict(values), self._dir(run_id) / "state-pause.json")
            run["pending"] = self._pending(payload, values["extraction"])
            run["status"] = "paused"
            run["stages"]["sign-off"] = {"status": "paused"}
        else:
            # No proposed edges: the gate passed straight through — finalize.
            self._finalize(run, values)
        self._save(run)
        return self.snapshot(run_id)

    def signoff(self, run_id: str, decisions: dict[str, bool]) -> dict:
        """Resume the paused run with approve/reject per edge, then finalize."""
        run = self._require(run_id, "paused")
        run["status"] = "running"
        self._save(run)
        try:
            graph = build_forecast_graph(
                *self._timed_fns(run), checkpointer=self._checkpointer(run_id)
            )
            config = {"configurable": {"thread_id": self._thread(run)}}
            graph.invoke(Command(resume=decisions), config)
            values = graph.get_state(config).values
        except Exception:
            run["status"] = "paused"  # the run is still parked at the gate
            self._save(run)
            raise
        run["decisions"] = decisions
        run["pending"] = []
        self._finalize(run, values)
        self._save(run)
        return self.snapshot(run_id)

    def undo_signoff(self, run_id: str) -> dict:
        """Reopen the sign-off: rewind to the pre-gate state; downstream re-runs.

        The decisions are wiped and the run parks at the gate again — over a *fresh
        thread* rebuilt from `state-pause.json`, so the next sign-off resumes through
        the same checkpointed interrupt as the first.
        """
        run = self._require(run_id, "completed")
        pause_path = self._dir(run_id) / "state-pause.json"
        if not pause_path.exists():
            raise ValueError(f"run {run_id} never paused at the gate; nothing to undo")
        pre_gate = json.loads(pause_path.read_text(encoding="utf-8"))

        run["thread_gen"] += 1
        run["status"] = "running"
        self._save(run)
        try:
            graph = build_forecast_graph(
                *self._timed_fns(run), checkpointer=self._checkpointer(run_id)
            )
            config = {"configurable": {"thread_id": self._thread(run)}}
            graph.update_state(config, pre_gate, as_node="align")
            result = graph.invoke(None, config)
            payload = result["__interrupt__"][0].value["sign_off"]
        except Exception:
            run["thread_gen"] -= 1
            run["status"] = "completed"
            self._save(run)
            raise

        run["decisions"] = {}
        run["pending"] = self._pending(payload, pre_gate["extraction"])
        run["status"] = "paused"
        run["stages"]["sign-off"] = {"status": "paused"}
        # the downstream re-runs once the re-made decision resolves
        run["stages"]["draft"] = {"status": "pending"}
        run["stages"]["brief"] = {"status": "pending"}
        self._save(run)
        return self.snapshot(run_id)

    # --- sources (pre-run edits) -------------------------------------------

    def edit_sources(self, run_id: str, sources: list[dict]) -> dict:
        """Replace the corpus before the run starts (the strategist's override)."""
        run = self._require(run_id, "created")
        run["sources"] = [source_doc_to_dict(source_doc_from_dict(s)) for s in sources]
        self._save(run)
        return self.snapshot(run_id)

    def reset_sources(self, run_id: str) -> dict:
        """Restore the auto-discovered source set."""
        run = self._require(run_id, "created")
        run["sources"] = [
            source_doc_to_dict(s) for s in self._select_sources(self._ask(run))
        ]
        self._save(run)
        return self.snapshot(run_id)

    def _select_sources(self, ask: Ask) -> list[SourceDoc]:
        """The auto-discovered sources for an ask. Fixture runs pin the seed corpus:
        the recorded outputs are authored against it, so discovery's index selection
        would leave the fixture signals with nothing to cite. Live runs discover."""
        if self.mode == "fixture":
            return list(SEED_CORPUS)
        return discover_sources(ask, self._index)

    # --- metrics -------------------------------------------------------------

    def metrics(self, run_id: str) -> dict:
        """The Metrics tab's data: cost (tokens), per-stage latency, eval scores
        (when a golden case matches the corpus), and prediction accuracy.

        Accuracy is soft, lagging telemetry (#17): trends are recorded at finalize
        and marked materialized later, so an unchecked run reports null accuracy —
        never a gate."""
        run = self._load(run_id)
        usage_path = self._dir(run_id) / "usage.json"
        trends_path = self._dir(run_id) / "trends.json"
        report: dict = {
            "usage": json.loads(usage_path.read_text(encoding="utf-8"))
            if usage_path.exists()
            else self._aggregate(run["usage_calls"]),
            "stages": {k: v for k, v in run["stages"].items() if v.get("status") == "done"},
            "eval": None,
            "accuracy": None,
        }

        state_path = self._dir(run_id) / "state-final.json"
        if not state_path.exists():
            return report  # not finalized: tokens/stages only

        # The golden case measures the pipeline's correctness *before* human judgment
        # (a batch run's edges are all held at the gate). For an interactive run the
        # faithful scoring point is therefore the pause state, when there was one;
        # the strategist's decisions live in the Brief, not in the pipeline score.
        pause_path = self._dir(run_id) / "state-pause.json"
        if pause_path.exists():
            eval_values = json.loads(pause_path.read_text(encoding="utf-8"))
            scored_at = "gate (pre-sign-off)"
        else:
            eval_values = json.loads(state_path.read_text(encoding="utf-8"))
            scored_at = "finalize"
        forecast = forecast_run_from_state(eval_values)

        seed_uris = sorted(source.uri for source in SEED_CORPUS)
        run_uris = sorted(s["uri"] for s in run["sources"])
        if run_uris == seed_uris:
            scores = evaluate(forecast, SEED_CASE)
            report["eval"] = {
                "case": SEED_CASE.name,
                "scored_at": scored_at,
                "scores": scores,
                "below_threshold": check(scores, DEFAULT_THRESHOLDS),
            }
        else:
            report["eval"] = {
                "case": None,
                "scores": None,
                "reason": "no golden case matches this run's corpus",
            }

        if trends_path.exists():
            report["accuracy"] = report_accuracy(trends_path)
        return report

    # --- reads ---------------------------------------------------------------

    def list(self) -> list[dict]:
        """All runs, newest first (the reopen list)."""
        runs = [self._load(run_id) for run_id in self._run_ids()]
        runs.sort(key=lambda r: r["created_at"], reverse=True)
        return [
            {
                "id": r["id"],
                "created_at": r["created_at"],
                "mode": r["mode"],
                "status": r["status"],
                "ask": r["ask"],
            }
            for r in runs
        ]

    def snapshot(self, run_id: str) -> dict:
        """Everything the stepper needs to render a run."""
        run = self._load(run_id)
        brief_path = self._dir(run_id) / "brief.json"
        usage_path = self._dir(run_id) / "usage.json"
        return {
            "id": run["id"],
            "created_at": run["created_at"],
            "mode": run["mode"],
            "status": run["status"],
            "ask": run["ask"],
            "sources": run["sources"],
            "stages": run["stages"],
            "pending": run["pending"],
            "decisions": run["decisions"],
            "brief": json.loads(brief_path.read_text(encoding="utf-8"))
            if brief_path.exists()
            else None,
            "usage": json.loads(usage_path.read_text(encoding="utf-8"))
            if usage_path.exists()
            else None,
        }

    # --- notes (annotations overlay) ------------------------------------------

    def notes(self, run_id: str) -> list[dict]:
        """The run's notes, append-only. An overlay: never read by the pipeline."""
        path = self._dir(run_id) / "notes.json"
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def add_note(
        self, run_id: str, target_id: str, text: str, author: str = "strategist", target_kind: str = "node"
    ) -> dict:
        """Attach a note to a node/edge. Appended with author + timestamp; nothing
        about the run's reasoning, graph, or brief is touched."""
        self._load(run_id)  # notes attach to a real run
        if not text.strip():
            raise ValueError("note text is empty")
        note = {
            "target_id": target_id,
            "target_kind": target_kind,
            "text": text.strip(),
            "author": author.strip() or "strategist",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        notes = self.notes(run_id)
        notes.append(note)
        path = self._dir(run_id) / "notes.json"
        path.write_text(json.dumps(notes, indent=2), encoding="utf-8")
        return note

    # --- internals -----------------------------------------------------------

    def _timed_fns(self, run: dict) -> StateFns:
        """Stage fns wrapped to record per-stage tokens (from the usage log the OTel
        model-call spans feed) + latency into the run record."""

        def timed(name: str, fn):
            def wrapper(*args):
                before = len(get_usage())
                started = time.perf_counter()
                try:
                    return fn(*args)
                finally:
                    usage = get_usage()[before:]
                    run["stages"][name] = {
                        "status": "done",
                        "tokens": sum(u.total_tokens for u in usage),
                        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                    }
                    run["usage_calls"].extend(asdict(u) for u in usage)

            return wrapper

        return (
            timed("extract", self._extract_fn),
            timed("align", self._align_fn),
            timed("draft", self._draft_fn),
        )

    def _finalize(self, run: dict, values: dict) -> None:
        """Write the export artifacts and mark the run completed."""
        run_id = run["id"]
        out = self._dir(run_id)
        started = time.perf_counter()
        run["stages"]["sign-off"] = {"status": "done"}
        forecast = forecast_run_from_state(values)
        dump_state(values, out / "state-final.json")
        (out / "brief.md").write_text(forecast.brief.to_markdown(), encoding="utf-8")
        (out / "brief.json").write_text(forecast.brief.to_json(), encoding="utf-8")
        (out / "graph.ttl").write_text(forecast.graph.serialize(format="turtle"), encoding="utf-8")
        write_graph_html(forecast, out / "graph.html")
        write_presentation(forecast.brief, out / "brief.pptx")
        usage = self._aggregate(run["usage_calls"])
        (out / "usage.json").write_text(json.dumps(usage, indent=2), encoding="utf-8")
        record_trends(forecast, out / "trends.json")
        run["stages"]["brief"] = {
            "status": "done",
            "tokens": 0,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }
        run["status"] = "completed"

    @staticmethod
    def _aggregate(calls: list[dict]) -> dict:
        return {
            "input_tokens": sum(c["input_tokens"] for c in calls),
            "output_tokens": sum(c["output_tokens"] for c in calls),
            "total_tokens": sum(c["total_tokens"] for c in calls),
            "calls": calls,
        }

    @staticmethod
    def _pending(payload: list[dict], extraction: dict) -> list[dict]:
        """The gate's sign_off payload, with entity ids resolved to display names."""
        by_id = {e["id"]: e for e in extraction["entities"]}

        def field(entity_id: str, key: str, fallback: str) -> str:
            return by_id.get(entity_id, {}).get(key, fallback)

        return [
            {
                "id": e["id"],
                "left_entity_id": e["left_entity_id"],
                "right_entity_id": e["right_entity_id"],
                "left": field(e["left_entity_id"], "name", e["left_entity_id"]),
                "right": field(e["right_entity_id"], "name", e["right_entity_id"]),
                "left_category": field(e["left_entity_id"], "category", "?"),
                "right_category": field(e["right_entity_id"], "category", "?"),
                "confidence": e["confidence"],
            }
            for e in payload
        ]

    def _require(self, run_id: str, status: str) -> dict:
        run = self._load(run_id)
        if run["status"] != status:
            raise ValueError(f"run {run_id} is {run['status']!r}, expected {status!r}")
        return run

    @staticmethod
    def _ask(run: dict) -> Ask:
        window = run["ask"]["window"]
        return Ask(
            category=run["ask"]["category"],
            question=run["ask"]["question"],
            window=TimeWindow(start=window["start"], end=window["end"]),
            market=run["ask"]["market"],
        )

    @staticmethod
    def _thread(run: dict) -> str:
        return run["id"] if run["thread_gen"] == 0 else f"{run['id']}.{run['thread_gen']}"

    def _checkpointer(self, run_id: str):
        return file_checkpointer(str(self._dir(run_id) / "checkpoints.sqlite"))

    def _run_ids(self) -> list[str]:
        return sorted(p.name for p in self.root.iterdir() if (p / "run.json").exists())

    def _load(self, run_id: str) -> dict:
        path = self._dir(run_id) / "run.json"
        if not path.exists():
            raise KeyError(f"unknown run: {run_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, run: dict) -> None:
        self._dir(run["id"]).mkdir(exist_ok=True)
        path = self._dir(run["id"]) / "run.json"
        path.write_text(json.dumps(run, indent=2), encoding="utf-8")

    def _dir(self, run_id: str) -> Path:
        # run ids are generated here, so a traversal-safe join is enough
        return self.root / run_id
