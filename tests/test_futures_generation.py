"""Live futures generation (#31): per-order model calls through the store, with the
model seam replaced by recorded outputs — no network."""

import json

import pytest

from cultural_signal_graph.config import futures_model
from cultural_signal_graph.futures import generator as gen
from cultural_signal_graph.futures.fixtures import FIXTURE_GOAL, RECORDED_ORDER_OUTPUTS
from cultural_signal_graph.futures.log import OperationLog
from cultural_signal_graph.futures.store import ExplorationStore
from cultural_signal_graph.models import Usage
from cultural_signal_graph.runstore import RunStore, fixture_stage_fns

SEED_ANCHORS = ["sig-release-note", "sig-search-spike", "sig-viral-fad", "sig-gaming-chatter"]


@pytest.fixture()
def run_id(tmp_path):
    runs = RunStore(tmp_path, stage_fns=fixture_stage_fns())
    rid = runs.create("tech", "AI wearables adoption", "2026-01-01", "2026-06-30")["id"]
    runs.start(rid)
    return rid


@pytest.fixture()
def store(tmp_path):
    return ExplorationStore(tmp_path, mode="live")


def script(monkeypatch, outputs):
    """Replace the model seam with a queue of raw outputs; record each prompt."""
    queue = list(outputs)
    prompts = []

    def fake(prompt, call_type="generate"):
        prompts.append(prompt)
        model, temperature = futures_model(call_type)
        return queue.pop(0), Usage(model, 100, 50, 150), model, temperature

    monkeypatch.setattr(gen, "_call_generation_model", fake)
    return prompts


def out(*projections):
    return json.dumps({"projections": list(projections)})


def proj(id, frm, window, baseline=False, discontinuity=False, statement=None):
    return {
        "id": id,
        "statement": statement or id,
        "from": frm,
        "window": window,
        "baseline": baseline,
        "discontinuity": discontinuity,
    }


def explore(store, run_id, **kw):
    args = {"goal": FIXTURE_GOAL, "anchor_ids": SEED_ANCHORS, "horizon": 10, "orders": 5, "start_year": 2026}
    args.update(kw)
    return store.create(run_id, **args)["exploration"]["id"]


def test_live_generation_one_call_and_op_per_order(monkeypatch, store, run_id):
    prompts = script(monkeypatch, RECORDED_ORDER_OUTPUTS)
    exp_id = explore(store, run_id)
    snap = store.generate(run_id, exp_id)

    assert len(prompts) == 5
    assert snap["orders_generated"] == 5
    ops = store.ops(run_id, exp_id)
    gen_ops = [o for o in ops if o["op"] == "generate_order"]
    assert [o["order"] for o in gen_ops] == [1, 2, 3, 4, 5]
    first = gen_ops[0]
    # the op embeds the full input and the raw output, so redo/replay never re-calls
    assert first["input"]["prompt"] == prompts[0]
    assert first["input"]["system"] == gen.SYSTEM_PROMPT
    assert first["output"] == RECORDED_ORDER_OUTPUTS[0]
    assert first["model"] == "deepseek-v4-flash"
    assert first["temperature"] == 0.9
    # the prompt carries the goal, the anchors, and (from order 2) earlier projections
    assert FIXTURE_GOAL in prompts[0] and "sig-viral-fad" in prompts[0]
    assert "o1-glasses-default" in prompts[1]


def test_invariants_hold_on_every_order(monkeypatch, store, run_id):
    script(monkeypatch, RECORDED_ORDER_OUTPUTS)
    snap = store.generate(run_id, explore(store, run_id))
    by_order = {}
    for p in snap["projections"]:
        by_order.setdefault(p["order"], []).append(p)
        assert p["parents"] or p["anchors"]  # the structural check
    for ps in by_order.values():
        assert sum(p["baseline"] for p in ps) == 1
        assert any(p["discontinuity"] for p in ps)
    # the baseline is one continuous branch
    baseline = sorted((p for p in snap["projections"] if p["baseline"]), key=lambda p: p["order"])
    for prev, nxt in zip(baseline, baseline[1:]):
        assert prev["id"] in nxt["parents"]


def test_unanchored_output_is_dropped(monkeypatch, store, run_id):
    script(monkeypatch, [out(
        proj("o1-a", ["sig-release-note"], [2026, 2027], baseline=True, discontinuity=True),
        proj("o1-ghost", ["no-such-id"], [2026, 2027]),
        proj("o1-nothing", [], [2026, 2027]),
    )])
    snap = store.generate(run_id, explore(store, run_id, orders=1))
    assert [p["id"] for p in snap["projections"]] == ["o1-a"]


