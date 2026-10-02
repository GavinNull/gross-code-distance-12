"""evaluators/leaderboard.py（评估器 v2）：只有 pipeline 能写；哈希链 + 外部锚点；语义核对。

全部写临时路径；最后确认真正的 research/leaderboard.jsonl 没被碰过。auditor G1 LB1–LB7 的回归测试也在这里
（LB1–LB4、LB7 主要在 test_pipeline.py / 本文件的语义核对里）。
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from evaluators import leaderboard as lb
from evaluators import pipeline

ROOT = Path(__file__).resolve().parent.parent


def _real_board_digest():
    p = lb.DEFAULT_PATH
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


_REAL_BEFORE = _real_board_digest()


def _body(rec: dict) -> dict:
    """去掉系统字段，得到 pipeline 交给 _append 的记录。"""
    return {k: v for k, v in rec.items() if k not in lb.SYSTEM_FIELDS}


@pytest.fixture()
def board(selftest_runs, tmp_path):
    p = tmp_path / "board.jsonl"
    shutil.copy(selftest_runs["path"], p)
    return p


def test_pipeline_records_are_complete_and_chain_verifies(selftest_runs):
    recs = lb.read_leaderboard(selftest_runs["path"])
    assert [r["seq"] for r in recs] == [0, 1]
    assert recs[0]["prev_hash"] == lb.GENESIS and recs[1]["prev_hash"] == recs[0]["entry_hash"]
    assert lb.verify_leaderboard(selftest_runs["path"]) == []
    r = recs[0]
    for f in ("task_id", "task_hash", "schedule", "schedule_hash", "circuit_hashes", "rounds_verified", "seed",
              "score", "l0", "l2", "time", "evaluator", "git", "versions", "attempt"):
        assert f in r, f
    assert r["task_id"] == "selftest-surface-d3-sd6-paper" and r["rounds"] == 3
    assert r["rounds_verified"] == {"3": {"Z": [3], "X": [3]}}
    assert r["versions"]["stim"] and r["evaluator"]["hash"]
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "freeze_evaluator.py"), "hash"],
                         capture_output=True, text=True, check=True).stdout.strip()
    assert r["evaluator"]["hash"] == out
    assert min(r["l2"]["counts"]["fail_Z"], r["l2"]["counts"]["fail_X"]) >= 1000


def test_LB2_no_public_writer_and_credential_required(selftest_runs, tmp_path):
    rec = _body(lb.read_leaderboard(selftest_runs["path"])[0])
    with pytest.raises(PermissionError):
        lb.submit(rec, tmp_path / "x.jsonl")
    with pytest.raises(PermissionError):
        lb.build_entry("x", code=None, l2=None, l0_report={"passed": True}, distance_upper_bound=99)
    with pytest.raises(PermissionError):
        lb._append(rec, tmp_path / "x.jsonl", object())
    assert not (tmp_path / "x.jsonl").exists()


@pytest.mark.parametrize("mutate,keyword", [
    # LB2：伪造 L0 / L2 字典
    (lambda r: r["l0"]["r=3 (with distance)"].update(passed=False), "L0"),
    (lambda r: r["l2"]["per_round"]["P_any"].update(best=1e-9), "per-round"),
    (lambda r: r["score"]["per_round_P_any"].update(best=1e-9), "score"),
    (lambda r: r["l2"]["counts"].update(fail_Z=5, fail_X=5, fail_any=8), "fewer than 1000"),
    (lambda r: r.update(distance_upper_bound=2), "distance"),
    # LB1：轮数造假
    (lambda r: r.update(rounds=30), "rounds"),
    (lambda r: r["l2"]["inputs"].update(rounds=30), "rounds"),
    (lambda r: r.update(rounds_verified={"3": {"Z": [1], "X": [1]}}), "round count"),
    # LB3：非打分噪声模型
    (lambda r: r.update(noise_model="gross_sd6"), "noise_model"),
    (lambda r: r["l2"]["inputs"].update(noise_model="gross_sd6"), "noise_model"),
    # LB4：schedule_hash 与采样电路不一致
    (lambda r: r.update(schedule_hash="deadbeef" * 8), "schedule_hash"),
    (lambda r: r["schedule"]["z_checks"][0]["cnots"].reverse() or r["schedule"]["z_checks"][0]["cnots"][0].__setitem__(1, 2), ""),
    (lambda r: r["l2"]["circuit"].update(candidate_hash="0" * 64), "sampled"),
    # LB7：不同 p / 解码器 / 码 / 任务混榜
    (lambda r: r.update(p=0.001), "p="),
    (lambda r: r["l2"]["decoder"].update(name="bposd"), "decoder"),
    (lambda r: r["code"].update(checks_sha256="0" * 64), "code"),
    (lambda r: r.update(task_id="gross-sd6-p4e-3"), ""),
    (lambda r: r.update(task_hash="0" * 64), "task_hash"),
    (lambda r: r.update(task_id="no-such-task"), "unknown task"),
])
def test_forged_records_rejected_even_with_credential(selftest_runs, tmp_path, mutate, keyword):
    """即使拿到凭证（同进程恶意代码），伪造 / 不一致的记录也写不进去；事后 verify 也能发现。"""
    rec = json.loads(json.dumps(_body(lb.read_leaderboard(selftest_runs["path"])[0])))
    mutate(rec)
    probs = lb.entry_problems(rec)
    assert probs, "mutation not detected"
    if keyword:
        assert any(keyword.lower() in p.lower() for p in probs), probs
    with pytest.raises(ValueError, match="inconsistent record"):
        lb._append(rec, tmp_path / "x.jsonl", pipeline._CREDENTIAL)


def test_system_fields_cannot_be_supplied(selftest_runs, tmp_path):
    rec = _body(lb.read_leaderboard(selftest_runs["path"])[0])
    for f in ("evaluator", "entry_hash", "seq", "attempt"):
        with pytest.raises(ValueError, match="filled in by the leaderboard"):
            lb._append(dict(rec, **{f: "forged"}), tmp_path / "x.jsonl", pipeline._CREDENTIAL)


def test_tampering_is_detected(board):
    lines = board.read_text().splitlines()
    rec = json.loads(lines[1])
    rec["score"]["per_round_P_any"]["best"] = 1e-9
    board.write_text("\n".join([lines[0], json.dumps(rec)]) + "\n")
    probs = lb.verify_leaderboard(board)
    assert any("entry_hash mismatch" in p for p in probs) and any("score" in p for p in probs)


def test_LB5_tail_deletion_detected_with_anchor(board):
    anchor = lb.anchor_line(board)
    n, h = map(str.strip, anchor.split("lines=")[1].split("head="))
    assert lb.verify_leaderboard(board, anchors=[(int(n), h)]) == []
    lines = board.read_text().splitlines()
    board.write_text(lines[0] + "\n")                               # 删掉末行：链本身仍然完整
    assert [p for p in lb.verify_leaderboard(board) if "anchor" in p] == []
    probs = lb.verify_leaderboard(board, anchors=[(int(n), h)])
    assert any("tail deleted" in p for p in probs), probs


def test_LB6_rewrite_and_rehash_whole_chain_detected_with_anchor(board):
    n, h = lb.chain_head(board)
    recs = lb.read_leaderboard(board)
    recs[0]["candidate_id"] = "rewritten"
    prev = lb.GENESIS
    out = []
    for r in recs:                                                   # 整条链重算
        r["prev_hash"] = prev
        r["entry_hash"] = lb.entry_hash(r)
        prev = r["entry_hash"]
        out.append(lb._canonical(r))
    board.write_text("\n".join(out) + "\n")
    assert lb.verify_leaderboard(board) == []                        # 没有锚点时发现不了（README 已说明）
    probs = lb.verify_leaderboard(board, anchors=[(n, h)])
    assert any("history rewritten" in p for p in probs), probs


def test_anchor_regex_matches_commit_message_format(board):
    line = lb.anchor_line(board)
    m = lb.ANCHOR_RE.search(f"some commit\n\n{line}\n")
    assert m and int(m.group(1)) == 2


def test_truncated_file_refuses_append(selftest_runs, tmp_path):
    p = tmp_path / "trunc.jsonl"
    p.write_text(selftest_runs["path"].read_text()[:-10])
    rec = _body(lb.read_leaderboard(selftest_runs["path"])[0])
    with pytest.raises(RuntimeError):
        lb._append(rec, p, pipeline._CREDENTIAL)


_WORKER = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from evaluators import leaderboard as lb, pipeline
rec = json.load(open(sys.argv[2]))
for i in range(int(sys.argv[5])):
    lb._append(dict(rec, candidate_id=f"{sys.argv[4]}-{i}"), sys.argv[3], pipeline._CREDENTIAL)
"""


