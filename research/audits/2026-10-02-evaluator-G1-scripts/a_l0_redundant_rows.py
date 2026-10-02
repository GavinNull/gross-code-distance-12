"""L0-2：冗余校验行可以完全不测（每一轮都不测），L0 仍判“每个生成元恰好测了 rounds 次”。
码：表面码 d=3 + 一个冗余 Z 行 + 一个冗余 X 行（同 tests/test_l0.py::test_redundant_stabilizer_rows_are_supported）。
电路：tests/memory_builder.build_memory，用 skip 让冗余行的辅助比特在所有轮都不做任何操作。
这不是“骗分”本身，而是需要 PI 裁决的口径：gross code 的 HX/HZ 各有 6 个冗余行，候选可以少用 12 个辅助比特、
少做 12×6 个 CNOT / 轮，而与“每轮测全部 72+72 行”的 IBM 电路在同一个榜上比较。

用法：uv run python a_l0_redundant_rows.py
"""
import sys
from pathlib import Path

import numpy as np

from common import ROOT  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests"))
from memory_builder import build_memory  # noqa: E402

from evaluators.codes import CSSCode, rotated_surface_code_from_stim  # noqa: E402
from evaluators.l0 import L0Constraints, check_l0  # noqa: E402


def main():
    code0, _, _ = rotated_surface_code_from_stim(3, "Z")
    HZ = np.vstack([code0.HZ, code0.HZ[0] ^ code0.HZ[1]])
    HX = np.vstack([code0.HX, code0.HX[1] ^ code0.HX[2]])
    code = CSSCode(HX, HZ, code0.LX, code0.LZ)
    R = 3
    skip = {(r, "Z", HZ.shape[0] - 1) for r in range(R)} | {(r, "X", HX.shape[0] - 1) for r in range(R)}
    for basis in "ZX":
        full, data = build_memory(code, basis, R, detectors="both")
        lean, _ = build_memory(code, basis, R, detectors="both", skip=skip)
        n2 = lambda c: sum(len(i.target_groups()) for i in c.flattened() if i.name == "CX")  # noqa: E731
        for name, c in (("all rows", full), ("redundant rows never measured", lean)):
            r = check_l0(c, code, basis, L0Constraints(data_qubits=data, rounds=R, require_opposite_type_detectors=True,
                                                      min_circuit_distance=3, distance_bposd_trials=200,
                                                      distance_lns_starts=8))
            cov = r.get("stabilizer_coverage")
            print(f"{basis} {name}: L0 passed={r.passed} d_circ={r.d_circ} CX count={n2(c)} "
                  f"counts={cov.details.get('counts')}")


if __name__ == "__main__":
    main()
