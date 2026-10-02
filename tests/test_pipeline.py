"""evaluators/pipeline.py：单一评估入口（自检任务上端到端），以及各种拒绝路径。"""
from __future__ import annotations

import dataclasses
import json

import pytest

from evaluators import leaderboard as lb
from evaluators import pipeline, tasks
from evaluators.pipeline import evaluate
from schedule_helpers import surface_schedule

PAPER = "selftest-surface-d3-sd6-paper"
DIFF = "selftest-surface-d3-sd6-diff"


def test_registry_is_valid_and_example_task_is_frozen_config():
    t = tasks.get_task("gross-sd6-p4e-3")
    assert t.noise_model == "sd6" and t.p == 4e-3 and t.boundary == "paper" and t.rounds == 12
    assert t.stop["min_sector_errors"] >= 1000 and t.num_workers <= 3
    assert t.decoder["name"] == "bposd" and t.decoder["params"]["osd_order"] == 7
    assert "PENDING E-004" in t.funnel["status"] and t.funnel["tiers"] == []
    code, norm = tasks.build_code(t, None)
    assert (code.n, code.k) == (144, 12) and code.HX.shape == (72, 144)
    for tid, task in tasks.TASKS.items():
        task.validate()
        assert task.noise_model in ("sd6",)


@pytest.mark.parametrize("bad", [
    dict(noise_model="si1000"), dict(noise_model="gross_sd6"),            # LB3 / N1 / N2：只允许 sd6
    dict(stop={"max_shots": 10, "min_sector_errors": 10}),                 # L2-4：小样本规则不可放宽
    dict(num_workers=8), dict(allow_redundant_row_omission=True),          # CPU 规定；L0-2 未裁决前不允许
    dict(boundary="flat"),
])
def test_task_validation_rejects_forbidden_settings(bad):
    t = dataclasses.replace(tasks.get_task(PAPER), **bad)
    with pytest.raises(ValueError):
        t.validate()


def test_gross_code_family_matches_baselines():
    bb = pytest.importorskip("baselines.bb_code")
    import numpy as np
    from baselines.gross import parse_poly
    ref = bb.BBCode(12, 6, parse_poly(["x^3", "y", "y^2"]), parse_poly(["y^3", "x", "x^2"]))
    code, _ = tasks.build_code(tasks.get_task("gross-sd6-p4e-3"), None)
    assert np.array_equal(code.HX, ref.HX) and np.array_equal(code.HZ, ref.HZ)


def test_paper_selftest_scores_and_is_written(selftest_runs):
    rep = selftest_runs["paper"]
    assert rep.status == "scored" and rep.eligible, rep.to_text()
    assert rep.rounds_verified == {"3": {"Z": [3], "X": [3]}}
    assert rep.distance_upper_bound == 3
    assert rep.leaderboard_record["seq"] == 0
    s = rep.score["per_round_P_any"]
    assert 0 < s["low"] <= s["best"] <= s["high"] < 0.1
    assert min(rep.l2["counts"]["fail_Z"], rep.l2["counts"]["fail_X"]) >= 1000
    assert "score:" in rep.to_text()


def test_diff_selftest_both_round_counts_generated_and_l0_checked(selftest_runs):
    """L2-2：diff 的两个轮数的电路都由评估器从同一调度生成，都过 L0（候选无法单独操纵短轮数电路）。"""
    rep = selftest_runs["diff"]
    assert rep.status == "scored" and rep.eligible, rep.to_text()
    assert set(rep.l0) == {"r=3 (with distance)", "r=9"} and all(v["passed"] for v in rep.l0.values())
    assert rep.rounds_verified == {"3": {"Z": [3], "X": [3]}, "9": {"Z": [9], "X": [9]}}
    for r in ("3", "9"):
        c = rep.l2["components"][r]["counts"]
        assert min(c["fail_Z"], c["fail_X"]) >= 1000
        assert rep.l2["components"][r]["circuit"]["candidate_hash"] == rep.circuit_hashes[r]
    d = rep.l2["per_round"]["P_any"]
    assert d["diff"]["valid"] and 0 <= d["low"] <= d["best"] <= d["high"]


