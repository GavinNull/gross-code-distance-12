"""评估器 v2.1：auditor 第二轮审计（research/audits/2026-10-02-evaluator-v2.md §4“冻结前必须修”第 1–7 条）的回归测试。

每个攻击都按 research/audits/2026-10-02-evaluator-v2-scripts/ 里的复现脚本改写，证明修复后被拒绝或在结构上被排除。
所有成绩单都写临时路径；正式成绩单 research/leaderboard.jsonl 不被碰（test_freeze / test_pipeline 另有检查）。
"""
from __future__ import annotations

import copy
import dataclasses
import inspect
import json
import os
import random
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

import numpy as np
import pytest

from evaluators import candidate as cand
from evaluators import l2 as l2mod
from evaluators import leaderboard as lb
from evaluators import pipeline, tasks
from evaluators.l0 import check_l0
from schedule_helpers import surface_schedule
import v21_helpers as H

PAPER = "selftest-surface-d3-sd6-paper"
DIFF = "selftest-surface-d3-sd6-diff"
ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "research" / "audits" / "2026-10-02-evaluator-v2-scripts"


def _body(rec):
    return {k: v for k, v in rec.items() if k not in lb.SYSTEM_FIELDS}


# ---------------------------------------------------------------------------
# S4 批文件注入（严重）
# ---------------------------------------------------------------------------

# auditor s4_batch_file_injection.py 的攻击进程（只知道目录位置，不 import 评估器、不拿凭证）
ATTACKER = r'''
import json, os, sys, time, glob
target, deadline = sys.argv[1], time.time() + float(sys.argv[2])
fake = {"index": 0, "stim_seed": 0, "shots": 10**7, "fail_Z": 1000, "fail_X": 1000, "fail_any": 1999,
        "fail_both": 1, "bits_Z": "", "bits_X": "", "cpu_s": 0.0}
before = set(glob.glob(os.path.join(target, "l2_*")))
done = set()
while time.time() < deadline:
    for d in [d for d in glob.glob(os.path.join(target, "l2_*")) if d not in before]:
        f = os.path.join(d, "batch_000000000.json")
        if d not in done and os.path.exists(f):
            tmp = os.path.join(d, ".x.tmp")
            try:
                open(tmp, "w").write(json.dumps(fake))
                os.replace(tmp, f)
                done.add(d)
                print("replaced", f, flush=True)
            except OSError:
                pass
    time.sleep(0.001)
'''


def test_S4_public_work_dir_parameter_removed():
    """S4 (c)：调用方不能再指定批文件目录（auditor 攻击 A）；reproduce_entry 同样没有 work_dir。"""
    assert "work_dir" not in inspect.signature(pipeline.evaluate).parameters
    assert "work_dir" not in inspect.signature(lb.reproduce_entry).parameters


def test_S4_batch_file_injection_attack_is_detected(tmp_path, monkeypatch):
    """auditor 攻击 B：扫描临时目录里新出现的 l2_* 目录、替换第 0 批。v2 里这会写进一个低 260 倍的分数；
    现在 HMAC / 逐批核对发现篡改，评估作废（integrity_error），不写榜。
    （评估器的临时目录改到本测试私有的目录，攻击进程只扫描那里，不会碰到同机其他实验的 l2_* 目录。）"""
    private_tmp = tmp_path / "tmp"
    private_tmp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(private_tmp))
    board = tmp_path / "board.jsonl"
    _, spec = surface_schedule(3)
    atk = subprocess.Popen([sys.executable, "-c", ATTACKER, str(private_tmp), "120"], stdout=subprocess.PIPE,
                           text=True)
    time.sleep(0.5)
    try:
        rep = pipeline.evaluate(PAPER, None, spec.to_dict(), seed=11, candidate_id="injected", leaderboard_path=board)
    finally:
        atk.terminate()
        out = atk.communicate()[0]
    assert "replaced" in out, "the attacker never got to replace a batch file (test did not exercise the attack)"
    assert rep.status == "integrity_error", rep.to_text()
    assert any("HMAC" in d or "rejected" in d for d in rep.diagnostics), rep.diagnostics
    assert rep.leaderboard_record is None and rep.score is None
    assert not board.exists() or board.read_text() == ""


