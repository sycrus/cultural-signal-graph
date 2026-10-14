"""Export an exploration as files: the snapshot (JSON), a readable walk by order
(Markdown), the operation log itself (JSONL — re-importable), and its named graph
(TriG)."""

from __future__ import annotations

import json


def to_markdown(snap: dict) -> str:
    e = snap["exploration"]
    by_id = {p["id"]: p for p in snap["projections"]}
    anchors = {a["id"]: a for a in snap["anchors"]}

    def name(node_id: str) -> str:
        if node_id in by_id:
            return by_id[node_id]["statement"]
        if node_id in anchors:
            return anchors[node_id]["text"]
        return f"{snap['removed'].get(node_id, node_id)} (removed)"

    lines = [
        f"# Exploration: {e['goal']}",
        "",
        f"{e['start_year']} to {e['start_year'] + e['horizon']} · {e['orders']} orders · "
        f"created {e['created_at'][:10]} · speculative: no probabilities, internal use",
        "",
        "## Present (anchors)",
        "",
    ]
    for a in snap["anchors"]:
        tags = [a["kind"]] + ([a["flag"]] if a.get("flag") else []) + (["pending sign-off"] if a.get("pending") else [])
        src = f" ({a['source_uri']})" if a.get("source_uri") else ""
        lines.append(f"- **{a['text']}** _[{', '.join(tags)}]_{src}")
    for order in sorted({p["order"] for p in snap["projections"]}):
        lines += ["", f"## Order {order}", ""]
        for p in (q for q in snap["projections"] if q["order"] == order):
            marks = [m for m, on in (
                ("baseline", p.get("baseline")),
                ("discontinuity", p.get("discontinuity")),
                (p["origin"], p["origin"] != "generated"),
                ("stale", p.get("stale")),
                ("timing conflict", p.get("timing_conflict")),
            ) if on]
            for lens, tag in p.get("tags", {}).items():
                marks.append(f"{lens}: {tag['value']}")
            years = str(p["window"][0]) if p["window"][0] == p["window"][1] else f"{p['window'][0]}–{p['window'][1]}"
            lines.append(f"- **{years}** {p['statement']}" + (f" _[{', '.join(marks)}]_" if marks else ""))
            sources = [name(s) for s in p["parents"] + p["anchors"]]
            if sources:
                lines.append(f"  - grows from: {'; '.join(sources)}")
    return "\n".join(lines) + "\n"


def to_json(snap: dict) -> str:
    return json.dumps(snap, indent=2, ensure_ascii=False)