def test_convergence_is_one_node_with_several_parents(monkeypatch, store, run_id):
    script(monkeypatch, [
        out(
            proj("o1-a", ["sig-release-note"], [2026, 2027], baseline=True),
            proj("o1-b", ["sig-viral-fad"], [2026, 2027], discontinuity=True),
        ),
        out(proj("o2-meet", ["o1-a", "o1-b"], [2028, 2029], baseline=True, discontinuity=True)),
    ])
    snap = store.generate(run_id, explore(store, run_id, orders=2))
    meet = [p for p in snap["projections"] if p["order"] == 2]
    assert len(meet) == 1 and meet[0]["parents"] == ["o1-a", "o1-b"]


def test_caps_bound_each_order(monkeypatch, store, run_id):
    monkeypatch.setenv("CSG_FUTURES_MAX_PER_ORDER", "3")
    monkeypatch.setenv("CSG_FUTURES_MAX_CHILDREN", "2")
    many = [proj(f"o1-{i}", ["sig-release-note"], [2026, 2027]) for i in range(5)]
    many += [proj("o1-d", ["sig-viral-fad"], [2026, 2027], discontinuity=True)]
    script(monkeypatch, [out(*many)])
    snap = store.generate(run_id, explore(store, run_id, orders=1))
    ps = snap["projections"]
    assert len(ps) == 3
    assert sum("sig-release-note" in p["anchors"] for p in ps) == 2
    assert any(p["discontinuity"] for p in ps)  # prioritized past the cap


def test_baseline_is_repaired_to_exactly_one(monkeypatch, store, run_id):
    script(monkeypatch, [out(
        proj("o1-a", ["sig-release-note"], [2026, 2027], baseline=True, discontinuity=True),
        proj("o1-b", ["sig-search-spike"], [2026, 2027], baseline=True),
    )])
    snap = store.generate(run_id, explore(store, run_id, orders=1))
    assert sum(p["baseline"] for p in snap["projections"]) == 1


def test_missing_discontinuity_retries_once_then_warns(monkeypatch, store, run_id):
    plain = out(proj("o1-a", ["sig-release-note"], [2026, 2027], baseline=True))
    prompts = script(monkeypatch, [plain, plain])
    exp_id = explore(store, run_id, orders=1)
    store.generate(run_id, exp_id)
    assert len(prompts) == 2
    (op,) = [o for o in store.ops(run_id, exp_id) if o["op"] == "generate_order"]
    assert op["attempts"] == 2
    assert op["warnings"] == ["no discontinuity in this generation"]


def test_unparseable_output_retries_then_fails(monkeypatch, store, run_id):
    script(monkeypatch, ["not json", "still not json"])
    exp_id = explore(store, run_id, orders=1)
    with pytest.raises(ValueError):
        store.generate(run_id, exp_id)
    assert store.snapshot(run_id, exp_id)["orders_generated"] == 0


def test_time_limit_halts_generation(monkeypatch, store, run_id):
    script(monkeypatch, [
        out(proj("o1-a", ["sig-release-note"], [2026, 2028], baseline=True, discontinuity=True)),
        out(
            proj("o2-late", ["o1-a"], [2031, 2034], baseline=True, discontinuity=True),
            proj("o2-past", ["o1-a"], [2030, 2031], discontinuity=True),
        ),
    ])
    exp_id = explore(store, run_id, horizon=4, orders=5)  # 2026..2030
    snap = store.generate(run_id, exp_id)
    ids = {p["id"]: p for p in snap["projections"]}
    assert "o2-late" not in ids  # starts beyond the horizon
    assert ids["o2-past"]["window"] == [2030, 2030]  # clamped to the horizon
    # every order-2 projection sits at the horizon's last year: no order 3
    gen_orders = [o["order"] for o in OperationLog(store.root / run_id / "explorations" / exp_id).active() if o["op"] == "generate_order"]
    assert gen_orders == [1, 2]


def test_model_routing_is_configurable(monkeypatch):
    assert futures_model("generate") == ("deepseek-v4-flash", 0.9)
    assert futures_model("classify") == ("deepseek-v4-flash", 0.0)
    monkeypatch.setenv("CSG_FUTURES_MODEL_GENERATE", "deepseek-v4-pro")
    monkeypatch.setenv("CSG_FUTURES_TEMP_GENERATE", "0.7")
    assert futures_model("generate") == ("deepseek-v4-pro", 0.7)


def test_failed_generation_can_continue(monkeypatch, store, run_id):
    script(monkeypatch, [RECORDED_ORDER_OUTPUTS[0], "bad", "bad"])
    exp_id = explore(store, run_id)
    with pytest.raises(ValueError):
        store.generate(run_id, exp_id)
    snap = store.snapshot(run_id, exp_id)
    assert snap["orders_generated"] == 1 and snap["can_continue"]
    script(monkeypatch, RECORDED_ORDER_OUTPUTS[1:])
    snap = store.generate(run_id, exp_id)
    assert snap["orders_generated"] == 5 and not snap["can_continue"]