def _honest_batch(seed=5, index=3, shots=64):
    rng = np.random.default_rng(1)
    fz, fx = rng.random(shots) < 0.2, rng.random(shots) < 0.2
    return {"index": index, "stim_seed": l2mod._batch_seed(seed, index), "shots": shots,
            "fail_Z": int(fz.sum()), "fail_X": int(fx.sum()), "fail_any": int((fz | fx).sum()),
            "fail_both": int((fz & fx).sum()), "bits_Z": np.packbits(fz).tobytes().hex(),
            "bits_X": np.packbits(fx).tobytes().hex(), "cpu_s": 0.01}


@pytest.mark.parametrize("mutate,why", [
    (lambda r: r.update(shots=10**7), "HMAC"),                               # 不重签：签名失效
    (lambda r: r.update(fail_any=0), "HMAC"),
    (lambda r: r.pop("mac"), "fields"),
])
def test_S4_unsigned_or_modified_batches_rejected(mutate, why):
    key = b"k" * 32
    r = l2mod._sign(key, _honest_batch())
    assert l2mod._check_batch(r, index=3, key=key, seed=5, batch_size=64) is None
    r2 = dict(r)
    mutate(r2)
    msg = l2mod._check_batch(r2, index=3, key=key, seed=5, batch_size=64)
    assert msg and why in msg


@pytest.mark.parametrize("mutate,why", [
    (lambda r: r.update(shots=128), "batch_size"),                           # 即使攻击者拿到密钥并重签
    (lambda r: r.update(index=4), "file name"),
    (lambda r: r.update(fail_Z=r["fail_Z"] - 1), "per-shot failure bits"),
    (lambda r: r.update(fail_both=r["fail_both"] + 1), "per-shot failure bits"),
    (lambda r: r.update(stim_seed=0), "stim seed"),
    (lambda r: r.update(bits_Z="00"), "bit vector"),
])
def test_S4_inconsistent_batches_rejected_even_if_resigned(mutate, why):
    key = b"k" * 32
    r = _honest_batch()
    mutate(r)
    msg = l2mod._check_batch(l2mod._sign(key, r), index=3, key=key, seed=5, batch_size=64)
    assert msg and why in msg, msg


def test_S4_spot_checks_recorded_and_entry_checks_shots(selftest_runs):
    """S4 (b)(d)：主进程随机抽查重算（记录在 reproducibility 里）；entry_problems 核对 shots = batches_used × batch_size
    （auditor W1 式的“失败数不变、shots ×3”伪造现在被语义核对发现）。"""
    rep = selftest_runs["paper"]
    assert len(rep.l2["reproducibility"]["spot_checked_batches"]) == 2
    rec = _body(lb.read_leaderboard(selftest_runs["path"])[0])
    assert lb.entry_problems(rec) == []
    forged = copy.deepcopy(rec)
    forged["l2"]["counts"]["shots"] *= 3
    probs = lb.entry_problems(forged)
    assert any("batches_used" in p for p in probs), probs


# ---------------------------------------------------------------------------
# S8 误拒合法调度（严重）
# ---------------------------------------------------------------------------

def _pipeline_l0(code, spec, rounds=3):
    task = tasks.get_task(PAPER)
    return check_l0(pipeline.circuits_for(spec, code, rounds), code, "both",
                    pipeline._l0_constraints(task, code, rounds, with_distance=False))