def test_rejected_code_and_schedule_have_readable_diagnostics(tmp_path):
    _, spec = surface_schedule(3)
    sched = spec.to_dict()
    r = evaluate(PAPER, {"family": "rotated_surface", "d": 5}, sched, seed=1, leaderboard_path=tmp_path / "b")
    assert r.status == "rejected_code" and "fixes the code" in r.to_text()
    for bad, kw in ((dict(sched, rounds=30), "unknown top-level field"),                # LB1：候选不能给轮数
                    (dict(sched, noise={"p": 0}), "unknown top-level field"),
                    (dict(sched, z_checks=sched["z_checks"][:-1]), "every row (including redundant rows)"),
                    ("{not json", "not valid JSON")):
        r = evaluate(PAPER, None, bad, seed=1, leaderboard_path=tmp_path / "b")
        assert r.status == "rejected_schedule" and kw in r.to_text(), r.to_text()
        assert r.l2 is None and r.leaderboard_record is None
    assert not (tmp_path / "b").exists()


def test_valid_but_bad_schedule_is_rejected_by_l0(tmp_path):
    """模板合法、但 CNOT 顺序破坏对易（不确定）或降低距离的调度：由 L0 拒绝，不进入 L2。"""
    from evaluators.candidate import memory_circuit, parse_schedule, validate_schedule
    code, spec = surface_schedule(3)
    base = spec.to_dict()
    found = None
    import itertools
    for ci in range(len(base["x_checks"])):       # 重排某个 X 校验的 CNOT 时间：模板合法，但与 Z 校验不对易
        ts = [t for _, t in base["x_checks"][ci]["cnots"]]
        for perm in itertools.permutations(ts):
            d = json.loads(json.dumps(base))
            for e, t in zip(d["x_checks"][ci]["cnots"], perm):
                e[1] = t
            s = parse_schedule(d)
            if validate_schedule(s, code):
                continue
            try:
                for b in "ZX":
                    memory_circuit(s, code, b, 2).detector_error_model()
            except ValueError:
                found = d
                break
        if found:
            break
    assert found is not None
    r = evaluate(PAPER, None, found, seed=1, leaderboard_path=tmp_path / "b")
    assert r.status == "rejected_l0", r.to_text()
    assert "[FAIL] Z:determinism" in r.to_text() or "[FAIL] X:determinism" in r.to_text()
    assert r.l2 is None and not (tmp_path / "b").exists()


def test_L2_4_small_sample_not_ranked_and_never_written(tmp_path):
    """预算耗尽时每个 sector 不足 1000 次失败：给出结果但不上榜。"""
    _, spec = surface_schedule(3)
    t = dataclasses.replace(tasks.get_task(PAPER), stop={"max_shots": 2000, "max_errors": 1000,
                                                         "min_sector_errors": 1000, "batch_size": 1000})
    rep = pipeline._evaluate_task(t, None, spec.to_dict(), seed=3, leaderboard_path=tmp_path / "b")
    assert rep.status == "insufficient_statistics" and not rep.eligible
    assert any("fewer than 1000" in x for x in rep.ineligible_reasons)
    assert not (tmp_path / "b").exists()


def test_runtime_modified_task_is_refused(monkeypatch):
    t = tasks.TASKS[PAPER]
    monkeypatch.setitem(t.stop, "min_sector_errors", 1)
    _, spec = surface_schedule(3)
    with pytest.raises(RuntimeError, match="modified at runtime"):
        evaluate(PAPER, None, spec.to_dict(), seed=1, submit=False)


