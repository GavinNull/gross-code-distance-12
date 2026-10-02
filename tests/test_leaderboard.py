"""evaluators/leaderboard.py 的测试。全部写临时路径；最后确认真正的 research/leaderboard.jsonl 没被碰过。"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from evaluators import leaderboard as lb
from evaluators.codes import rotated_surface_code_from_stim
from evaluators.l2 import DecoderConfig, StopRule, sample_l2

ROOT = Path(__file__).resolve().parent.parent


def _real_board_digest():
    p = lb.DEFAULT_PATH
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


_REAL_BEFORE = _real_board_digest()

FAKE_L0 = {"passed": True, "basis": "both", "d_circ": 3,
           "checks": [{"name": "determinism", "status": "pass"}, {"name": "circuit_distance", "status": "pass"}],
           "per_basis": {"Z": {"d_circ": 3}, "X": {"d_circ": 3}}}


@pytest.fixture(scope="module")
def entry():
    code, data, cz = rotated_surface_code_from_stim(3, "Z")
    _, _, cx = rotated_surface_code_from_stim(3, "X")
    circs = {"Z": cz, "X": cx}
    l2 = sample_l2(code, circs, data, p=0.005, rounds=3, decoder=DecoderConfig("pymatching"), seed=1,
                   stop=StopRule(max_shots=2000, batch_size=1000), num_workers=1)
    return lb.build_entry("surface-d3-test", code=code, circuits=circs, l0_report=FAKE_L0,
                          distance_upper_bound=3, l2=l2)


def test_submit_appends_with_hashes(tmp_path, entry):
    path = tmp_path / "board.jsonl"
    r1 = lb.submit(entry, path)
    r2 = lb.submit(dict(entry, candidate_id="second"), path)
    lines = path.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == r1 and json.loads(lines[1]) == r2
    assert r1["prev_hash"] == lb.GENESIS and r2["prev_hash"] == r1["entry_hash"]
    assert lb.verify_leaderboard(path) == []
    # 必备字段
    for f in lb.REQUIRED_FIELDS + lb.SYSTEM_FIELDS:
        assert f in r1, f
    assert r1["boundary"] == "paper" and r1["rounds"] == 3 and r1["p"] == 0.005
    assert r1["boundary_detail"]["boundary"] == "paper" and "1-(1-P)" in r1["boundary_detail"]["definition"]
    assert r1["l2"]["rates"]["P_any"]["best"] >= r1["l2"]["rates"]["P_Z"]["best"]
    assert r1["versions"]["stim"] and r1["versions"]["ldpc"] and r1["versions"]["pymatching"]
    assert len(r1["schedule_hash"]) == 64
    # 评估器哈希与 scripts/freeze_evaluator.py hash 一致
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "freeze_evaluator.py"), "hash"],
                         capture_output=True, text=True, check=True).stdout.strip()
    assert r1["evaluator"]["hash"] == out
    assert "commit" in r1["git"]


def test_tampering_is_detected(tmp_path, entry):
    path = tmp_path / "board.jsonl"
    for i in range(3):
        lb.submit(dict(entry, candidate_id=f"c{i}"), path)
    lines = path.read_text().splitlines()
    rec = json.loads(lines[1])
    rec["l2"]["rates"]["P_any"]["best"] = 1e-9
    bad = tmp_path / "bad.jsonl"
    bad.write_text("\n".join([lines[0], json.dumps(rec), lines[2]]) + "\n")
    assert any("entry_hash mismatch" in p for p in lb.verify_leaderboard(bad))
    deleted = tmp_path / "deleted.jsonl"
    deleted.write_text("\n".join([lines[0], lines[2]]) + "\n")
    assert any("chain broken" in p for p in lb.verify_leaderboard(deleted))
    # 截断的文件：拒绝继续追加
    trunc = tmp_path / "trunc.jsonl"
    trunc.write_text(path.read_text()[:-10])
    with pytest.raises(RuntimeError):
        lb.submit(entry, trunc)


def test_rejects_bad_entries(tmp_path, entry):
    path = tmp_path / "board.jsonl"
    with pytest.raises(ValueError, match="filled in by submit"):
        lb.submit(dict(entry, entry_hash="x"), path)
    with pytest.raises(ValueError, match="filled in by submit"):
        lb.submit(dict(entry, evaluator={"hash": "forged"}), path)
    with pytest.raises(ValueError, match="L0 did not pass"):
        lb.submit(dict(entry, l0=dict(entry["l0"], passed=False)), path)
    l2 = json.loads(json.dumps(entry["l2"]))
    l2["joint"]["approximation"] = "independent"
    with pytest.raises(ValueError, match="approximation"):
        lb.submit(dict(entry, l2=l2), path)
    missing = {k: v for k, v in entry.items() if k != "schedule_hash"}
    with pytest.raises(ValueError, match="missing"):
        lb.submit(missing, path)
    assert not path.exists() or path.read_text() == ""


_WORKER = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from evaluators import leaderboard as lb
entry = json.load(open(sys.argv[2]))
for i in range(int(sys.argv[5])):
    lb.submit(dict(entry, candidate_id=f"{sys.argv[4]}-{i}"), sys.argv[3])
"""


def test_concurrent_submits_do_not_corrupt(tmp_path, entry):
    path = tmp_path / "board.jsonl"
    ef = tmp_path / "entry.json"
    ef.write_text(json.dumps(entry))
    nproc, per = 6, 5
    procs = [subprocess.Popen([sys.executable, "-c", _WORKER, str(ROOT), str(ef), str(path), f"w{j}", str(per)])
             for j in range(nproc)]
    for pr in procs:
        assert pr.wait(timeout=300) == 0
    recs = lb.read_leaderboard(path)
    assert len(recs) == nproc * per
    assert len({r["candidate_id"] for r in recs}) == nproc * per
    assert lb.verify_leaderboard(path) == []


def test_real_leaderboard_untouched():
    assert _real_board_digest() == _REAL_BEFORE


def test_diff_boundary_is_recorded(tmp_path):
    """boundary="diff" 的成绩记录口径、两个轮数和子采样口径。"""
    code, data, _ = rotated_surface_code_from_stim(3, "Z")
    circ = lambda b, r: rotated_surface_code_from_stim(3, b, r)[2]   # noqa: E731
    l2 = sample_l2(code, circ, data, p=0.006, rounds=6, boundary="diff", diff_rounds=3,
                   decoder=DecoderConfig("pymatching"), seed=2, stop=StopRule(max_shots=4000, batch_size=2000),
                   num_workers=1)
    e = lb.build_entry("surface-d3-diff", code=code, circuits={b: circ(b, 6) for b in "ZX"}, l0_report=FAKE_L0,
                       distance_upper_bound=3, l2=l2)
    rec = lb.submit(e, tmp_path / "board.jsonl")
    assert rec["boundary"] == "diff" and rec["rounds"] == 6
    assert rec["boundary_detail"]["diff_rounds"] == [3, 6]
    assert rec["boundary_detail"]["inner_boundary"] == "paper"
    assert rec["l2"]["per_round"]["P_any"]["diff"]["r1"] == 3
    assert lb.verify_leaderboard(tmp_path / "board.jsonl") == []