def test_S8_auditor_bb72_free_window_schedules_all_pass():
    """auditor s8 (b)：BB72 的 12 个合法自由窗口变体（v2 误拒 10 个），现在全部通过 pipeline 的 L0。"""
    code, specs = H.auditor_bb72_variants(12)
    assert len(specs) == 12
    for i, s in enumerate(specs):
        r = _pipeline_l0(code, s)
        assert r.passed, f"variant {i}: " + r.to_text()[:2000]
        for b in "ZX":
            counts = r.per_basis[b].get("stabilizer_coverage").details["counts"]
            assert set(counts.values()) == {3}


def test_S8_auditor_gross_free_window_schedules_all_pass():
    """auditor s8b：gross 的 3 个自由窗口变体（v2 误拒第 1 个：X 行 5 被数成 6 次）。"""
    code, specs = H.auditor_gross_variants(3)
    for i, s in enumerate(specs):
        r = _pipeline_l0(code, s)
        assert r.passed, f"variant {i}: " + r.to_text()[:2000]


def test_S8_raw_l0_without_ancilla_map_keeps_v2_behaviour():
    """原始电路（不给 generator_ancillas）上计数口径不变：auditor 的第 0 个 BB72 变体仍被数成 6 次。说明修复只作用于
    pipeline 的模板路径（那里每行自己的辅助比特是已知的）。"""
    code, specs = H.auditor_bb72_variants(1)
    task = tasks.get_task(PAPER)
    cons = dataclasses.replace(pipeline._l0_constraints(task, code, 3, with_distance=False), generator_ancillas=None)
    r = check_l0(pipeline.circuits_for(specs[0], code, 3), code, "both", cons)
    assert not r.passed and "measured 6 time(s)" in r.to_text()


@pytest.mark.parametrize("claimed", [2, 4])
def test_S8_own_ancilla_counting_still_rejects_wrong_round_counts(claimed):
    """按自己的辅助比特计数只会让计数变少：声称 2 轮或 4 轮的 3 轮电路都被拒。"""
    code, spec = surface_schedule(3)
    task = tasks.get_task(PAPER)
    r = check_l0(pipeline.circuits_for(spec, code, 3), code, "both",
                 pipeline._l0_constraints(task, code, claimed, with_distance=False))
    assert not r.passed and "stabilizer_coverage" in {c.name.split(":")[1] for c in r.failures}


def test_S8_template_structure_check():
    """模板结构独立核对：每行每轮恰好一次 复位→全部 CNOT→测量；少一个 CNOT 被发现。"""
    code, spec = surface_schedule(3)
    c = pipeline.circuits_for(spec, code, 3)
    for b in "ZX":
        counts = cand.template_round_counts(c[b], code, b)
        assert set(counts["X"]) == {3} and set(counts["Z"]) == {3}
    bad = c["Z"].flattened()
    import stim
    out = stim.Circuit()
    dropped = False
    for inst in bad:
        if inst.name == "CX" and not dropped:
            t = inst.targets_copy()
            out.append("CX", t[2:])
            dropped = True
        else:
            out.append(inst)
    with pytest.raises(ValueError):
        cand.template_round_counts(out, code, "Z")


# ---------------------------------------------------------------------------
# S1 规范化哈希 ⇔ 电路
# ---------------------------------------------------------------------------

def test_S1_200_random_free_schedules_shift_invariant():
    """auditor s1：200 个随机自由调度，每个都做全部 D 个全局平移：调度哈希相同，pipeline 生成的电路也完全相同
    （v2 里 36% 的调度在平移下给出不止一种电路）。"""
    code, _ = surface_schedule(3)
    rng = random.Random(1)
    n = 0
    while n < 200:
        D = rng.randint(6, 10)
        spec = H.random_free_schedule(code, D, rng)
        if spec is None:
            continue
        n += 1
        h0 = spec.hash()
        c0 = lb_hash(pipeline.circuits_for(spec, code, 3))
        for s in range(1, D):
            sp = H.shifted(spec, s)
            assert sp.hash() == h0
            assert lb_hash(pipeline.circuits_for(sp, code, 3)) == c0


def lb_hash(c):
    from evaluators.l2 import circuit_hash
    return circuit_hash(c)


