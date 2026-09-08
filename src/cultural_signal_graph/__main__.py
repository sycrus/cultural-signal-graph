"""CLI: `python -m cultural_signal_graph` runs the slice and writes artifacts.

Writes brief.md, brief.json, and graph.ttl into ./out/ (gitignored) and echoes
the Markdown brief to stdout.
"""

import json
import sys
from pathlib import Path

from .fixtures import SEED_CORPUS
from .pipeline import run
from .slides import write_presentation
from .tracing import aggregate_usage, init_tracing_from_env
from .viz import write_graph_html


def main() -> None:
    # Windows consoles default to cp1252; force UTF-8 so the brief's Unicode
    # (→ and ≈) prints without raising UnicodeEncodeError.
    sys.stdout.reconfigure(encoding="utf-8")

    # Enable OTel trace export (e.g. to Langfuse) when the OTLP env vars are set.
    init_tracing_from_env()

    forecast = run(SEED_CORPUS)
    out = Path("out")
    out.mkdir(exist_ok=True)
    (out / "brief.md").write_text(forecast.brief.to_markdown(), encoding="utf-8")
    (out / "brief.json").write_text(forecast.brief.to_json(), encoding="utf-8")
    (out / "graph.ttl").write_text(forecast.graph.serialize(format="turtle"), encoding="utf-8")
    write_graph_html(forecast, out / "graph.html")
    write_presentation(forecast.brief, out / "brief.pptx")
    (out / "usage.json").write_text(
        json.dumps(aggregate_usage(forecast.usage), indent=2), encoding="utf-8"
    )
    print(forecast.brief.to_markdown())


if __name__ == "__main__":
    main()
