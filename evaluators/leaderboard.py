"""成绩单：research/leaderboard.jsonl（CLAUDE.md 铁律 1）。评估器 v2（2026-10-02）。

**只有 evaluators.pipeline.evaluate 能写成绩单**（修复 auditor G1 LB1–LB7）：
  - 没有公开的写入函数。`_append(record, path, credential)` 只接受 pipeline 模块私有的凭证对象，记录由 pipeline 从
    自己的计算结果组装（候选只提交调度 JSON）；调用方不能传 L0 / L2 字典进来。旧接口 `submit` / `build_entry`
    保留为直接报错的桩，提示改用 pipeline。
  - 每条记录带 task_id 与 task_hash（任务注册表 evaluators/tasks.py），`rounds` 是任务的轮数并由 L0 实测核对
    （rounds_verified），schedule_hash 是评估器对规范化调度算的哈希，记录里同时保存规范化调度本身和每个轮数的
    电路哈希，所以任何人都能从记录重新生成电路核对，或用 `reproduce_entry` 按同一种子逐位复算 L2。
  - `_append` 在写入前、`verify_leaderboard` 在事后都做语义核对（`entry_problems`）：任务存在且未被改动、
    噪声 / p / 轮数 / 边界 / 解码器 / 停止规则与任务一致、调度哈希与电路哈希可由记录里的调度重算、L0 全部通过、
    每个 sector 失败数 >= 1000（小样本不上榜）、分数等于 L2 的每轮值。
  - 不同任务不混榜：`table(task_id)` 只看一个任务；同一调度多次提交只按**第一次**的结果排名（attempt 计数记在
    记录里，防止换种子挑结果，auditor G1 L2-4）。

只追加 + 哈希链：
  - `open(..., "a+")` + `fcntl.flock` 排他锁；锁内读最后一行取 prev_hash 与 seq，追加，fsync。
  - entry_hash = 除自身外所有字段规范 JSON 的 sha256；prev_hash = 上一行的 entry_hash（首行 64 个 0）；seq 从 0 连续。
  - 哈希链能发现中间行被改 / 删，但**发现不了删掉末尾若干行，或改了之后把整条链重算**（LB5、LB6）。这两种只能靠
    外部锚点发现：每次写榜之后把 `anchor_line()` 的输出（行数 + 链尾哈希）写进 git commit message
    （`git commit -m "... leaderboard-anchor: lines=N head=<hash>"`）。`verify_leaderboard()` 对默认路径会自动
    读取 git 历史里的全部锚点并核对：锚定过的第 N 行必须仍然存在且哈希不变。也可以传 anchors=[(N, hash)]。
"""
from __future__ import annotations

import datetime as _dt
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "research" / "leaderboard.jsonl"
GENESIS = "0" * 64
SYSTEM_FIELDS = ("seq", "attempt", "time", "evaluator", "git", "versions", "prev_hash", "entry_hash")
ANCHOR_RE = re.compile(r"leaderboard-anchor:\s*lines=(\d+)\s+head=([0-9a-f]{64})")

__all__ = [
    "DEFAULT_PATH",
    "anchor_line",
    "chain_head",
    "entry_hash",
    "entry_problems",
    "evaluator_hash",
    "git_anchors",
    "git_info",
    "read_leaderboard",
    "reproduce_entry",
    "table",
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
    """{"hash", "frozen", "frozen_hash", "matches_frozen", "verified", "problems"}（scripts/freeze_evaluator.py）。"""
    v = _freeze_module().verify_tree()
    fh = v["frozen_hash"]
    return {"hash": v["hash"], "frozen": v["frozen"], "frozen_hash": fh,
            "matches_frozen": (fh == v["hash"]) if fh else None, "verified": v["verified"],
            "problems": v["problems"]}


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
# 规范 JSON 与哈希
# ---------------------------------------------------------------------------

def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_json_default)


def _json_default(o):
    import numpy as np
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(f"not JSON serialisable: {type(o)}")