def test_S1_strikis_shifts_give_one_circuit():
    """auditor s1c：Strikis Fig. 12 的 8 个平移在 v2 里给出 2 种电路；pipeline 现在只有 1 种。"""
    pytest.importorskip("baselines.strikis")
    from baselines.bb_code import gross_code
    from baselines.strikis import strikis_fig12
    from schedule_helpers import from_baseline
    code, _ = tasks.build_code(tasks.get_task("gross-sd6-p4e-3"), None)
    spec = from_baseline(strikis_fig12(gross_code())[0])
    hs = {lb_hash(pipeline.circuits_for(H.shifted(spec, s), code, 3)) for s in range(spec.period)}
    assert len(hs) == 1


def test_S1_noncanonical_shift_is_scored_and_written(tmp_path):
    """auditor s1b：提交非规范平移代表时，v2 跑完 L2 后在写榜时抛 ValueError；现在正常打分并写榜，verify 通过。"""
    sub = json.loads((AUDIT / "s1b_schedule_submitted.json").read_text())
    board = tmp_path / "board.jsonl"
    rep = pipeline.evaluate(PAPER, None, sub, seed=101, leaderboard_path=board)
    assert rep.status == "scored" and rep.leaderboard_record is not None, rep.to_text()
    assert lb.verify_leaderboard(board) == []


# ---------------------------------------------------------------------------
# S10 / W2 正式成绩单
# ---------------------------------------------------------------------------

def test_S10_official_path_is_resolved(tmp_path, monkeypatch):
    official = tmp_path / "research" / "leaderboard.jsonl"
    official.parent.mkdir()
    official.write_text("")
    monkeypatch.setattr(lb, "DEFAULT_PATH", official)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "link.jsonl").symlink_to(official)
    os.link(official, tmp_path / "hard.jsonl")
    for p in (None, official, "research/leaderboard.jsonl", "research/../research/leaderboard.jsonl",
              "link.jsonl", "hard.jsonl", str(official)):
        assert lb.is_official_path(p), p
    assert not lb.is_official_path(tmp_path / "other.jsonl")


def test_S10_selftest_via_relative_path_not_written(tmp_path, monkeypatch):
    """auditor s10：相对路径 / 带 .. 的路径不再绕过“正式成绩单只收冻结评估器 + purpose=score”。"""
    official = tmp_path / "research" / "leaderboard.jsonl"
    official.parent.mkdir()
    official.write_text("")
    monkeypatch.setattr(lb, "DEFAULT_PATH", official)
    monkeypatch.chdir(tmp_path)
    _, spec = surface_schedule(3)
    rep = pipeline.evaluate(PAPER, None, spec.to_dict(), seed=3, leaderboard_path="research/../research/leaderboard.jsonl")
    assert rep.leaderboard_record is None
    assert any("never written to the official leaderboard" in r for r in rep.ineligible_reasons)
    assert official.read_text() == ""


def test_W2_verify_on_official_board_checks_purpose_freeze_and_versions(selftest_runs, tmp_path, monkeypatch):
    """W2：verify 对正式成绩单要求 purpose=score、评估器已冻结且哈希等于冻结记录、库版本固定。自检记录（v2 里能经
    S10 写进正式榜且 verify 返回 []）现在被报出来；伪造 evaluator / versions 字段同样被报出来。"""
    p = tmp_path / "board.jsonl"
    p.write_text(selftest_runs["path"].read_text())
    assert lb.verify_leaderboard(p) == []                                  # 临时榜：只做语义核对
    probs = lb.verify_leaderboard(p, official=True)
    assert any("purpose" in x for x in probs) and any("not frozen" in x for x in probs)
    rec = lb.read_leaderboard(p)[0]
    rec = dict(rec, purpose="score", versions=dict(rec["versions"], stim="0.0.0"),
               evaluator=dict(rec["evaluator"], frozen=True, verified=True, hash="f" * 64))
    probs = lb.official_problems(rec)
    assert any("library versions" in x for x in probs)
    assert any("frozen evaluator" in x for x in probs)
    monkeypatch.setattr(lb, "frozen_record", lambda: {"evaluator_hash": "e" * 64})
    assert any("differs from the frozen evaluator hash" in x for x in lb.official_problems(rec))
    good = dict(rec, versions=dict(rec["versions"], **tasks.PINNED_VERSIONS),
                evaluator=dict(rec["evaluator"], hash="e" * 64))
    assert lb.official_problems(good) == []


