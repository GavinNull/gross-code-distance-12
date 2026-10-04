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
    "is_official_path",
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


def is_official_path(p) -> bool:
    """p 是否指向正式成绩单（auditor v2 S10）：None，或 resolve（解析符号链接、相对路径、..）后等于 DEFAULT_PATH，
    或者两个文件都存在且是同一个 inode（硬链接）。"""
    if p is None:
        return True
    a = Path(p).expanduser().resolve()
    b = DEFAULT_PATH.resolve()
    if a == b:
        return True
    try:
        return a.exists() and b.exists() and os.path.samefile(a, b)
    except OSError:
        return False


def frozen_record() -> dict | None:
    """research/evaluator_freeze.json（冻结时写在 evaluators/ 之外的记录）；没有冻结时为 None。"""
    path = ROOT / "research" / "evaluator_freeze.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def official_problems(rec: Mapping) -> list[str]:
    """正式成绩单上每条记录额外要满足的条件（auditor v2 W2）：purpose=score、记录的评估器已冻结且验证通过、
    评估器哈希等于冻结记录 research/evaluator_freeze.json 里的哈希、库版本等于 tasks.PINNED_VERSIONS。"""
    from evaluators import tasks as T
    P = []
    if rec.get("purpose") != "score":
        P.append(f"purpose {rec.get('purpose')!r} is not allowed on the official leaderboard")
    ev = rec.get("evaluator") or {}
    if ev.get("verified") is not True or ev.get("frozen") is not True:
        P.append("recorded evaluator was not frozen and verified")
    fr = frozen_record()
    want = (fr or {}).get("hash") or (fr or {}).get("evaluator_hash")
    if not want:
        P.append("no frozen evaluator record (research/evaluator_freeze.json) to check the evaluator hash against")
    elif ev.get("hash") != want:
        P.append("recorded evaluator hash differs from the frozen evaluator hash")
    vers = rec.get("versions") or {}
    bad = {k: vers.get(k) for k, v in T.PINNED_VERSIONS.items() if vers.get(k) != v}
    if bad:
        P.append(f"library versions differ from the pinned versions: {bad}")
    return P


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
    if rec.get("kind", "l2") != task.kind:
        P.append(f"kind={rec.get('kind')!r} but task {tid} is {task.kind!r}")
    if task.kind == "distance":
        return P + _distance_entry_problems(rec, task, regenerate=regenerate)
    if task.kind == "decoder":
        return P + _decoder_entry_problems(rec, task, regenerate=regenerate)
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
    if task.purpose == "score":
        from evaluators.pipeline import derive_seed
        if rec.get("seed") != derive_seed(task.hash(), rec.get("schedule_hash"), "l2"):
            P.append("seed is not the evaluator-derived seed of this task and schedule (seed shopping)")
    rounds = [task.rounds] if task.boundary != "diff" else [task.boundary_options["diff_rounds"], task.rounds]
    ch = rec.get("circuit_hashes") or {}
    if regenerate:
        for R in rounds:
            if ch.get(str(R)) != circuit_hash(cand.build_circuits(spec.canonical(), code, R)):
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
        top = l2.get("counts") or {}
        for R, c in zip(rounds, runs):
            if top.get(f"rounds_{R}") != c:
                P.append(f"top-level L2 counts for {R} rounds differ from the component counts")
        if top.get("shots") != sum(c.get("shots", 0) for c in runs):
            P.append("top-level L2 shots differ from the sum of the components")
    else:
        runs = [l2.get("counts") or {}]
    bs = want_stop["batch_size"]
    for c in runs:
        if c.get("shots") != c.get("batches_used", -1) * bs:
            P.append(f"L2 shots {c.get('shots')} != batches_used {c.get('batches_used')} x batch_size {bs}")
        if not (c.get("fail_any", 0) <= c.get("fail_Z", 0) + c.get("fail_X", 0)
                and max(c.get("fail_Z", 0), c.get("fail_X", 0)) <= c.get("fail_any", 0) <= c.get("shots", 0)
                and c.get("fail_both", 0) == c.get("fail_Z", 0) + c.get("fail_X", 0) - c.get("fail_any", 0)):
            P.append(f"L2 counts are not self-consistent: {c}")
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


