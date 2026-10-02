"""S1 调度规范化 / 哈希：全局时间平移的规范化是否让两个不同电路得到同一哈希（或反过来）。

pipeline 用**候选提交的** spec 生成电路（circuit_hashes），但成绩单存的是 spec.canonical()，verify / reproduce_entry
从 canonical 重新生成电路。如果 unroll 的平移选择（总层数最少、并列取最小 σ）不是平移不变的，同一个哈希就对应两个
不同电路，而且 pipeline 在 L2 跑完后写榜时会被 entry_problems 拒绝（circuit hash mismatch）。

用法：uv run python s1_canonical_hash.py [trials]
"""
import random
import sys

from common import cand, circuit_hash, random_free_schedule, surface, deterministic


def shifted(spec, s):
    D = spec.period
    return cand.ScheduleSpec(D, tuple(cand._shift(c, s, D) for c in spec.x_checks),
                             tuple(cand._shift(c, s, D) for c in spec.z_checks))


def main(trials=300):
    code, std = surface(3)
    rng = random.Random(1)
    n_tested = n_coll = n_det_coll = 0
    example = None
    for t in range(trials):
        D = rng.randint(6, 10)
        spec = random_free_schedule(code, D, rng)
        if spec is None:
            continue
        n_tested += 1
        canon = spec.canonical()
        hs = {}
        for s in range(D):
            sp = shifted(spec, s)
            assert sp.hash() == spec.hash()
            hs[s] = circuit_hash(cand.build_circuits(sp, code, 3))
        if len(set(hs.values())) > 1:
            n_coll += 1
            det = deterministic(spec, code)
            n_det_coll += det
            if example is None and det:
                example = (spec, hs)
    print(f"random free schedules (d=3 surface, D in 6..10): {n_tested}")
    print(f"  same schedule_hash but >1 distinct circuits among its {''}global shifts: {n_coll}"
          f" (of which deterministic: {n_det_coll})")
    if example:
        spec, hs = example
        print("example schedule:", spec.to_dict())
        print("  circuit hash per shift:", {s: h[:12] for s, h in hs.items()})
        canon_h = circuit_hash(cand.build_circuits(spec.canonical(), code, 3))
        print("  submitted circuit == canonical circuit ?", hs[0] == canon_h)
        U0 = cand.unroll(spec, code, 3)
        Uc = cand.unroll(spec.canonical(), code, 3)
        print(f"  layers submitted {U0.num_layers} (sigma {U0.sigma}) vs canonical {Uc.num_layers} (sigma {Uc.sigma})")
        import json
        from pathlib import Path
        Path(__file__).with_name("s1_example_schedule.json").write_text(json.dumps(spec.to_dict()))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 300)
