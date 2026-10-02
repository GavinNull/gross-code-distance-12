"""S3 成绩单回归（LB1–LB7）与新攻击。全部写临时文件，不碰 research/leaderboard.jsonl。

  LB-API   submit / build_entry / _append(假凭证)
  LB1/3/4/7 拿到真凭证（同进程）后提交与任务不一致的记录（rounds、噪声、调度哈希、p）
  LB2c     同进程拿真凭证，伪造“计数自洽”的记录（失败数不变、shots ×3）
  W1       **不用凭证**：直接把计数自洽的伪造记录追加到文件（哈希链自己算），verify_leaderboard 是否发现
  W2       记录的 evaluator 字段（哈希 / 是否冻结）被改成“未冻结的另一个评估器”，verify 是否发现
  LB5/LB6  删末行 / 改一行后整链重算：无锚点、有锚点
  R1       reproduce_entry 能否发现 W1 的伪造（paper 任务）
  R2       diff 任务：只伪造 components[r1].counts 与 per_round（保留顶层 counts），entry_problems 与 reproduce_entry 是否发现

用法：uv run python s3_leaderboard.py
"""
import copy
import json
import tempfile
from pathlib import Path

from common import surface
from evaluators import leaderboard as lb
from evaluators import pipeline
from evaluators.l2 import _interval_dict, diff_per_round, per_round
from evaluators.stats import binomial_interval

PAPER = "selftest-surface-d3-sd6-paper"
DIFF = "selftest-surface-d3-sd6-diff"


def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def raw_append(path: Path, rec: dict):
    """不经过 _append：自己算 seq / prev_hash / entry_hash 后直接写文件。"""
    lines = [x for x in path.read_text().splitlines() if x.strip()] if path.exists() else []
    last = json.loads(lines[-1]) if lines else None
    rec = copy.deepcopy(rec)
    rec["seq"] = (last["seq"] + 1) if last else 0
    rec["prev_hash"] = last["entry_hash"] if last else lb.GENESIS
    rec["attempt"] = 0
    rec.pop("entry_hash", None)
    rec["entry_hash"] = lb.entry_hash(rec)
    with open(path, "a") as f:
        f.write(canon(rec) + "\n")
    return rec


def forge_paper_counts(rec, factor=3):
    r = copy.deepcopy(rec)
    l2 = r["l2"]
    c = l2["counts"]
    c["shots"] *= factor
    lf = l2["inputs"].get("likelihood_factor", 1000.0)
    R = r["rounds"]
    for key, ck in (("P_Z", "fail_Z"), ("P_X", "fail_X"), ("P_any", "fail_any")):
        iv = binomial_interval(c[ck], c["shots"], lf)
        l2["per_round"][key].update(best=per_round(iv.best, R), low=per_round(iv.low, R), high=per_round(iv.high, R))
        l2["rates"][key] = _interval_dict(c[ck], c["shots"], lf)
    r["score"]["per_round_P_any"] = {k: l2["per_round"]["P_any"][k] for k in ("best", "low", "high")}
    r["score"]["per_round_per_logical"] = r["score"]["per_round_P_any"]["best"] / r["score"]["k"]
    r["candidate_id"] = "forged"
    return r


