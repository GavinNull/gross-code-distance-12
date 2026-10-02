"""评估器 v2.1：只评距离的任务（kind="distance"，H-004）、screen 入口、见证翻译成调度坐标。"""
from __future__ import annotations

import copy
import random

import numpy as np
import pytest

from evaluators import candidate as cand
from evaluators import leaderboard as lb
from evaluators import pipeline, tasks
from schedule_helpers import surface_schedule
import v21_helpers as H

DCIRC = ["bb72-dcirc", "bb90-dcirc", "bb108-dcirc", "bb120-dcirc", "cp126-dcirc", "gross-dcirc"]
NK = {"bb72-dcirc": (72, 12), "bb90-dcirc": (90, 8), "bb108-dcirc": (108, 8), "bb120-dcirc": (120, 8),
      "cp126-dcirc": (126, 12), "gross-dcirc": (144, 12)}


@pytest.mark.parametrize("tid", DCIRC)
def test_dcirc_tasks_registered_and_codes_match_e004(tid):
    t = tasks.get_task(tid)
    t.validate()
    assert t.kind == "distance" and t.purpose == "score" and t.num_workers <= 3
    assert t.schedule_constraints == {"max_period": 8}
    assert t.l0["distance_rounds"] == 3 and t.l0["distance_seed"] == "derived"
    code, spec = H.dcirc_ibm_spec(tid)              # 断言 search 构造的矩阵与评估器逐元素相同
    assert (code.n, code.k) == NK[tid]
    assert spec.period == 8 and not cand.validate_schedule(spec, code)


def test_evaluators_do_not_import_search_or_baselines():
    import pathlib
    import re
    pat = re.compile(r"^\s*(import|from)\s+(search|baselines)\b", re.M)
    for f in pathlib.Path(tasks.__file__).parent.glob("*.py"):
        assert not pat.search(f.read_text()), f


@pytest.mark.parametrize("bad", [dict(boundary="paper"), dict(stop={"max_shots": 1}),
                                 dict(l0={"distance_rounds": 3, "distance_seed": 0}),
                                 dict(rounds=4), dict(kind="other"), dict(schedule_constraints={"max_depth": 3})])
def test_distance_task_validation(bad):
    import dataclasses
    t = dataclasses.replace(tasks.get_task("bb90-dcirc"), **bad)
    with pytest.raises(ValueError):
        t.validate()


def test_period_above_8_rejected():
    code, spec = H.dcirc_ibm_spec("bb72-dcirc")
    rng = random.Random(3)
    longer = None
    while longer is None:
        longer = H.free_window_variant(spec, rng, 10)
    rep = pipeline.screen("bb72-dcirc", None, longer.to_dict())
    assert rep.status == "rejected_schedule"
    assert any("exceeds this task's maximum 8" in d for d in rep.diagnostics)


@pytest.fixture(scope="module")
def bb72_eval(tmp_path_factory):
    code, spec = H.dcirc_ibm_spec("bb72-dcirc")
    board = tmp_path_factory.mktemp("dboard") / "board.jsonl"
    rep = pipeline.evaluate("bb72-dcirc", None, spec.to_dict(), seed=123, candidate_id="bb72-ibm",
                            leaderboard_path=board)
    return {"rep": rep, "board": board, "spec": spec, "code": code}


def test_bb72_distance_task_scored_and_written(bb72_eval):
    rep = bb72_eval["rep"]
    assert rep.status == "scored" and rep.kind == "distance", rep.to_text()
    assert rep.l2 is None and rep.funnel == []
    assert rep.seed == pipeline.derive_seed(rep.task_hash, rep.schedule_hash, "distance")
    assert any("caller seed 123 ignored" in d for d in rep.diagnostics)
    s = rep.score
    assert s["d_circ_upper_bound"] == 6 and s["period"] == 8 and s["low_weight_witnesses"] >= 1
    assert s["sort_key"] == [-6, s["low_weight_witnesses"], 8]
    rec = rep.leaderboard_record
    assert rec is not None and rec["kind"] == "distance"
    for b in "ZX":
        w = rec["distance"]["per_basis"][b]
        assert len(w["faults"]) == w["weight"] >= 6
        assert len(w["witness_in_schedule_coordinates"]) == w["weight"]
    assert lb.verify_leaderboard(bb72_eval["board"]) == []
    t = lb.table("bb72-dcirc", bb72_eval["board"])
    assert t[0]["d_circ_upper_bound"] == 6 and t[0]["period"] == 8


