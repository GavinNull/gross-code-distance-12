"""成绩单：research/leaderboard.jsonl 的唯一写入口（CLAUDE.md 铁律 1）。

    from evaluators.leaderboard import build_entry, submit, verify_leaderboard
    entry = build_entry("cand-0007", code=code, circuits={"Z": cz, "X": cx}, l0_report=report,
                        distance_upper_bound=report.d_circ, l2=l2_result)
    line = submit(entry)                      # 默认写 research/leaderboard.jsonl
    problems = verify_leaderboard()           # [] = 完整

规则：
  - 只追加：文件以 "a" 模式打开，从不重写已有行；submit 在排他文件锁（fcntl.flock，锁住文件本身）内
    读最后一行、追加新行、fsync，所以多个进程并发写也不会交错或丢行。
  - 哈希链：每行带 prev_hash（上一行的 entry_hash，第一行为 64 个 0）和 entry_hash
    （本行除 entry_hash 外所有字段的规范 JSON 的 sha256）。改写或删除任何一行都会被 verify_leaderboard 发现。
  - 下列字段由 submit 填写，调用方不得提供：time、evaluator（哈希 + 是否冻结）、git、versions、
    prev_hash、entry_hash。评估器哈希用 scripts/freeze_evaluator.py 里的同一算法（直接调用它的函数）。
  - L0 未通过的候选拒绝上榜；L2 必须是 X/Z 联合采样的结果（approximation 为 None）。
  - 测试一律传入临时路径，不得写真正的 research/leaderboard.jsonl。
"""
from __future__ import annotations

import datetime as _dt
import fcntl
import hashlib
import importlib.util
import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "research" / "leaderboard.jsonl"
GENESIS = "0" * 64

REQUIRED_FIELDS = ("candidate_id", "code", "schedule_hash", "noise_model", "p", "rounds", "boundary",
                   "l0", "distance_upper_bound", "l2")
SYSTEM_FIELDS = ("time", "evaluator", "git", "versions", "prev_hash", "entry_hash")

__all__ = [
    "DEFAULT_PATH",
    "REQUIRED_FIELDS",
    "SYSTEM_FIELDS",
    "build_entry",
    "entry_hash",
    "evaluator_hash",
    "git_info",
    "read_leaderboard",
    "submit",
    "verify_leaderboard",
]


# ---------------------------------------------------------------------------
# 元数据
# ---------------------------------------------------------------------------

def _freeze_module():
    path = ROOT / "scripts" / "freeze_evaluator.py"
    spec = importlib.util.spec_from_file_location("_freeze_evaluator", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def evaluator_hash() -> dict:
    """{"hash": scripts/freeze_evaluator.py 的 combined_hash, "frozen": evaluators/FROZEN 是否存在,
    "frozen_hash": FROZEN 文件记录的哈希（未冻结为 None）}"""
    fm = _freeze_module()
    h = fm.combined_hash(fm.file_hashes())
    frozen_hash = None
    if fm.FROZEN.exists():
        for line in fm.FROZEN.read_text().splitlines():
            if line.startswith("evaluator_hash="):
                frozen_hash = line.split("=", 1)[1].strip()
    return {"hash": h, "frozen": fm.FROZEN.exists(), "frozen_hash": frozen_hash,
            "matches_frozen": (frozen_hash == h) if frozen_hash else None}


def git_info() -> dict:
    def run(*args):
        try:
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                                  timeout=20).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    commit = run("rev-parse", "HEAD") or None
    status = run("status", "--porcelain", "--", "evaluators")
    return {"commit": commit, "evaluators_dirty": bool(status) if commit else None}


def _versions() -> dict:
    from evaluators.l2 import library_versions
    return library_versions()


# ---------------------------------------------------------------------------
# 条目
# ---------------------------------------------------------------------------

def _l0_summary(l0) -> dict:
    if l0 is None:
        raise ValueError("an L0 report is required")
    d = l0.to_dict() if hasattr(l0, "to_dict") else dict(l0)
    checks = d.get("checks", [])
    summ = {"passed": bool(d.get("passed")), "basis": d.get("basis"), "d_circ": d.get("d_circ"),
            "checks": {c.get("name"): c.get("status") for c in checks if isinstance(c, Mapping)}}
    per = d.get("per_basis") or {}
    if per:
        summ["per_basis_d_circ"] = {b: (r.get("d_circ") if isinstance(r, Mapping) else None) for b, r in per.items()}
    return summ


_SCORE_DEFINITION = {
    "paper": "per_round = 1-(1-P)^(1/rounds) of one run; perfect code-state init and readout (arXiv:2308.07915 §6); "
             "boundary rounds included (pipelined circuits keep their fill/drain data idle noise)",
    "noisy": "per_round = 1-(1-P)^(1/rounds) of one run; noisy data reset and readout (project-internal)",
    "flat": "per_round = 1-(1-P)^(1/rounds) of one run; paper + data-qubit noise before the first / after the last "
            "two-qubit gate removed (auditor E-003 trim)",
    "diff": "per_round = bulk per-round rate from two runs (rounds r1 < r2), boundary cancels: "
            "eps = (1-exp((log(1-cP2)-log(1-cP1))/(r2-r1)))/c, c = 2^K/(2^K-1)",
}


def _boundary_detail(l2d: Mapping) -> dict:
    """成绩用的边界口径（README §7.2）。不同口径的分数不可直接比较。"""
    inp = l2d["inputs"]
    b = inp["boundary"]
    out = {"boundary": b, "score_field": "l2.per_round", "definition": _SCORE_DEFINITION.get(b, "unknown")}
    if b == "diff":
        out.update(diff_rounds=inp.get("diff_rounds"), inner_boundary=inp.get("diff_inner_boundary"))
    return out