def entry_hash(record: Mapping) -> str:
    body = {k: v for k, v in record.items() if k != "entry_hash"}
    return hashlib.sha256(_canonical(body).encode()).hexdigest()


# ---------------------------------------------------------------------------
# 语义核对（写入前与 verify 时都做）
# ---------------------------------------------------------------------------

def entry_problems(rec: Mapping, *, regenerate: bool = True) -> list[str]:
    """一条记录与任务注册表、自身内容是否一致。regenerate=True 时从记录里的调度重新生成电路核对哈希。"""
    from evaluators import candidate as cand
    from evaluators import tasks as T
    from evaluators.l2 import DecoderConfig, circuit_hash

    P: list[str] = []
    tid = rec.get("task_id")
    if tid not in T.TASKS:
        return [f"unknown task {tid!r}"]
    task = T.TASKS[tid]
    if rec.get("task_hash") != task.hash():
        P.append("task_hash does not match the registered task (task definition changed or forged)")
    for f, want in (("noise_model", task.noise_model), ("p", task.p), ("rounds", task.rounds),
                    ("boundary", task.boundary), ("purpose", task.purpose)):
        if rec.get(f) != want:
            P.append(f"{f}={rec.get(f)!r} but task {tid} has {want!r}")
    if dict(rec.get("boundary_options") or {}) != dict(task.boundary_options):
        P.append("boundary_options differ from the task")
    try:
        code, norm = T.build_code(task, (rec.get("code") or {}).get("spec"))
        if T.code_hash(code) != rec["code"].get("checks_sha256") or norm != rec["code"].get("spec"):
            P.append("code hash/spec mismatch")
    except Exception as e:  # noqa: BLE001
        return P + [f"code cannot be rebuilt: {e}"]
    try:
        spec = cand.parse_schedule(rec.get("schedule"))
        if cand.validate_schedule(spec, code):
            return P + ["schedule violates the template constraints"]
        if spec.hash() != rec.get("schedule_hash"):
            P.append("schedule_hash is not the hash of the stored schedule")
    except Exception as e:  # noqa: BLE001
        return P + [f"schedule cannot be parsed: {e}"]
    rounds = [task.rounds] if task.boundary != "diff" else [task.boundary_options["diff_rounds"], task.rounds]
    ch = rec.get("circuit_hashes") or {}
    if regenerate:
        for R in rounds:
            if ch.get(str(R)) != circuit_hash(cand.build_circuits(spec, code, R)):
                P.append(f"circuit hash for {R} rounds does not match the circuits generated from the schedule")
    rv = rec.get("rounds_verified") or {}
    for R in rounds:
        if rv.get(str(R)) != {"Z": [R], "X": [R]}:
            P.append(f"L0-verified round count for {R} rounds missing or wrong: {rv.get(str(R))}")
    l0 = rec.get("l0") or {}
    if not l0 or not all(v.get("passed") for v in l0.values()):
        P.append("not every L0 run passed")
    dmin = task.l0.get("min_circuit_distance")
    dub = rec.get("distance_upper_bound")
    if dmin is not None and (dub is None or dub < dmin):
        P.append(f"distance upper bound {dub} below the task minimum {dmin}")
    l2 = rec.get("l2") or {}
    inp = l2.get("inputs") or {}
    if inp.get("seed") != rec.get("seed"):
        P.append("L2 seed differs from the record seed")
    for f, want in (("noise_model", task.noise_model), ("p", task.p), ("rounds", task.rounds),
                    ("boundary", task.boundary)):
        if inp.get(f) != want:
            P.append(f"L2 input {f}={inp.get(f)!r} differs from the task ({want!r})")
    want_stop = {"max_shots": task.stop["max_shots"], "max_errors": task.stop.get("max_errors"),
                 "min_sector_errors": task.stop.get("min_sector_errors"),
                 "batch_size": task.stop.get("batch_size", 256)}
    if inp.get("stop") != want_stop:
        P.append(f"L2 stop rule {inp.get('stop')} differs from the task {want_stop}")
    dec = DecoderConfig(task.decoder["name"], dict(task.decoder.get("params") or {}))
    if (l2.get("decoder") or {}).get("name") != dec.name or \
            json.loads(_canonical((l2.get("decoder") or {}).get("params"))) != json.loads(_canonical(dec.resolved_params())):
        P.append("L2 decoder differs from the task")
    cand_hash = (l2.get("circuit") or {}).get("candidate_hash")
    want_hash = ch.get(str(task.rounds)) if task.boundary != "diff" else {str(R): ch.get(str(R)) for R in rounds}
    if cand_hash != want_hash:
        P.append("L2 was not sampled on the evaluator-generated circuits of this record")
    if task.boundary == "diff":
        runs = [((l2.get("components") or {}).get(str(R)) or {}).get("counts") or {} for R in rounds]
    else:
        runs = [l2.get("counts") or {}]
    for c in runs:
        if min(c.get("fail_Z", 0), c.get("fail_X", 0)) < T.MIN_SECTOR_ERRORS_FOR_LEADERBOARD:
            P.append(f"fewer than {T.MIN_SECTOR_ERRORS_FOR_LEADERBOARD} failures in a sector ({c}); small samples "
                     f"are not ranked")
    # 分数必须能由计数重算（伪造的 rates / per_round 被发现；计数本身的伪造只能靠 reproduce_entry 复算）
    try:
        from evaluators.l2 import diff_per_round, per_round as _per_round
        from evaluators.stats import binomial_interval
        lf = inp.get("likelihood_factor", 1000.0)
        if task.boundary == "diff":
            k_obs = (l2.get("joint") or {}).get("num_observables") or {}
            kk = {"P_Z": k_obs.get("Z"), "P_X": k_obs.get("X"), "P_any": (k_obs.get("Z") or 0) + (k_obs.get("X") or 0)}
            ck = {"P_Z": "fail_Z", "P_X": "fail_X", "P_any": "fail_any"}
            for key in ("P_Z", "P_X", "P_any"):
                d = diff_per_round(runs[0][ck[key]], runs[0]["shots"], rounds[0], runs[1][ck[key]], runs[1]["shots"],
                                   rounds[1], num_observables=kk[key], likelihood_factor=lf)
                got = ((l2.get("per_round") or {}).get(key)) or {}
                if any(not _close(got.get(f), d[f]) for f in ("best", "low", "high")):
                    P.append(f"L2 per-round {key} is not what the counts give")
        else:
            c = runs[0]
            for key, ck in (("P_Z", "fail_Z"), ("P_X", "fail_X"), ("P_any", "fail_any")):
                iv = binomial_interval(c[ck], c["shots"], lf)
                got = ((l2.get("per_round") or {}).get(key)) or {}
                want = {"best": _per_round(iv.best, task.rounds), "low": _per_round(iv.low, task.rounds),
                        "high": _per_round(iv.high, task.rounds)}
                if any(not _close(got.get(f), want[f]) for f in want):
                    P.append(f"L2 per-round {key} is not what the counts give")
    except Exception as e:  # noqa: BLE001
        P.append(f"L2 counts cannot be re-scored: {e}")
    pr = ((l2.get("per_round") or {}).get("P_any")) or {}
    sc = ((rec.get("score") or {}).get("per_round_P_any")) or {}
    if not pr or any(sc.get(k) != pr.get(k) for k in ("best", "low", "high")):
        P.append("score does not equal the L2 per-round P_any")
    if pr and (pr.get("best") is None or pr["best"] < 0 or (pr.get("low") is not None and pr.get("high") is not None
                                                            and pr["low"] > pr["high"])):
        P.append("invalid L2 estimate (negative or inverted interval)")
    if task.boundary == "diff" and not all(((l2.get("per_round") or {}).get(k) or {}).get("diff", {}).get("valid")
                                           for k in ("P_Z", "P_X", "P_any")):
        P.append("diff estimate flagged invalid")
    return P


