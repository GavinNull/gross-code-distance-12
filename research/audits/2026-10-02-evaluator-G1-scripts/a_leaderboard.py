"""攻击 LB：leaderboard 的 submit / verify_leaderboard 与 sample_l2 的 rounds 参数。
全部写临时文件，不碰 research/leaderboard.jsonl。

  LB1  sample_l2 的 rounds 由调用方给出、不与电路核对：3 轮电路声称 rounds=30，每轮错误率缩小约 10 倍，submit 照收
  LB2  submit 只看 dict：伪造 l0={"passed": True}、伪造 l2 rates/per_round，照收
  LB3  非打分噪声模型（gross_sd6：只在显式 I 门上有空闲噪声）的 L2 结果照收（只有 warning）
  LB4  schedule_hash 与 L2 实际采样的电路不一致（circuits 参数换成别的电路），照收
  LB5  删掉末尾若干行：verify_leaderboard 不报错
  LB6  改写一行后把它和后续所有行的哈希链重算：verify_leaderboard 不报错（README 已承认）
  LB7  不同 decoder 参数（例如 osd_order 更高）与不同 p 混在同一个榜上，submit 不拒绝

用法：uv run python a_leaderboard.py
"""
import copy
import json
import tempfile
from pathlib import Path

from common import cons_for, honest

from evaluators.l0 import check_l0
from evaluators.leaderboard import build_entry, entry_hash, submit, verify_leaderboard
from evaluators.l2 import DecoderConfig, StopRule, sample_l2


def main():
    code, data, circs = honest(3, 3)
    _, _, circs5 = honest(3, 5)
    cons = cons_for(data, circs, 3, min_circuit_distance=3)
    l0 = check_l0(circs, code, "both", cons)
    assert l0.passed
    stop = StopRule(max_shots=20_000, batch_size=2000)
    kw = dict(decoder=DecoderConfig("pymatching"), seed=1, stop=stop, num_workers=1)
    true = sample_l2(code, circs, data, p=0.005, rounds=3, **kw)
    lie = sample_l2(code, circs, data, p=0.005, rounds=30, **kw)
    print(f"LB1 same 3-round circuit: rounds=3 -> per-round P_any {true.per_round['P_any']['best']:.3e}; "
          f"rounds=30 claimed -> {lie.per_round['P_any']['best']:.3e} "
          f"(same counts {true.counts['fail_any']} / {lie.counts['fail_any']})")

    tmp = Path(tempfile.mkdtemp()) / "lb.jsonl"
    r = submit(build_entry("LB1-rounds-lie", code=code, circuits=circs, l0_report=l0,
                           distance_upper_bound=l0.d_circ, l2=lie), tmp)
    print("LB1 accepted:", r["rounds"], r["l2"]["per_round"]["P_any"]["best"])

    forged_l2 = copy.deepcopy(true.to_dict())
    for key in ("P_Z", "P_X", "P_any"):
        forged_l2["rates"][key].update(errors=0, best=1e-9, low=0.0, high=1e-8)
        forged_l2["per_round"][key].update(best=1e-10, low=0.0, high=1e-9)
    r = submit(build_entry("LB2-forged", code=code, schedule_hash="deadbeef", l0_report={"passed": True, "d_circ": 99},
                           distance_upper_bound=99, l2=forged_l2), tmp)
    print("LB2 forged l0/l2 dict accepted:", r["l0"], r["l2"]["per_round"]["P_any"]["best"])

    g = sample_l2(code, circs, data, p=0.005, rounds=3, noise_model="gross_sd6", **kw)
    r = submit(build_entry("LB3-gross_sd6", code=code, circuits=circs, l0_report=l0, distance_upper_bound=3, l2=g), tmp)
    print("LB3 non-scoring noise model accepted:", r["noise_model"], "warnings:", r["l2"]["warnings"])

    r = submit(build_entry("LB4-hash-mismatch", code=code, circuits=circs5, l0_report=l0, distance_upper_bound=3,
                           l2=true), tmp)
    print("LB4 schedule_hash != l2.circuit.candidate_hash accepted:",
          r["schedule_hash"][:12], "vs", r["l2"]["circuit"]["candidate_hash"][:12])

    hi = sample_l2(code, circs, data, p=0.001, rounds=3, decoder=DecoderConfig("pymatching", {}), seed=1, stop=stop,
                   num_workers=1)
    r = submit(build_entry("LB7-other-p", code=code, circuits=circs, l0_report=l0, distance_upper_bound=3, l2=hi), tmp)
    print("LB7 different p on same board accepted:", r["p"])

    print("verify (intact):", verify_leaderboard(tmp))
    lines = tmp.read_text().splitlines(keepends=True)
    tmp.write_text("".join(lines[:2]))
    print("LB5 after deleting the last", len(lines) - 2, "lines, verify:", verify_leaderboard(tmp))

    tmp.write_text("".join(lines))
    recs = [json.loads(x) for x in lines]
    recs[0]["l2"]["per_round"]["P_any"]["best"] = 1e-12
    prev = "0" * 64
    for rec in recs:
        rec["prev_hash"] = prev
        rec["entry_hash"] = entry_hash(rec)
        prev = rec["entry_hash"]
    tmp.write_text("".join(json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
                           for x in recs))
    print("LB6 after rewriting line 1 and re-chaining, verify:", verify_leaderboard(tmp))


if __name__ == "__main__":
    main()
