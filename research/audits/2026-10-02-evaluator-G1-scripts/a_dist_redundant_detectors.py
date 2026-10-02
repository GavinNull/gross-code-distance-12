"""攻击 D1：用冗余 detector（已有 detector 的 GF(2) 组合）把每个故障的症状“加粗”，
让距离上界的四路搜索找不到真实的短逻辑错误，使距离不达标的调度通过 min_circuit_distance。

对象：tests/memory_builder.build_memory 的 X 基底 d=5 表面码电路（README 攻击表里“合法但调度差，距离 5 -> 3”）。
冗余 detector 是确定的（determinism 通过）、不改变 detector 张成（coverage 通过）、不改变真实电路距离，
L0 也不检查 detector 是否多余（README §5 已知局限）。

用法：uv run python a_dist_redundant_detectors.py [extra_per_det] [seed]
"""
import sys
from pathlib import Path

import numpy as np
import stim

from common import ROOT  # noqa: F401  (sys.path)

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests"))
from memory_builder import build_memory  # noqa: E402

from evaluators.codes import rotated_surface_code_from_stim  # noqa: E402
from evaluators.distance import lower_bound  # noqa: E402
from evaluators.l0 import L0Constraints, check_l0  # noqa: E402
from evaluators.noise import add_noise  # noqa: E402

extra = int(sys.argv[1]) if len(sys.argv) > 1 else 8
seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
code, _, _ = rotated_surface_code_from_stim(5, "Z")
cx, data = build_memory(code, "X", 5)


def detector_sets(c: stim.Circuit):
    out = []
    m = 0
    for inst in c.flattened():
        if inst.name == "DETECTOR":
            out.append(frozenset(m + t.value for t in inst.targets_copy()))
        elif inst.name != "OBSERVABLE_INCLUDE":
            tmp = stim.Circuit(); tmp.append(inst); m += tmp.num_measurements
    return out, m


def add_redundant(c: stim.Circuit, extra: int, rng) -> stim.Circuit:
    dets, M = detector_sets(c)
    out = c.flattened().copy()
    for _ in range(extra * len(dets)):
        k = rng.integers(2, 6)
        pick = rng.choice(len(dets), size=k, replace=False)
        s = frozenset()
        for i in pick:
            s = s ^ dets[i]
        if s:
            out.append("DETECTOR", [stim.target_rec(r - M) for r in sorted(s)])
    return out


rng = np.random.default_rng(seed)
cx_red = add_redundant(cx, extra, rng)

def main():
    print(f"detectors: original {cx.num_detectors}, padded {cx_red.num_detectors}")
    for name, c in (("bad schedule", cx), ("bad schedule + redundant detectors", cx_red)):
        cons = L0Constraints(data_qubits=data, rounds=5, min_circuit_distance=5, distance_seed=seed,
                             distance_early_stop=False, distance_num_workers=1)   # 默认预算
        r = check_l0(c, code, "X", cons)
        print(f"=== {name}: passed={r.passed} d_circ={r.d_circ}")
        print(r.get("circuit_distance").message[:600])
        for c2 in r.checks:
            if c2.status != "pass":
                print("   ", c2.name, c2.status, c2.message[:200])

    # 独立核对：真实距离（精确下界）
    lb = lower_bound(add_noise(cx_red, "sd6", 1e-3), method="cpsat", time_limit_s=120, target=5)
    print("exact check on padded circuit (target=5):", lb.status, "lower_bound", lb.lower_bound, "ub", lb.upper_bound)


if __name__ == "__main__":
    main()
