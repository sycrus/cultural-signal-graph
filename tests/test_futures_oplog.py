"""Workshop A (#51, ADR-0013): the operation log lives in SQLite.

Exercised through the OperationLog seam: concurrent appends never lose a write, the
ADR-0008 cursor semantics are unchanged, logs stored the old way (log.jsonl +
cursor.json) still open, and log.jsonl stays the import / export format."""

import json
import threading

import pytest

from cultural_signal_graph.futures.log import OperationLog


def _log(tmp_path, exp="x-1") -> OperationLog:
    return OperationLog(tmp_path / "run-1" / "explorations" / exp)


def _created(tmp_path, exp="x-1") -> OperationLog:
    log = _log(tmp_path, exp)
    log.append({"op": "create", "exploration": {"id": exp}})
    return log


def test_parallel_appends_all_land_in_order(tmp_path):
    log = _created(tmp_path)
    writers, per_writer = 8, 25

    def write(w):
        for i in range(per_writer):
            # each writer opens its own handle, like separate requests on the thread pool
            _log(tmp_path).append({"op": "note", "writer": w, "i": i}, author=f"p{w}")

    threads = [threading.Thread(target=write, args=(w,)) for w in range(writers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ops = log.active()
    assert len(ops) == 1 + writers * per_writer  # none lost
    assert [o["seq"] for o in ops] == list(range(len(ops)))  # dense, in order
    for w in range(writers):  # each writer's own ops kept their order
        assert [o["i"] for o in ops if o.get("writer") == w] == list(range(per_writer))


def test_undo_redo_and_append_after_undo_drops_the_redo_tail(tmp_path):
    log = _created(tmp_path)
    log.append({"op": "a"})
    log.append({"op": "b"})
    assert not log.can_redo()

    log.undo()
    assert [o["op"] for o in log.active()] == ["create", "a"]
    assert log.can_redo() and len(log.ops()) == 3  # b is the redo tail

    log.redo()
    assert [o["op"] for o in log.active()] == ["create", "a", "b"]

    log.undo()
    log.append({"op": "c"}, author="maria")
    assert [o["op"] for o in log.ops()] == ["create", "a", "c"]  # tail dropped
    assert log.active()[-1]["seq"] == 2 and log.active()[-1]["author"] == "maria"
    assert not log.can_redo()


def test_create_is_never_undone(tmp_path):
    log = _created(tmp_path)
    assert not log.can_undo()
    with pytest.raises(ValueError):
        log.undo()


def test_explorations_on_one_run_are_independent(tmp_path):
    a, b = _created(tmp_path, "x-a"), _created(tmp_path, "x-b")
    a.append({"op": "only-a"})
    assert [o["op"] for o in b.active()] == ["create"]
    assert not _log(tmp_path, "x-none").exists()


def test_a_log_stored_the_old_way_still_opens(tmp_path):
    d = tmp_path / "run-1" / "explorations" / "x-old"
    d.mkdir(parents=True)
    old = [{"seq": i, "op": op, "author": "system"} for i, op in enumerate(["create", "a", "b"])]
    (d / "log.jsonl").write_text("".join(json.dumps(o) + "\n" for o in old), encoding="utf-8")
    (d / "cursor.json").write_text(json.dumps({"cursor": 2}), encoding="utf-8")

    log = OperationLog(d)
    assert log.exists()
    assert [o["op"] for o in log.active()] == ["create", "a"]  # cursor carried over
    assert log.can_redo()
    log.append({"op": "c"})
    assert [o["op"] for o in OperationLog(d).ops()] == ["create", "a", "c"]


def test_import_ops_writes_a_whole_log(tmp_path):
    ops = [{"seq": 0, "op": "create"}, {"seq": 1, "op": "a"}, {"seq": 2, "op": "b"}]
    log = _log(tmp_path, "x-imp")
    log.import_ops(ops)
    assert log.active() == ops and log.cursor() == 3
    with pytest.raises(ValueError):
        log.import_ops(ops)  # never overwrites an existing log
