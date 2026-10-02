"""攻击 L2-2：boundary="diff" 的短轮数电路由候选的 callable 给出，评估器既不对它跑 L0，也不检查它与
长轮数电路是“同一调度”。候选让 r1 的电路边界更差（这里：读出前多等 K 层空闲），P(r1) 变大，
差分得到的“体内每轮错误率”就被压低，甚至为负（best < 0，low 截断到 0）。

用法：uv run python a_l2_diff.py [K]
"""
import sys

import stim

from common import honest

from evaluators.l2 import DecoderConfig, StopRule, sample_l2


def with_wait(c: stim.Circuit, k: int) -> stim.Circuit:
    """在最后一个 TICK 之后（最终读出所在层之前）插入 k 个空层。"""
    flat = c.flattened()
    idx = max(i for i, inst in enumerate(flat) if inst.name == "TICK")
    out = stim.Circuit()
    for i, inst in enumerate(flat):
        out.append(inst)
        if i == idx:
            for _ in range(k):
                out.append("TICK")
    return out


def main():
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    d, r1, r2 = 3, 3, 9
    code, data, _ = honest(d, r2)

    def honest_fn(b, r):
        return honest(d, r)[2][b]

    def cheat_fn(b, r):
        c = honest(d, r)[2][b]
        return with_wait(c, K) if r == r1 else c

    stop = StopRule(max_shots=400_000, max_errors=3000, min_sector_errors=1500, batch_size=4000)
    for name, fn in (("honest", honest_fn), (f"r1 circuit padded with {K} idle layers", cheat_fn)):
        res = sample_l2(code, fn, data, p=0.005, rounds=r2, boundary="diff", diff_rounds=r1,
                        decoder=DecoderConfig("pymatching"), seed=11, stop=stop, num_workers=3)
        pr = res.per_round["P_any"]
        print(f"=== {name}: diff per-round P_any best={pr['best']:.4e} [{pr['low']:.4e}, {pr['high']:.4e}] "
              f"low_unclipped={pr['diff']['low_unclipped']:.4e}; candidate_hash={res.circuit['candidate_hash']}")
        print("    warnings:", res.warnings)


if __name__ == "__main__":
    main()