def test_distance_record_forgeries_detected(bb72_eval):
    rec = {k: v for k, v in bb72_eval["rep"].leaderboard_record.items() if k not in lb.SYSTEM_FIELDS}
    assert lb.entry_problems(rec) == []
    # 1) 声称更大的距离，但见证还是 6
    f = copy.deepcopy(rec)
    f["score"]["d_circ_upper_bound"] = 8
    f["score"]["sort_key"][0] = -8
    f["distance"]["d_circ_upper_bound"] = f["distance_upper_bound"] = 8
    assert lb.entry_problems(f)
    # 2) 把见证换成一个不是逻辑错误的故障集合（删掉一个故障，权重跟着改）
    f = copy.deepcopy(rec)
    for b in "ZX":
        f["distance"]["per_basis"][b]["faults"] = f["distance"]["per_basis"][b]["faults"][:-1]
        f["distance"]["per_basis"][b]["weight"] -= 1
    f["distance"]["d_circ_upper_bound"] = f["distance_upper_bound"] = 5
    assert any("re-injection" in p for p in lb.entry_problems(f))
    # 3) 少报低权重见证数 / 改种子 / 改预算
    f = copy.deepcopy(rec)
    f["score"]["low_weight_witnesses"] = 1
    assert lb.entry_problems(f)
    assert any("seed" in p for p in lb.entry_problems(dict(rec, seed=1)))
    f = copy.deepcopy(rec)
    f["distance_params"]["distance_bposd_trials"] = 10
    assert any("budget" in p for p in lb.entry_problems(f))


def test_screen_matches_evaluate_and_never_writes(bb72_eval, tmp_path):
    rep = pipeline.screen("bb72-dcirc", None, bb72_eval["spec"].to_dict())
    ev = bb72_eval["rep"]
    assert rep.status == "screened" and rep.leaderboard_record is None
    assert rep.score == ev.score and rep.seed == ev.seed
    for b in "ZX":
        assert rep.distance["per_basis"][b]["faults"] == ev.distance["per_basis"][b]["faults"]
    txt = rep.to_text()
    assert "schedule coordinates" in txt and "CNOT of" in txt


def test_witness_coordinates_are_consistent_with_the_schedule(bb72_eval):
    """每个 CNOT 故障翻译出来的 (校验, 数据列, 周期内时间步) 必须正是调度 JSON 里那个 CNOT 的时间步。"""
    rep = bb72_eval["rep"]
    canon = cand.parse_schedule(rep.schedule)
    checks = {"X": canon.x_checks, "Z": canon.z_checks}
    n_cnot = 0
    for b in "ZX":
        for c in rep.distance["per_basis"][b]["coords"]:
            if c["op"] != "cnot":
                continue
            n_cnot += 1
            typ, idx = c["check"].split("#")
            t = dict(checks[typ][int(idx)].cnots)[c["data_col"]]
            assert t == c["step"], c
            assert 0 <= c["round"] < 3
    assert n_cnot > 0


def test_describe_faults_unit_surface():
    code, spec = surface_schedule(3)
    canon = spec.canonical()
    U = cand.unroll(canon, code, 3)
    lay = cand.layout_for(code)
    layer, (a, b) = next((t, pr) for t, prs in sorted(U.cnots.items()) for pr in prs)
    anc = a if a >= code.n else b
    col = b if anc == a else a
    out = cand.describe_faults(canon, code, 3, [{"tick": layer, "gate": "DEPOLARIZE2", "qubits": [a, b],
                                                 "paulis": [f"Z{col}"]},
                                                {"tick": 0, "gate": "X_ERROR", "qubits": [0], "paulis": ["X0"]},
                                                {"tick": U.num_layers, "gate": "X_ERROR", "qubits": [4],
                                                 "paulis": ["X4"]}])
    typ = "X" if anc in lay.x_anc else "Z"
    idx = (lay.x_anc if typ == "X" else lay.z_anc).index(anc)
    assert out[0]["op"] == "cnot" and out[0]["check"] == f"{typ}#{idx}" and out[0]["data_col"] == col
    assert out[0]["round"] == 0 and out[0]["paulis"] == [(f"data col {col}", "Z")]
    assert out[1]["op"] == "data_reset" and out[2]["op"] == "readout"


@pytest.mark.slow
@pytest.mark.parametrize("tid,known", [("bb90-dcirc", 8), ("bb108-dcirc", 8), ("bb120-dcirc", 10),
                                       ("cp126-dcirc", 9)])
def test_ibm_schedules_reproduce_known_dcirc_upper_bounds(tid, known):
    """E-004 / 文献的 d_circ 上界在任务预算下复现（每个约 1–1.5 分钟，3 进程）。"""
    code, spec = H.dcirc_ibm_spec(tid)
    rep = pipeline.screen(tid, None, spec.to_dict())
    assert rep.status == "screened", rep.to_text()
    assert rep.score["d_circ_upper_bound"] == known
