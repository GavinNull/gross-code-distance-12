"""L2 可复现性独立核对：同 seed、不同 num_workers、错误数停止规则（sinter 波次会多算、被丢弃）下计数是否逐位相同；
以及“换种子挑最好”的选择性报告空间有多大（同一电路 8 个种子的每轮 P_any 分布，小样本停止规则）。
用法：uv run python a_l2_repro.py
"""
from common import honest

from evaluators.l2 import DecoderConfig, StopRule, sample_l2


def main():
    code, data, circs = honest(3, 3)
    kw = dict(p=0.005, rounds=3, decoder=DecoderConfig("pymatching"),
              stop=StopRule(max_shots=10**6, max_errors=500, min_sector_errors=200, batch_size=500))
    a = sample_l2(code, circs, data, seed=42, num_workers=1, **kw)
    b = sample_l2(code, circs, data, seed=42, num_workers=3, **kw)
    print("workers 1:", a.counts, "discarded", a.reproducibility["batches_discarded_beyond_prefix"][:5])
    print("workers 3:", b.counts, "discarded", b.reproducibility["batches_discarded_beyond_prefix"][:5])
    print("identical:", a.counts == b.counts and a.rates == b.rates)
    small = StopRule(max_shots=2000, batch_size=500)
    vals = []
    for s in range(8):
        r = sample_l2(code, circs, data, p=0.005, rounds=3, decoder=DecoderConfig("pymatching"), stop=small,
                      seed=s, num_workers=1)
        vals.append((r.per_round["P_any"]["best"], s, r.counts["fail_any"], r.warnings[:1]))
    vals.sort()
    print("seed shopping with 2000-shot runs (per-round P_any, seed, failures):", [(f"{v:.4f}", s, f) for v, s, f, _ in vals])
    print("best/worst ratio:", vals[0][0] / vals[-1][0], "| the leaderboard accepts any of them (warning only)")


if __name__ == "__main__":
    main()