def main():
    _, spec = surface(3)
    sched = spec.to_dict()
    td = Path(tempfile.mkdtemp(prefix="s3lb_"))
    board = td / "board.jsonl"

    print("-- LB-API")
    for f in (lb.submit, lb.build_entry):
        try:
            f({})
        except PermissionError as e:
            print(f"  {f.__name__}: PermissionError ({str(e)[:60]}...)")
    try:
        lb._append({"task_id": PAPER}, board, object())
    except PermissionError as e:
        print("  _append with a fake credential: PermissionError")

    rep = pipeline.evaluate(PAPER, None, sched, seed=11, candidate_id="honest", leaderboard_path=board)
    print(f"honest paper run: status {rep.status}, score {rep.score['per_round_P_any']['best']:.4e}, "
          f"written seq {rep.leaderboard_record['seq']}, wall {rep.timing['wall_s']} s")
    good = {k: v for k, v in rep.leaderboard_record.items() if k not in lb.SYSTEM_FIELDS}

    print("-- LB1/3/4/7 with the real credential (in-process), inconsistent records")
    variants = {
        "LB1 rounds=30": lambda r: r.update(rounds=30),
        "LB3 noise_model=gross_sd6": lambda r: r.update(noise_model="gross_sd6"),
        "LB4 schedule_hash=deadbeef": lambda r: r.update(schedule_hash="deadbeef"),
        "LB7 p=1e-3": lambda r: r.update(p=1e-3),
        "LB2 per_round faked": lambda r: r["l2"]["per_round"]["P_any"].update(best=1e-9),
    }
    for name, f in variants.items():
        r = copy.deepcopy(good)
        f(r)
        try:
            lb._append(r, board, pipeline._CREDENTIAL)
            print(f"  {name}: ACCEPTED")
        except ValueError as e:
            print(f"  {name}: rejected ({str(e)[45:150]})")

    forged = forge_paper_counts(good)
    print(f"-- LB2c count-consistent forgery (shots x3): entry_problems = {lb.entry_problems(forged)}; "
          f"forged score {forged['score']['per_round_P_any']['best']:.4e}")

    print("-- W1 no credential: append the forged record directly to the file")
    raw_append(board, forged)
    print(f"  verify_leaderboard(board) = {lb.verify_leaderboard(board)}")
    print(f"  table: {[(x['candidate_id'], round(x['per_round_P_any'], 5)) for x in lb.table(PAPER, board)]}")

    print("-- W2 evaluator field says 'not frozen / other hash'")
    w2 = copy.deepcopy(good)
    w2["candidate_id"] = "unfrozen-evaluator"
    w2["schedule"] = copy.deepcopy(w2["schedule"])
    w2.update(evaluator={"hash": "0000000000000000", "frozen": False, "verified": None, "matches_frozen": None,
                         "frozen_hash": None, "problems": []},
              versions={"stim": "0.0.0"}, git={"commit": None, "evaluators_dirty": True}, time="1970-01-01")
    raw_append(board, w2)
    print(f"  verify_leaderboard(board) = {lb.verify_leaderboard(board)}")

    print("-- LB5 / LB6")
    lines = board.read_text().splitlines(keepends=True)
    n, head = lb.chain_head(board)
    anchor = [(n, head)]
    board.write_text("".join(lines[:-1]))
    print(f"  LB5 tail deleted, no anchor: {lb.verify_leaderboard(board, semantic=False)}")
    print(f"  LB5 tail deleted, anchor lines={n}: {lb.verify_leaderboard(board, anchors=anchor, semantic=False)}")
    board.write_text("".join(lines))
    recs = [json.loads(x) for x in lines]
    recs[0] = forge_paper_counts(recs[0], factor=2) | {k: recs[0][k] for k in lb.SYSTEM_FIELDS}
    prev = lb.GENESIS
    for r in recs:
        r["prev_hash"] = prev
        r.pop("entry_hash")
        r["entry_hash"] = lb.entry_hash(r)
        prev = r["entry_hash"]
    board.write_text("".join(canon(r) + "\n" for r in recs))
    print(f"  LB6 line 1 rewritten + re-chained, no anchor: {lb.verify_leaderboard(board)}")
    print(f"  LB6 with anchor lines={n}: {lb.verify_leaderboard(board, anchors=anchor, semantic=False)}")

    print("-- R1 reproduce_entry on the W1 forgery")
    print(f"  {lb.reproduce_entry(forged)}")

    print("-- R2 diff task: forge only components[r1] counts + per_round")
    board2 = td / "board2.jsonl"
    rd = pipeline.evaluate(DIFF, None, sched, seed=12, candidate_id="honest-diff", leaderboard_path=board2)
    g2 = {k: v for k, v in rd.leaderboard_record.items() if k not in lb.SYSTEM_FIELDS}
    f2 = copy.deepcopy(g2)
    l2 = f2["l2"]
    r1, r2 = rd.l2["inputs"]["diff_rounds"]
    c1 = l2["components"][str(r1)]["counts"]
    c2 = l2["components"][str(r2)]["counts"]
    c1["shots"] = int(c1["shots"] * 0.80)        # 短轮数那次的失败率被抬高 25% → 差分（体内每轮）变小
    k_obs = l2["joint"]["num_observables"]
    kk = {"P_Z": k_obs["Z"], "P_X": k_obs["X"], "P_any": k_obs["Z"] + k_obs["X"]}
    for key, ck in (("P_Z", "fail_Z"), ("P_X", "fail_X"), ("P_any", "fail_any")):
        d = diff_per_round(c1[ck], c1["shots"], r1, c2[ck], c2["shots"], r2, num_observables=kk[key],
                           likelihood_factor=l2["inputs"].get("likelihood_factor", 1000.0))
        l2["per_round"][key].update(best=d["best"], low=d["low"], high=d["high"], diff=d)
    f2["score"]["per_round_P_any"] = {k: l2["per_round"]["P_any"][k] for k in ("best", "low", "high")}
    f2["score"]["per_round_per_logical"] = f2["score"]["per_round_P_any"]["best"] / f2["score"]["k"]
    print(f"  honest diff score {g2['score']['per_round_P_any']['best']:.4e} -> forged "
          f"{f2['score']['per_round_P_any']['best']:.4e}")
    print(f"  top-level counts untouched: {l2['counts'][f'rounds_{r1}'] != c1}")
    print(f"  entry_problems(forged) = {lb.entry_problems(f2)}")
    print(f"  reproduce_entry(forged) = {lb.reproduce_entry(f2)}")
    print("temp dir:", td)


if __name__ == "__main__":
    main()
