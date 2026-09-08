"""CLI: `python -m cultural_signal_graph` runs the slice and writes artifacts.

Writes brief.md, brief.json, and graph.ttl into ./out/ (gitignored) and echoes
the Markdown brief to stdout.
"""

import sys
from pathlib import Path

from .fixtures import SEED_CORPUS
from .pipeline import run


def main() -> None:
    # Windows consoles default to cp1252; force UTF-8 so the brief's Unicode
    # (→ and ≈) prints without raising UnicodeEncodeError.
    sys.stdout.reconfigure(encoding="utf-8")

    forecast = run(SEED_CORPUS)
    out = Path("out")
    out.mkdir(exist_ok=True)
    (out / "brief.md").write_text(forecast.brief.to_markdown(), encoding="utf-8")
    (out / "brief.json").write_text(forecast.brief.to_json(), encoding="utf-8")
    (out / "graph.ttl").write_text(forecast.graph.serialize(format="turtle"), encoding="utf-8")
    print(forecast.brief.to_markdown())


if __name__ == "__main__":
    main()