def _distance_entry_problems(rec: Mapping, task, *, regenerate: bool = True) -> list[str]:
    """距离任务（kind="distance"）记录的语义核对：任务参数、码、调度、电路哈希、派生种子、L0、分数与见证一致；
    regenerate=True 时从调度重新生成电路，把每个基底的最短见证重新注入验证（伪造的“更短”见证或与电路对不上的
    见证都会被发现）。声称的距离**偏大**（藏起更短的见证）只能靠 reproduce_entry 按同一种子复算发现。"""
    from evaluators import candidate as cand
    from evaluators import tasks as T
    from evaluators.distance import Fault, verify_faults
    from evaluators.l2 import circuit_hash
    from evaluators.noise import add_noise
    from evaluators.pipeline import derive_seed

    P: list[str] = []
    for f, want in (("noise_model", task.noise_model), ("rounds", task.rounds), ("purpose", task.purpose)):
        if rec.get(f) != want:
            P.append(f"{f}={rec.get(f)!r} but task {task.task_id} has {want!r}")
    if json.loads(_canonical(rec.get("distance_params"))) != json.loads(_canonical(dict(task.l0))):
        P.append("distance_params differ from the task's fixed budget")
    try:
        code, norm = T.build_code(task, (rec.get("code") or {}).get("spec"))
        if T.code_hash(code) != rec["code"].get("checks_sha256") or norm != rec["code"].get("spec"):
            P.append("code hash/spec mismatch")
    except Exception as e:  # noqa: BLE001
        return P + [f"code cannot be rebuilt: {e}"]
    try:
        spec = cand.parse_schedule(rec.get("schedule"))
        probs = cand.validate_schedule(spec, code)
        maxp = (task.schedule_constraints or {}).get("max_period")
        if probs or (maxp is not None and spec.period > maxp):
            return P + ["schedule violates the template / task constraints"]
        if spec.hash() != rec.get("schedule_hash"):
            P.append("schedule_hash is not the hash of the stored schedule")
    except Exception as e:  # noqa: BLE001
        return P + [f"schedule cannot be parsed: {e}"]
    if rec.get("seed") != derive_seed(task.hash(), rec.get("schedule_hash"), "distance"):
        P.append("seed is not the evaluator-derived distance seed of this task and schedule")
    R = task.rounds
    canon = spec.canonical()
    circs = cand.build_circuits(canon, code, R) if regenerate else None
    if regenerate and (rec.get("circuit_hashes") or {}).get(str(R)) != circuit_hash(circs):
        P.append(f"circuit hash for {R} rounds does not match the circuits generated from the schedule")
    if (rec.get("rounds_verified") or {}).get(str(R)) != {"Z": [R], "X": [R]}:
        P.append("L0-verified round count missing or wrong")
    l0 = rec.get("l0") or {}
    if not l0 or not all(v.get("passed") for v in l0.values()):
        P.append("not every L0 run passed")
    dist = rec.get("distance") or {}
    per = dist.get("per_basis") or {}
    if set(per) != {"Z", "X"}:
        return P + ["distance results for both bases are required"]
    ws = {}
    for b, v in per.items():
        faults = v.get("faults") or []
        if v.get("weight") is None or len(faults) != v["weight"]:
            P.append(f"{b}: witness has {len(faults)} faults but weight {v.get('weight')}")
            continue
        ws[b] = v["weight"]
        if regenerate:
            try:
                noisy = add_noise(circs[b], task.noise_model, 1e-3)
                ok, msg, _ = verify_faults(noisy.flattened(), [Fault(**f) for f in faults])
            except Exception as e:  # noqa: BLE001
                ok, msg = False, str(e)
            if not ok:
                P.append(f"{b}: witness fails re-injection ({msg})")
    d = min(ws.values()) if len(ws) == 2 else None
    if d is None or dist.get("d_circ_upper_bound") != d or rec.get("distance_upper_bound") != d:
        P.append("d_circ upper bound is not the minimum witness weight over the two bases")
    lw = sum(per[b].get("min_weight_count") or 0 for b in ws if ws[b] == d) if d is not None else None
    if dist.get("low_weight_witnesses") != lw:
        P.append("low_weight_witnesses is not the sum of the per-basis minimum-weight counts")
    sc = rec.get("score") or {}
    if (sc.get("d_circ_upper_bound") != d or sc.get("low_weight_witnesses") != lw or sc.get("period") != spec.period
            or sc.get("sort_key") != [-(d or 0), lw, spec.period]):
        P.append("score does not match the distance results")
    return P