def test_concurrent_appends_do_not_corrupt(selftest_runs, tmp_path):
    path = tmp_path / "board.jsonl"
    ef = tmp_path / "rec.json"
    ef.write_text(json.dumps(_body(lb.read_leaderboard(selftest_runs["path"])[0])))
    nproc, per = 3, 3
    procs = [subprocess.Popen([sys.executable, "-c", _WORKER, str(ROOT), str(ef), str(path), f"w{j}", str(per)])
             for j in range(nproc)]
    for pr in procs:
        assert pr.wait(timeout=600) == 0
    recs = lb.read_leaderboard(path)
    assert len(recs) == nproc * per and [r["seq"] for r in recs] == list(range(nproc * per))
    assert sorted(r["attempt"] for r in recs) == list(range(nproc * per))   # 同一调度：attempt 计数
    assert lb.verify_leaderboard(path) == []
    t = lb.table("selftest-surface-d3-sd6-paper", path)
    assert len(t) == 1 and t[0]["submissions"] == nproc * per and t[0]["seq"] == 0   # 只按第一次排名


def test_LB7_tables_are_per_task(selftest_runs):
    a = lb.table("selftest-surface-d3-sd6-paper", selftest_runs["path"])
    b = lb.table("selftest-surface-d3-sd6-diff", selftest_runs["path"])
    assert len(a) == 1 and len(b) == 1 and a[0]["seq"] != b[0]["seq"]
    assert lb.table("gross-sd6-p4e-3", selftest_runs["path"]) == []


def test_real_leaderboard_untouched():
    assert _real_board_digest() == _REAL_BEFORE
