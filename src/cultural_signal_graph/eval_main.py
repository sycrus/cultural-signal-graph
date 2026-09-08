"""CLI: run the golden set and enforce the regression gate.

`python -m cultural_signal_graph.eval_main` scores each eval case against the golden
set using deterministic fixtures (no live model calls) and exits non-zero if any metric
falls below threshold. A live-model eval is `run(case.corpus, category=case.category)`
with the default (real) stage functions instead of fixtures.
"""

from __future__ import annotations

from .eval import check, evaluate
from .fixtures import ALIGNED_EDGES, DRAFTED_REASONING, EXTRACTED
from .golden import EVAL_CASES
from .pipeline import run


def main() -> int:
    failures = 0
    for case in EVAL_CASES:
        forecast = run(
            case.corpus,
            category=case.category,
            extract_fn=lambda _: EXTRACTED,
            align_fn=lambda _: ALIGNED_EDGES,
            draft_fn=lambda extraction, category: DRAFTED_REASONING,
        )
        metrics = evaluate(forecast, case)
        failing = check(metrics, case.thresholds)
        print(f"{case.name}: {'PASS' if not failing else 'FAIL ' + str(failing)} {metrics}")
        failures += 1 if failing else 0
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
