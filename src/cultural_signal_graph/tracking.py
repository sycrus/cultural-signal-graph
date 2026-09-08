"""Prediction-accuracy tracking (issue #17) — soft, lagging telemetry.

Records forecast trends so they can be checked for materialization later, and reports
accuracy. Reported only — never used to gate or score reasoning.
"""

from __future__ import annotations

import json

from .models import ForecastRun


def record_trends(forecast: ForecastRun, path) -> None:
    trends = [
        {
            "id": f"claim-{i}",
            "statement": claim.statement,
            "as_of": forecast.brief.as_of,
            "materialized": None,
        }
        for i, claim in enumerate(forecast.brief.claims, 1)
    ]
    _write(path, {"trends": trends})


def mark_materialized(trend_id: str, materialized: bool, path) -> None:
    data = _read(path)
    for trend in data["trends"]:
        if trend["id"] == trend_id:
            trend["materialized"] = materialized
    _write(path, data)


def report_accuracy(path) -> dict:
    data = _read(path)
    checked = [t for t in data["trends"] if t["materialized"] is not None]
    materialized = sum(1 for t in checked if t["materialized"])
    return {
        "trends_total": len(data["trends"]),
        "checked": len(checked),
        "materialized": materialized,
        "accuracy": materialized / len(checked) if checked else None,
    }


def _read(path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _write(path, data) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
