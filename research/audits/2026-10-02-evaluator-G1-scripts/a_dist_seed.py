"""距离 D2：L0 距离判定对 seed / num_workers 的依赖。

在 a_dist_redundant_detectors 的“坏调度 + 冗余 detector”电路上（graphlike / stim_search 已失明，只剩 BP-OSD），
用较小预算扫 seed，看 L0 的 pass/fail 是否随 seed 改变；再看同一 seed 下 num_workers=1 与 3 是否相同。
预算小是为了让效应可见；默认预算下同样的现象出现在更大的电路上（README §3.1：gross 上 600 次 BP-OSD
时 9 个种子里有 1–2 个停在 11）。

用法：uv run python a_dist_seed.py
"""
import numpy as np

import a_dist_redundant_detectors as base  # noqa: F401  (重用电路；该模块顶层会先跑一次，耗时约 1 分钟)


def main():
    from evaluators.l0 import L0Constraints, check_l0
    c = base.cx_red
    rows = []
    for seed in range(8):
        cons = L0Constraints(data_qubits=base.data, rounds=5, min_circuit_distance=5, distance_seed=seed,
                             distance_bposd_trials=25, distance_lns_starts=0, distance_early_stop=False)
        r = check_l0(c, base.code, "X", cons)
        rows.append((seed, r.passed, r.d_circ))
        print(f"seed {seed}: L0 passed={r.passed} d_circ={r.d_circ}", flush=True)
    for w in (1, 3):
        cons = L0Constraints(data_qubits=base.data, rounds=5, min_circuit_distance=5, distance_seed=3,
                             distance_bposd_trials=150, distance_lns_starts=4, distance_early_stop=False,
                             distance_num_workers=w)
        r = check_l0(c, base.code, "X", cons)
        print(f"workers {w} (seed 3, 150 trials): passed={r.passed} d_circ={r.d_circ} "
              f"{r.get('circuit_distance').details.get('methods') and [m['method'] + ':' + str(m['weight']) for m in r.get('circuit_distance').details['methods']]}")


if __name__ == "__main__":
    main()