def build_entry(candidate_id: str, *, code, l2, l0_report, distance_upper_bound,
                circuits: Mapping | None = None, schedule_hash: str | None = None,
                extra: Mapping | None = None) -> dict:
    """由评估器的输出组装一条成绩（不写文件）。

    code: CSSCode；l2: L2Result（或其 to_dict()）；l0_report: L0Report（或 to_dict()）；
    distance_upper_bound: 距离上界（int 或 JSON 可序列化的 dict，例如独立距离模块的报告）；
    circuits: 无噪声候选电路 {"Z","X"}（用来算调度哈希），或直接给 schedule_hash。
    """
    from evaluators.l2 import circuit_hash
    l2d = l2.to_dict() if hasattr(l2, "to_dict") else dict(l2)
    if schedule_hash is None:
        if circuits is None:
            raise ValueError("give circuits or schedule_hash")
        schedule_hash = circuit_hash(circuits)
    inp = l2d["inputs"]
    return {
        "candidate_id": str(candidate_id),
        "code": {"name": getattr(code, "name", ""), "n": int(code.n), "k": int(code.k),
                 "HX_rows": int(code.HX.shape[0]), "HZ_rows": int(code.HZ.shape[0]),
                 "checks_sha256": hashlib.sha256(code.HX.tobytes() + b"|" + code.HZ.tobytes()
                                                 + repr((code.HX.shape, code.HZ.shape)).encode()).hexdigest()},
        "schedule_hash": schedule_hash,
        "noise_model": inp["noise_model"],
        "p": inp["p"],
        "rounds": inp["rounds"],
        "boundary": inp["boundary"],
        "boundary_detail": _boundary_detail(l2d),
        "l0": _l0_summary(l0_report),
        "distance_upper_bound": distance_upper_bound,
        "l2": l2d,
        "extra": dict(extra or {}),
    }


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_json_default)


def _json_default(o):
    try:
        import numpy as np
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
    except ImportError:  # pragma: no cover
        pass
    raise TypeError(f"not JSON serialisable: {type(o)}")


def entry_hash(record: Mapping) -> str:
    body = {k: v for k, v in record.items() if k != "entry_hash"}
    return hashlib.sha256(_canonical(body).encode()).hexdigest()


def _validate(entry: Mapping) -> None:
    missing = [f for f in REQUIRED_FIELDS if f not in entry]
    if missing:
        raise ValueError(f"leaderboard entry is missing fields {missing}")
    reserved = [f for f in SYSTEM_FIELDS if f in entry]
    if reserved:
        raise ValueError(f"fields {reserved} are filled in by submit() and must not be supplied")
    if not entry["l0"].get("passed"):
        raise ValueError("L0 did not pass; refusing to put the candidate on the leaderboard")
    l2 = entry["l2"]
    joint = l2.get("joint", {}) if isinstance(l2, Mapping) else {}
    if joint.get("approximation") is not None:
        raise ValueError("L2 result is an approximation; the leaderboard only takes joint X/Z sampling")
    for key in ("P_Z", "P_X", "P_any"):
        if key not in l2.get("rates", {}):
            raise ValueError(f"L2 result lacks {key}")


def _last_line(f) -> str | None:
    f.seek(0)
    data = f.read()
    if not data:
        return None
    if not data.endswith("\n"):
        raise RuntimeError("leaderboard file does not end with a newline (possibly corrupted); refusing to append")
    return data.rstrip("\n").rsplit("\n", 1)[-1]


def submit(entry: Mapping, path: str | os.PathLike | None = None) -> dict:
    """在排他锁内把 entry 追加为一行。返回实际写入的记录（含 time / evaluator / git / versions / 哈希）。"""
    _validate(entry)
    path = Path(path) if path is not None else DEFAULT_PATH
    record = dict(entry)
    record["time"] = _dt.datetime.now(_dt.UTC).isoformat()
    record["evaluator"] = evaluator_hash()
    record["git"] = git_info()
    record["versions"] = _versions()
    record = json.loads(_canonical(record))   # 规范化（numpy 类型、元组、整数键），保证读回后哈希一致
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            last = _last_line(f)
            if last is None:
                prev = GENESIS
            else:
                try:
                    prev = json.loads(last)["entry_hash"]
                except (json.JSONDecodeError, KeyError) as e:
                    raise RuntimeError(f"last leaderboard line is not a valid record: {e}") from e
            record["prev_hash"] = prev
            record["entry_hash"] = entry_hash(record)
            line = _canonical(record) + "\n"
            f.seek(0, os.SEEK_END)
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return record


def read_leaderboard(path: str | os.PathLike | None = None) -> list[dict]:
    path = Path(path) if path is not None else DEFAULT_PATH
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            text = f.read()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return [json.loads(x) for x in text.splitlines() if x.strip()]


def verify_leaderboard(path: str | os.PathLike | None = None) -> list[str]:
    """检查每行是合法 JSON、entry_hash 正确、prev_hash 链连续。返回问题列表（空 = 完整）。"""
    path = Path(path) if path is not None else DEFAULT_PATH
    if not path.exists():
        return []
    problems = []
    text = path.read_text(encoding="utf-8")
    if text and not text.endswith("\n"):
        problems.append("file does not end with a newline")
    prev = GENESIS
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            problems.append(f"line {i}: empty")
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            problems.append(f"line {i}: invalid JSON ({e})")
            prev = None
            continue
        if rec.get("prev_hash") != prev:
            problems.append(f"line {i}: prev_hash does not match the previous entry (chain broken)")
        if rec.get("entry_hash") != entry_hash(rec):
            problems.append(f"line {i}: entry_hash mismatch (line modified)")
        prev = rec.get("entry_hash")
    return problems