def _decoder_entry_problems(rec: Mapping, task, *, regenerate: bool = True) -> list[str]:
    """解码器任务（kind="decoder"，H-005）记录的语义核对：任务参数一致、split 必须是 holdout、程序哈希 = 记录里
    程序源码的 sha256、电路哈希可由任务重新生成（regenerate）、种子承诺等于由密钥派生的承诺（有密钥时）、计数自洽、
    每个 sector ≥ 1000 次失败、分数（P_any 与每轮值）可由计数重算、参考计数自洽、OS 沙箱。计数本身的伪造只能靠
    重新评估（同一留出集）发现；超时判定依赖机器负载，重评估只能统计一致，不能逐位一致（README §12）。"""
    import hashlib

    from evaluators import tasks as T
    from evaluators.l2 import per_round as _per_round
    from evaluators.stats import binomial_interval

    P: list[str] = []
    for f, want in (("noise_model", task.noise_model), ("p", task.p), ("rounds", task.rounds),
                    ("boundary", task.boundary), ("purpose", task.purpose)):
        if rec.get(f) != want:
            P.append(f"{f}={rec.get(f)!r} but task {task.task_id} has {want!r}")
    if rec.get("split") != "holdout":
        P.append(f"split {rec.get('split')!r}: only held-out evaluations can be ranked")
    prog = rec.get("program")
    if not isinstance(prog, str) or hashlib.sha256(prog.encode("utf-8")).hexdigest() != rec.get("program_hash"):
        P.append("program_hash is not the sha256 of the stored program")
    if rec.get("schedule_hash") != rec.get("program_hash"):
        P.append("schedule_hash (attempt key) must equal program_hash")
    if rec.get("batch_size") != int(task.stop["batch_size"]):
        P.append("batch size differs from the task")
    if rec.get("os_sandbox") is not True:
        P.append("candidate did not run under the OS-level sandbox")
    if regenerate:
        try:
            from evaluators.decoder_problem import build_instance
            if build_instance(task).circuit_hash != rec.get("circuit_hash"):
                P.append("circuit hash differs from the circuits the task generates")
        except Exception as e:  # noqa: BLE001
            P.append(f"task circuits cannot be rebuilt: {e}")
    try:
        from evaluators.decoder_eval import _seed_commitment
        if _seed_commitment(task, "holdout") != rec.get("seed_commitment"):
            P.append("seed commitment differs from the held-out seed derived from the decoder secret")
    except Exception as e:  # noqa: BLE001 - 没有密钥时无法核对，记一条
        P.append(f"seed commitment cannot be checked (decoder secret unavailable: {type(e).__name__})")
    c = rec.get("counts") or {}
    n = c.get("shots", 0)
    bs = int(task.stop["batch_size"])
    if not isinstance(n, int) or n <= 0 or n % bs or n > int(task.stop["max_shots"]) + bs * task.num_workers:
        P.append(f"shots {n} is not a positive multiple of the batch size within the task budget")
    if not (c.get("fail_any", 0) <= c.get("fail_Z", 0) + c.get("fail_X", 0)
            and max(c.get("fail_Z", 0), c.get("fail_X", 0)) <= c.get("fail_any", 0) <= n
            and c.get("fail_both", 0) == c.get("fail_Z", 0) + c.get("fail_X", 0) - c.get("fail_any", 0)):
        P.append(f"counts are not self-consistent: {c}")
    if min(c.get("fail_Z", 0), c.get("fail_X", 0)) < T.MIN_SECTOR_ERRORS_FOR_LEADERBOARD:
        P.append(f"fewer than {T.MIN_SECTOR_ERRORS_FOR_LEADERBOARD} failures in a sector; small samples are not ranked")
    sec = rec.get("sectors") or {}
    for s, key in (("Z", "fail_Z"), ("X", "fail_X")):
        st = sec.get(s) or {}
        parts = sum(int(st.get(f, 0)) for f in ("wrong", "timeout", "budget", "error", "format", "dead"))
        if st.get("shots") != n or st.get("failures") != c.get(key) or parts < c.get(key, 0):
            P.append(f"sector {s} breakdown does not match the counts")
    try:
        for key, ck in (("P_Z", "fail_Z"), ("P_X", "fail_X"), ("P_any", "fail_any")):
            iv = binomial_interval(c[ck], n)
            got = (rec.get("rates") or {}).get(key) or {}
            if any(not _close(got.get(f), getattr(iv, f)) for f in ("best", "low", "high")):
                P.append(f"rate {key} is not what the counts give")
            pr = (rec.get("per_round") or {}).get(key) or {}
            if any(not _close(pr.get(f), _per_round(getattr(iv, f), task.rounds)) for f in ("best", "low", "high")):
                P.append(f"per-round {key} is not what the counts give")
    except Exception as e:  # noqa: BLE001
        P.append(f"counts cannot be re-scored: {e}")
    sc = rec.get("score") or {}
    if sc.get("P_any") != (rec.get("rates") or {}).get("P_any") or \
            sc.get("per_round_P_any") != (rec.get("per_round") or {}).get("P_any"):
        P.append("score does not equal the counted P_any")
    ref = (rec.get("reference") or {})
    if ref.get("name") != task.decoder["reference"]["name"] or \
            json.loads(_canonical(ref.get("params"))) != json.loads(_canonical(task.decoder["reference"]["params"])):
        P.append("reference decoder differs from the task")
    rc = ref.get("counts") or {}
    if rc.get("shots") != n:
        P.append("reference was not run on the same shots")
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


