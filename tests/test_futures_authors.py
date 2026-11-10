"""Workshop B (#52): named authors on every op — a name plus a role.

Through the HTTP seam over the fixture exploration: human edits record who made
them, model ops record the model call and the human who triggered it, and logs
written before authors existed still replay."""

import json

import pytest
from fastapi.testclient import TestClient

from cultural_signal_graph.futures.fixtures import FIXTURE_GOAL
from cultural_signal_graph.runstore import RunStore, fixture_stage_fns
from cultural_signal_graph.server import create_app

SEED_ANCHORS = ["sig-release-note", "sig-search-spike", "sig-viral-fad", "sig-gaming-chatter"]
MARIA = {"author": "Maria", "role": "Service designer"}


@pytest.fixture()
def client(tmp_path):
    return TestClient(create_app(RunStore(tmp_path, stage_fns=fixture_stage_fns())))


@pytest.fixture()
def base(client) -> str:
    run_id = client.post(
        "/api/runs",
        json={"category": "tech", "question": "AI wearables adoption", "window_start": "2026-01-01", "window_end": "2026-06-30"},
    ).json()["id"]
    client.post(f"/api/runs/{run_id}/start")
    body = {"goal": FIXTURE_GOAL, "anchor_ids": SEED_ANCHORS, "horizon": 10, "orders": 5, **MARIA}
    exp = client.post(f"/api/runs/{run_id}/explorations", json=body).json()
    return f"/api/runs/{run_id}/explorations/{exp['exploration']['id']}"


def _ops(client, base) -> list[dict]:
    return [json.loads(line) for line in client.get(f"{base}/exports/log.jsonl").text.splitlines()]


def test_create_records_name_and_role(client, base):
    create = _ops(client, base)[0]
    assert (create["author"], create["author_role"]) == ("Maria", "Service designer")


def test_a_human_edit_records_name_and_role(client, base):
    client.post(f"{base}/generate", params={"author": "Maria"})
    res = client.patch(f"{base}/projections/o1-privacy-rules", json={"statement": "Rules shelved", "author": "Ken", "role": "Strategist"})
    assert res.status_code == 200
    edit = _ops(client, base)[-1]
    assert edit["op"] == "edit"
    assert (edit["author"], edit["author_role"]) == ("Ken", "Strategist")


def test_model_ops_record_the_call_and_the_human_who_triggered_it(client, base):
    client.post(f"{base}/generate", params=MARIA)
    gen = [o for o in _ops(client, base) if o["op"] == "generate_order"]
    assert gen and all(o["author"] == "Maria" and o["author_role"] == "Service designer" for o in gen)
    assert all("model" in o for o in gen)  # the model call stays on the op

    client.post(f"{base}/lenses/cone/classify", params={"author": "Ken", "role": "Strategist"})
    retag = [o for o in _ops(client, base) if o["op"] == "retag"][-1]
    assert (retag["author"], retag["author_role"]) == ("Ken", "Strategist")


def test_live_fill_records_who_started_it(client, base):
    with client.stream("POST", f"{base}/generate/stream", params=MARIA) as res:
        assert res.status_code == 200
        "".join(res.iter_text())
    gen = [o for o in _ops(client, base) if o["op"] == "generate_order"]
    assert gen and {o["author"] for o in gen} == {"Maria"}


def test_without_a_name_the_default_author_stands(client, base):
    client.post(f"{base}/generate")
    gen = [o for o in _ops(client, base) if o["op"] == "generate_order"]
    assert {o["author"] for o in gen} == {"strategist"}
    assert all("author_role" not in o for o in gen)


def test_a_log_without_authors_still_replays(client, base):
    client.post(f"{base}/generate", params=MARIA)
    ops = _ops(client, base)
    for o in ops:
        o.pop("author", None)
        o.pop("author_role", None)
    run_base = base.rsplit("/explorations/", 1)[0]
    res = client.post(f"{run_base}/explorations/import", json={"log": "".join(json.dumps(o) + "\n" for o in ops)})
    assert res.status_code == 201, res.text
    assert len(res.json()["projections"]) == len(client.get(base).json()["projections"])