def test_negative_diff_estimate_is_a_failure(monkeypatch, tmp_path):
    """L2-2：diff 点估计为负 → rejected_l2（不给分、不上榜）。用打桩的 sample_l2 模拟 auditor K=25 的情形。"""
    from evaluators.l2 import diff_per_round
    d = diff_per_round(1200, 10000, 3, 1100, 10000, 9)       # P(r2) < P(r1)
    assert d["best"] < 0 and d["valid"] is False and d["low"] <= d["high"]

    class Fake:
        def __init__(self):
            self.per_round = {k: {"best": d["best"], "low": d["low"], "high": d["high"], "diff": d}
                              for k in ("P_Z", "P_X", "P_any")}
            self.components = {}
            self.counts = {}

        def to_dict(self):
            return {"per_round": self.per_round}

    monkeypatch.setattr(pipeline, "sample_l2", lambda *a, **k: Fake())
    _, spec = surface_schedule(3)
    rep = evaluate(DIFF, None, spec.to_dict(), seed=1, leaderboard_path=tmp_path / "b")
    assert rep.status == "rejected_l2" and "diff estimate invalid" in rep.to_text()
    assert not (tmp_path / "b").exists()


def test_selftest_never_written_to_official_board(monkeypatch):
    """自检任务的结果永远不进正式成绩单；正式任务在评估器未冻结时也不进（这里只检查判定，不采样）。"""
    _, spec = surface_schedule(3)
    called = {}
    monkeypatch.setattr(lb, "_append", lambda *a, **k: called.setdefault("x", 1))
    t = dataclasses.replace(tasks.get_task(PAPER), stop={"max_shots": 2000, "max_errors": 1000,
                                                         "min_sector_errors": 1000, "batch_size": 1000})
    rep = pipeline._evaluate_task(t, None, spec.to_dict(), seed=3)    # 默认路径 = 正式成绩单
    assert "x" not in called
    assert any("never written to the official leaderboard" in x for x in rep.ineligible_reasons)


@pytest.mark.slow
@pytest.mark.parametrize("kind", ["ibm", "strikis"])
def test_gross_task_end_to_end_small_budget(kind, tmp_path):
    """gross 示例任务的完整流程（L0 12 轮 + 3 轮距离门槛 10 + L2），只把 L2 预算缩到很小：
    IBM 与 Strikis 调度都通过 L0（d_circ 上界 ≥ 10），结果因样本太小不上榜。"""
    pytest.importorskip("baselines.bb_code")
    from baselines.bb_code import BBCode
    from baselines.gross import parse_poly
    from baselines.schedule import ibm_depth8
    from baselines.strikis import strikis_fig12
    from schedule_helpers import from_baseline
    code = BBCode(12, 6, parse_poly(["x^3", "y", "y^2"]), parse_poly(["y^3", "x", "x^2"]))
    sched = ibm_depth8(code) if kind == "ibm" else strikis_fig12(code)[0]
    t = dataclasses.replace(tasks.get_task("gross-sd6-p4e-3"),
                            stop={"max_shots": 50, "max_errors": 1000, "min_sector_errors": 1000, "batch_size": 25})
    rep = pipeline._evaluate_task(t, None, from_baseline(sched).to_dict(), seed=5, leaderboard_path=tmp_path / "b")
    assert rep.status == "insufficient_statistics", rep.to_text()
    assert rep.distance_upper_bound is not None and rep.distance_upper_bound >= 10
    assert rep.rounds_verified == {"12": {"Z": [12], "X": [12]}}
    assert not (tmp_path / "b").exists()


def test_funnel_tier_can_filter(tmp_path):
    """分层漏斗接口（配置等 E-004）：一层小预算采样，门槛不达标就停止。"""
    _, spec = surface_schedule(3)
    t = dataclasses.replace(tasks.get_task(PAPER), funnel={"status": "test", "tiers": [
        {"name": "quick", "stop": {"max_shots": 2000, "max_errors": None, "min_sector_errors": None,
                                   "batch_size": 1000},
         "promote_if_per_round_P_any_below": 1e-6}]})
    rep = pipeline._evaluate_task(t, None, spec.to_dict(), seed=3, leaderboard_path=tmp_path / "b")
    assert rep.status == "filtered" and rep.funnel[0]["decision"] == "reject"
    assert not (tmp_path / "b").exists()