def verify_leaderboard(path=None, *, anchors=None, semantic: bool = True, regenerate: bool = True,
                       official: bool | None = None) -> list[str]:
    """哈希链 + 外部锚点 + 每条记录的语义核对。返回问题列表（空 = 完整）。

    anchors：[(行数, 该行 entry_hash)]；默认路径时自动加上 git 历史里的锚点。
    official：是否按正式成绩单核对（official_problems：purpose=score、评估器已冻结且哈希等于冻结记录、库版本固定）；
    None = 路径指向正式成绩单时（is_official_path，resolve 后比较）自动打开（auditor v2 S10 / W2）。
    """
    is_default = is_official_path(path)
    if official is None:
        official = is_default
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
        if official:
            for p in official_problems(rec):
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
    """一个任务的排名（只看该任务；同一调度只按第一次提交排名）。L2 任务按每轮 P_any 点估计升序；距离任务按
    （距离上界降序、最小权重见证数升序、周期升序）。"""
    first: dict[str, dict] = {}
    count: dict[str, int] = {}
    for r in read_leaderboard(path, task_id=task_id):
        h = r["schedule_hash"]
        count[h] = count.get(h, 0) + 1
        first.setdefault(h, r)
    rows = []
    if any(r.get("kind") == "decoder" for r in first.values()):
        for h, r in first.items():
            s = r["score"]
            rows.append({"program_hash": h, "candidate_id": r.get("candidate_id"), "seq": r["seq"],
                         "P_any": s["P_any"]["best"], "low": s["P_any"]["low"], "high": s["P_any"]["high"],
                         "per_round_P_any": s["per_round_P_any"]["best"], "cpu_per_shot_ms": s["cpu_per_shot_ms"],
                         "reference_P_any": ((r.get("reference") or {}).get("rates") or {}).get("P_any", {}).get("best"),
                         "shots": r["counts"]["shots"], "submissions": count[h]})
        return sorted(rows, key=lambda x: (x["P_any"], x["cpu_per_shot_ms"], x["seq"]))
    if any(r.get("kind") == "distance" for r in first.values()):
        for h, r in first.items():
            s = r["score"]
            rows.append({"schedule_hash": h, "candidate_id": r.get("candidate_id"), "seq": r["seq"],
                         "d_circ_upper_bound": s["d_circ_upper_bound"],
                         "low_weight_witnesses": s["low_weight_witnesses"], "period": s["period"],
                         "submissions": count[h]})
        return sorted(rows, key=lambda x: (-x["d_circ_upper_bound"], x["low_weight_witnesses"], x["period"],
                                           x["seq"]))
    for h, r in first.items():
        s = r["score"]["per_round_P_any"]
        rows.append({"schedule_hash": h, "candidate_id": r.get("candidate_id"), "seq": r["seq"],
                     "per_round_P_any": s["best"], "low": s["low"], "high": s["high"],
                     "per_round_per_logical": r["score"]["per_round_per_logical"],
                     "distance_upper_bound": r.get("distance_upper_bound"), "submissions": count[h]})
    return sorted(rows, key=lambda x: x["per_round_P_any"])


