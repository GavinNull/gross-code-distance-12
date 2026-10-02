"""测试用：把 baselines 的 Schedule、stim 的表面码电路转换成候选调度 JSON（evaluators/candidate.py 的规范）。

评估器本身不 import baselines；只有测试为了逐机制对照才 import。
"""
from __future__ import annotations

import numpy as np
import stim

from evaluators.candidate import CheckTiming, ScheduleSpec
from evaluators.codes import CSSCode, rotated_surface_code_from_stim


def from_baseline(sched) -> ScheduleSpec:
    """baselines.schedule.Schedule（循环层格式）-> ScheduleSpec。"""
    col = {q: j for j, q in enumerate(sched.data)}

    def one(q, is_x):
        tp = next(t for t, L in enumerate(sched.layers) if q in (L.prep_x if is_x else L.prep_z))
        tm = next(t for t, L in enumerate(sched.layers) if q in (L.meas_x if is_x else L.meas_z))
        cn = []
        for t, L in enumerate(sched.layers):
            for a, b in L.cnots:
                if q == a:
                    cn.append((col[b], t))
                elif q == b:
                    cn.append((col[a], t))
        return CheckTiming(tp, tm, tuple(sorted(cn)))

    return ScheduleSpec(sched.depth, tuple(one(q, True) for q in sched.x_checks),
                        tuple(one(q, False) for q in sched.z_checks))


def surface_schedule(d: int) -> tuple[CSSCode, ScheduleSpec]:
    """旋转表面码（stim 的生成器）+ 它的标准 CNOT 顺序（4 个 CNOT 层），周期 6：
    prep 0，CNOT 1..4（按 stim 电路中 CX 层的先后），meas 5。码的行序与 rotated_surface_code_from_stim 相同。"""
    code, data, circ = rotated_surface_code_from_stim(d, "Z", 2)
    col = {q: j for j, q in enumerate(data)}
    flat = circ.flattened()
    cx_layer = 0
    times: dict[int, dict[int, int]] = {}
    h_qubits = set()
    for inst in flat:
        if inst.name == "H":
            h_qubits.update(t.value for t in inst.targets_copy())
        if inst.name == "CX":
            cx_layer += 1
            for a, b in inst.target_groups():
                a, b = a.value, b.value
                anc, dq = (a, b) if a not in col else (b, a)
                times.setdefault(anc, {})[col[dq]] = cx_layer
        if inst.name in ("MR", "M") and cx_layer >= 4:
            break
    xs, zs = [], []
    for anc in sorted(times):
        (xs if anc in h_qubits else zs).append(anc)

    def row_of(anc):
        v = np.zeros(code.n, dtype=np.uint8)
        v[list(times[anc])] = 1
        return v

    def ordered(ancs, H):
        out = []
        for i in range(H.shape[0]):
            a = next(a for a in ancs if np.array_equal(row_of(a), H[i]))
            out.append(CheckTiming(0, 5, tuple(sorted(times[a].items()))))
        return tuple(out)

    return code, ScheduleSpec(6, ordered(xs, code.HX), ordered(zs, code.HZ))


def dem_mechanisms(circuit: stim.Circuit) -> dict:
    """{(detectors, observables): 合并后的概率}（相同症状的机制按独立异或合并）。"""
    out: dict = {}
    for inst in circuit.detector_error_model(allow_gauge_detectors=False).flattened():
        if inst.type != "error":
            continue
        p = inst.args_copy()[0]
        dets, obs = [], []
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                dets.append(t.val)
            elif t.is_logical_observable_id():
                obs.append(t.val)
        key = (tuple(sorted(dets)), tuple(sorted(obs)))
        q = out.get(key, 0.0)
        out[key] = q + p - 2 * q * p
    return out


def max_dem_difference(a: stim.Circuit, b: stim.Circuit) -> tuple[float, int, int]:
    ma, mb = dem_mechanisms(a), dem_mechanisms(b)
    keys = set(ma) | set(mb)
    return max(abs(ma.get(k, 0.0) - mb.get(k, 0.0)) for k in keys), len(ma), len(mb)