def _close(a, b, rel: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= rel * max(abs(a), abs(b), 1e-300)


# ---------------------------------------------------------------------------
# 写入（只有 pipeline）
# ---------------------------------------------------------------------------

def submit(*_a, **_k):
    raise PermissionError("leaderboard.submit was removed in evaluator v2: only evaluators.pipeline.evaluate writes "
                          "the leaderboard (candidates submit a schedule, not L0/L2 dictionaries)")


def build_entry(*_a, **_k):
    raise PermissionError("leaderboard.build_entry was removed in evaluator v2: use evaluators.pipeline.evaluate")


def _last_line(f) -> str | None:
    f.seek(0)
    data = f.read()
    if not data:
        return None
    if not data.endswith("\n"):
        raise RuntimeError("leaderboard file does not end with a newline (possibly corrupted); refusing to append")
    return data.rstrip("\n").rsplit("\n", 1)[-1]


def _append(record: Mapping, path, credential) -> dict:
    from evaluators import pipeline
    if credential is not pipeline._CREDENTIAL:
        raise PermissionError("only evaluators.pipeline may write the leaderboard")
    reserved = [f for f in SYSTEM_FIELDS if f in record]
    if reserved:
        raise ValueError(f"fields {reserved} are filled in by the leaderboard")
    rec = json.loads(_canonical(dict(record)))
    probs = entry_problems(rec)
    if probs:
        raise ValueError("refusing to append an inconsistent record: " + "; ".join(probs))
    path = Path(path) if path is not None else DEFAULT_PATH
    rec["time"] = _dt.datetime.now(_dt.UTC).isoformat()
    rec["evaluator"] = evaluator_hash()
    rec["git"] = git_info()
    rec["versions"] = _versions()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            text = f.read()
            if text and not text.endswith("\n"):
                raise RuntimeError("leaderboard file does not end with a newline (possibly corrupted)")
            lines = [x for x in text.splitlines() if x.strip()]
            if lines:
                try:
                    last = json.loads(lines[-1])
                    prev, seq = last["entry_hash"], int(last["seq"]) + 1
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                    raise RuntimeError(f"last leaderboard line is not a valid record: {e}") from e
            else:
                prev, seq = GENESIS, 0
            attempt = 0
            for x in lines:
                try:
                    o = json.loads(x)
                except json.JSONDecodeError:
                    continue
                if o.get("task_id") == rec["task_id"] and o.get("schedule_hash") == rec["schedule_hash"]:
                    attempt += 1
            rec["seq"] = seq
            rec["attempt"] = attempt
            rec["prev_hash"] = prev
            rec["entry_hash"] = entry_hash(rec)
            f.seek(0, os.SEEK_END)
            f.write(_canonical(rec) + "\n")
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return rec


# ---------------------------------------------------------------------------
# 读取、核对、锚点
# ---------------------------------------------------------------------------

def read_leaderboard(path=None, task_id: str | None = None) -> list[dict]:
    path = Path(path) if path is not None else DEFAULT_PATH
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            text = f.read()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    recs = [json.loads(x) for x in text.splitlines() if x.strip()]
    return [r for r in recs if task_id is None or r.get("task_id") == task_id]


def chain_head(path=None) -> tuple[int, str]:
    """(行数, 链尾 entry_hash)；空榜为 (0, GENESIS)。"""
    recs = read_leaderboard(path)
    return (len(recs), recs[-1]["entry_hash"]) if recs else (0, GENESIS)


def anchor_line(path=None) -> str:
    """写进 git commit message 的外部锚点，例如 'leaderboard-anchor: lines=3 head=ab12…'。"""
    n, h = chain_head(path)
    return f"leaderboard-anchor: lines={n} head={h}"


def git_anchors() -> list[tuple[int, str]]:
    """git 历史（全部分支）里所有 commit message 中的锚点。"""
    try:
        out = subprocess.run(["git", "log", "--all", "--format=%B"], cwd=ROOT, capture_output=True, text=True,
                             timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [(int(n), h) for n, h in ANCHOR_RE.findall(out)]


def verify_leaderboard(path=None, *, anchors=None, semantic: bool = True, regenerate: bool = True) -> list[str]:
    """哈希链 + 外部锚点 + 每条记录的语义核对。返回问题列表（空 = 完整）。

    anchors：[(行数, 该行 entry_hash)]；默认路径时自动加上 git 历史里的锚点。
    """
    is_default = path is None or Path(path).resolve() == DEFAULT_PATH.resolve()
    path = Path(path) if path is not None else DEFAULT_PATH
    anchors = list(anchors or [])
    if is_default:
        anchors += git_anchors()
    if not path.exists():
        return [f"anchor lines={n}: leaderboard file missing" for n, _ in anchors if n > 0]
    problems = []
    text = path.read_text(encoding="utf-8")
    if text and not text.endswith("\n"):
        problems.append("file does not end with a newline")
    prev = GENESIS
    hashes = []
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            problems.append(f"line {i}: empty")
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            problems.append(f"line {i}: invalid JSON ({e})")
            prev = None
            hashes.append(None)
            continue
        if rec.get("prev_hash") != prev:
            problems.append(f"line {i}: prev_hash does not match the previous entry (chain broken)")
        if rec.get("entry_hash") != entry_hash(rec):
            problems.append(f"line {i}: entry_hash mismatch (line modified)")
        if rec.get("seq") != i - 1:
            problems.append(f"line {i}: seq {rec.get('seq')} != {i - 1}")
        if semantic:
            for p in entry_problems(rec, regenerate=regenerate):
                problems.append(f"line {i}: {p}")
        prev = rec.get("entry_hash")
        hashes.append(prev)
    for n, h in anchors:
        if n == 0:
            continue
        if n > len(hashes):
            problems.append(f"anchor lines={n}: the leaderboard has only {len(hashes)} lines (tail deleted)")
        elif hashes[n - 1] != h:
            problems.append(f"anchor lines={n}: line {n} hash changed (history rewritten)")
    return problems


def table(task_id: str, path=None) -> list[dict]:
    """一个任务的排名（只看该任务；同一调度只按第一次提交排名）。按每轮 P_any 点估计升序。"""
    first: dict[str, dict] = {}
    count: dict[str, int] = {}
    for r in read_leaderboard(path, task_id=task_id):
        h = r["schedule_hash"]
        count[h] = count.get(h, 0) + 1
        first.setdefault(h, r)
    rows = []
    for h, r in first.items():
        s = r["score"]["per_round_P_any"]
        rows.append({"schedule_hash": h, "candidate_id": r.get("candidate_id"), "seq": r["seq"],
                     "per_round_P_any": s["best"], "low": s["low"], "high": s["high"],
                     "per_round_per_logical": r["score"]["per_round_per_logical"],
                     "distance_upper_bound": r.get("distance_upper_bound"), "submissions": count[h]})
    return sorted(rows, key=lambda x: x["per_round_P_any"])


def reproduce_entry(rec: Mapping, work_dir=None) -> list[str]:
    """按记录里的 (task, code, schedule, seed) 重新跑一遍 pipeline（不写榜），核对 L2 计数逐位相同。
    很慢（与原评估相同的算力）；auditor 抽查用。返回不一致项（空 = 复现）。"""
    from evaluators.pipeline import evaluate
    rep = evaluate(rec["task_id"], rec["code"]["spec"], rec["schedule"], seed=rec["seed"], submit=False,
                   work_dir=work_dir)
    out = []
    if rep.schedule_hash != rec["schedule_hash"]:
        out.append("schedule hash differs")
    if rep.circuit_hashes != rec["circuit_hashes"]:
        out.append("circuit hashes differ")
    if rep.l2 is None:
        return out + [f"re-evaluation did not reach L2 (status {rep.status})"]
    if rep.l2["counts"] != rec["l2"]["counts"]:
        out.append(f"L2 counts differ: {rep.l2['counts']} vs {rec['l2']['counts']}")
    if rep.distance_upper_bound != rec.get("distance_upper_bound"):
        out.append(f"distance upper bound differs: {rep.distance_upper_bound} vs {rec.get('distance_upper_bound')}")
    return out