def reproduce_entry(rec: Mapping) -> list[str]:
    """按记录里的 (task, code, schedule, seed) 重新跑一遍 pipeline（不写榜），核对 L2 计数逐位相同（diff 任务逐个
    component 比较，auditor v2 R2）；距离任务核对距离、见证数与每个基底的见证。
    很慢（与原评估相同的算力）；auditor 抽查用。返回不一致项（空 = 复现）。"""
    if rec.get("kind") == "decoder":
        # 解码器：同一留出集重评估；超时判定依赖负载，只要求分数在区间内一致（README §12）
        from evaluators.decoder_eval import evaluate_decoder
        rep = evaluate_decoder(rec["task_id"], rec["program"], split="holdout", submit=False)
        out = []
        lo, hi = rec["score"]["P_any"]["low"], rec["score"]["P_any"]["high"]
        if not (lo <= rep.rates["P_any"]["best"] <= hi):
            out.append(f"re-evaluated P_any {rep.rates['P_any']['best']:.3e} outside the recorded interval "
                       f"[{lo:.3e}, {hi:.3e}]")
        if rep.counts.get("shots") == rec["counts"]["shots"] and \
                rep.reference.get("counts") != rec["reference"].get("counts"):
            out.append("reference counts differ on the same held-out shots")
        return out
    from evaluators.pipeline import evaluate
    rep = evaluate(rec["task_id"], rec["code"]["spec"], rec["schedule"], seed=rec["seed"], submit=False)
    out = []
    if rep.seed != rec.get("seed"):
        out.append(f"seed differs: {rep.seed} vs {rec.get('seed')}")
    if rep.schedule_hash != rec["schedule_hash"]:
        out.append("schedule hash differs")
    if rep.circuit_hashes != rec["circuit_hashes"]:
        out.append("circuit hashes differ")
    if rec.get("kind") == "distance":
        if rep.distance is None:
            return out + [f"re-evaluation did not reach the distance search (status {rep.status})"]
        d0 = rec.get("distance") or {}
        if rep.distance["d_circ_upper_bound"] != d0.get("d_circ_upper_bound"):
            out.append(f"distance differs: {rep.distance['d_circ_upper_bound']} vs {d0.get('d_circ_upper_bound')}")
        if rep.distance["low_weight_witnesses"] != d0.get("low_weight_witnesses"):
            out.append("low-weight witness count differs")
        for b, v in (d0.get("per_basis") or {}).items():
            if (rep.distance["per_basis"].get(b) or {}).get("faults") != v.get("faults"):
                out.append(f"{b}: witness differs")
        return out
    if rep.l2 is None:
        return out + [f"re-evaluation did not reach L2 (status {rep.status})"]
    if rep.l2["counts"] != rec["l2"]["counts"]:
        out.append(f"L2 counts differ: {rep.l2['counts']} vs {rec['l2']['counts']}")
    comp_new = {r: (c or {}).get("counts") for r, c in (rep.l2.get("components") or {}).items()}
    comp_old = {r: (c or {}).get("counts") for r, c in (rec["l2"].get("components") or {}).items()}
    if comp_new != comp_old:
        out.append(f"L2 component counts differ: {comp_new} vs {comp_old}")
    pa_new = ((rep.l2.get("per_round") or {}).get("P_any") or {}).get("best")
    pa_old = ((rec["l2"].get("per_round") or {}).get("P_any") or {}).get("best")
    if pa_new != pa_old:
        out.append(f"L2 per-round P_any differs: {pa_new} vs {pa_old}")
    if rep.distance_upper_bound != rec.get("distance_upper_bound"):
        out.append(f"distance upper bound differs: {rep.distance_upper_bound} vs {rec.get('distance_upper_bound')}")
    return out