# ---------------------------------------------------------------------------
# S5 挑种子
# ---------------------------------------------------------------------------

def test_S5_official_task_ignores_caller_seed(tmp_path, monkeypatch):
    """auditor s5：正式（purpose=score）任务的 L2 种子由评估器从 (task_hash, schedule_hash) 派生，调用方的种子被忽略
    并记录在诊断里；两次不同的 seed 给出逐位相同的计数。记录里的种子被改动时语义核对报“seed shopping”。"""
    task = dataclasses.replace(tasks.get_task(PAPER), task_id="test-score-surface", purpose="score")
    monkeypatch.setitem(tasks.TASKS, task.task_id, task)
    _, spec = surface_schedule(3)
    board = tmp_path / "board.jsonl"
    a = pipeline._evaluate_task(task, None, spec.to_dict(), seed=1000, leaderboard_path=board)
    b = pipeline._evaluate_task(task, None, spec.to_dict(), seed=1011, submit=False)
    want = pipeline.derive_seed(task.hash(), a.schedule_hash, "l2")
    assert a.seed == b.seed == want
    assert a.l2["counts"] == b.l2["counts"]
    assert any("ignored" in d for d in a.diagnostics)
    rec = _body(a.leaderboard_record)
    assert lb.entry_problems(rec) == []
    assert any("seed" in p for p in lb.entry_problems(dict(rec, seed=1000)))


# ---------------------------------------------------------------------------
# F7 字节码缓存前缀
# ---------------------------------------------------------------------------

def test_F7_pycache_prefix_refused(monkeypatch):
    monkeypatch.setattr(sys, "pycache_prefix", "/tmp/somewhere")
    assert any("pycache_prefix" in p for p in pipeline.runtime_integrity())
    _, spec = surface_schedule(3)
    with pytest.raises(RuntimeError, match="runtime integrity"):
        pipeline.screen(PAPER, None, spec.to_dict())
    assert not pipeline.environment_check()["ok"]


def test_F7_module_loaded_from_outside_refused(monkeypatch, tmp_path):
    fake = types.ModuleType("evaluators.fake")
    fake.__file__ = str(tmp_path / "evil.py")
    monkeypatch.setitem(sys.modules, "evaluators.fake", fake)
    assert any("evaluators.fake" in p for p in pipeline.runtime_integrity())
    m = sys.modules["evaluators.stats"]
    monkeypatch.setattr(m, "__cached__", str(tmp_path / "stats.cpython-312.pyc"))
    assert any("byte-code cache" in p for p in pipeline.runtime_integrity())


def test_F7_environment_variable_in_subprocess(tmp_path):
    """auditor s6 F7 的入口：带 PYTHONPYCACHEPREFIX 启动的进程，evaluate / screen 拒绝运行。"""
    code = ("import sys; sys.path[:0] = ['.', 'tests']\n"
            "from evaluators import pipeline\n"
            "from schedule_helpers import surface_schedule\n"
            "print('PROBLEMS', len(pipeline.runtime_integrity()))\n"
            "try:\n    pipeline.screen('selftest-surface-d3-sd6-paper', None, surface_schedule(3)[1].to_dict())\n"
            "except RuntimeError as e:\n    print('REFUSED', str(e)[:80])\n")
    env = dict(os.environ, PYTHONPYCACHEPREFIX=str(tmp_path / "pfx"))
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    assert "REFUSED" in r.stdout, r.stdout + r.stderr
    assert "PROBLEMS 0" not in r.stdout


def test_runtime_integrity_clean_in_normal_process():
    assert pipeline.runtime_integrity() == []


# ---------------------------------------------------------------------------
# R2 reproduce_entry / entry_problems 比较 diff 任务的 components
# ---------------------------------------------------------------------------

def test_R2_diff_component_forgery_detected(selftest_runs):
    """auditor s3 R2：只伪造 components[r1].counts 与 per_round（顶层 counts 不动）。v2 里 entry_problems 与
    reproduce_entry 都返回 []；现在两者都发现。"""
    from evaluators.l2 import diff_per_round
    rec = next(r for r in lb.read_leaderboard(selftest_runs["path"]) if r["task_id"] == DIFF)
    f2 = copy.deepcopy(_body(rec))
    l2 = f2["l2"]
    r1, r2 = l2["inputs"]["diff_rounds"]
    c1, c2 = l2["components"][str(r1)]["counts"], l2["components"][str(r2)]["counts"]
    c1["shots"] = int(c1["shots"] * 0.80)
    k_obs = l2["joint"]["num_observables"]
    kk = {"P_Z": k_obs["Z"], "P_X": k_obs["X"], "P_any": k_obs["Z"] + k_obs["X"]}
    for key, ck in (("P_Z", "fail_Z"), ("P_X", "fail_X"), ("P_any", "fail_any")):
        d = diff_per_round(c1[ck], c1["shots"], r1, c2[ck], c2["shots"], r2, num_observables=kk[key],
                           likelihood_factor=l2["inputs"].get("likelihood_factor", 1000.0))
        l2["per_round"][key].update(best=d["best"], low=d["low"], high=d["high"], diff=d)
    f2["score"]["per_round_P_any"] = {k: l2["per_round"]["P_any"][k] for k in ("best", "low", "high")}
    f2["score"]["per_round_per_logical"] = f2["score"]["per_round_P_any"]["best"] / f2["score"]["k"]
    assert lb.entry_problems(f2), "forged diff components not detected by entry_problems"
    out = lb.reproduce_entry(f2)
    assert any("component counts differ" in x for x in out), out


# ---------------------------------------------------------------------------
# numpy 整数（auditor v2 S2 (a)(b)）
# ---------------------------------------------------------------------------

def test_numpy_integers_accepted_and_normalised():
    code, spec = surface_schedule(3)
    d = spec.to_dict()
    nd = {"format": d["format"], "period": np.int64(d["period"]),
          "x_checks": [{"prep": np.int32(c["prep"]), "meas": np.int64(c["meas"]),
                        "cnots": [[np.int64(a), np.int16(t)] for a, t in c["cnots"]]} for c in d["x_checks"]],
          "z_checks": [{"prep": np.uint8(c["prep"]), "meas": np.int64(c["meas"]),
                        "cnots": [np.array([a, t]) for a, t in c["cnots"]]} for c in d["z_checks"]]}
    s = cand.parse_schedule(nd)
    assert s.hash() == spec.hash()
    assert all(type(x) is int for c in s.x_checks + s.z_checks for x in (c.prep, c.meas, *sum(c.cnots, ())))
    assert type(s.period) is int
    with pytest.raises(cand.ScheduleError):
        cand.parse_schedule(dict(d, period=np.bool_(True)))


def test_schedule_object_goes_through_strict_parsing():
    """S2 (b)：直接传 ScheduleSpec 对象时 period 上限、时间步范围同样生效。"""
    code, spec = surface_schedule(3)
    with pytest.raises(cand.ScheduleError):
        cand.parse_schedule(dataclasses.replace(spec, period=200))
    bad = dataclasses.replace(spec, x_checks=(dataclasses.replace(spec.x_checks[0], prep=17),) + spec.x_checks[1:])
    with pytest.raises(cand.ScheduleError):
        cand.parse_schedule(bad)
