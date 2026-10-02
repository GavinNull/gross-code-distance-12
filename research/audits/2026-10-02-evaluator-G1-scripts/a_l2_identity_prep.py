"""攻击 L2-1：paper 口径下，在每个数据比特第一个双比特门之前插一个 I 门，
把“复位到第一个 CNOT 之间”的数据空闲噪声变成“制备”，被 paper 口径整段去掉。

同一个逻辑电路（I 门是恒等），噪声总量却变少。比较联合电路 DEM 的总先验与机制数（精确，无采样）。
可选 --l2：用 pymatching 采样比较 P_any。

用法：uv run python a_l2_identity_prep.py [d] [rounds] [--l2]
"""
import sys

import stim

from common import cons_for, honest

from evaluators.l0 import check_l0
from evaluators.l2 import DecoderConfig, StopRule, build_joint_circuit, sample_l2

d = int(sys.argv[1]) if len(sys.argv) > 1 else 5
R = int(sys.argv[2]) if len(sys.argv) > 2 else 5


def pad_identity(c: stim.Circuit, data) -> stim.Circuit:
    """在每个数据比特第一个双比特门所在层的前一层放一个 I（该比特在那一层本来空闲）。"""
    flat = c.flattened()
    layers = [[]]
    for inst in flat:
        if inst.name == "TICK":
            layers.append([])
        else:
            layers[-1].append(inst)
    first2 = {}
    for li, L in enumerate(layers):
        for inst in L:
            if stim.gate_data(inst.name).is_two_qubit_gate:
                for g in inst.target_groups():
                    for t in g:
                        if t.value in data and t.value not in first2:
                            first2[t.value] = li
    touched = [set(t.value for inst in L for t in inst.targets_copy() if t.is_qubit_target
                   and inst.name not in ("DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS"))
               for L in layers]
    add = {}
    for q, li in first2.items():
        if li - 1 >= 0 and q not in touched[li - 1]:
            add.setdefault(li - 1, []).append(q)
    out = stim.Circuit()
    for li, L in enumerate(layers):
        if li:
            out.append("TICK")
        for inst in L:
            out.append(inst)
        if li in add:
            out.append("I", sorted(add[li]))
    return out, sum(len(v) for v in add.values())


def total_prior(jc):
    dem = jc.circuit.detector_error_model(allow_gauge_detectors=False)
    s = 0.0
    n = 0
    for inst in dem.flattened():
        if inst.type == "error":
            s += inst.args_copy()[0]
            n += 1
    return s, n



def main():
    code, data, hon = honest(d, R)
    pad = {}
    for b in "ZX":
        pad[b], nadd = pad_identity(hon[b], set(data))
    print(f"inserted {nadd} I gates per basis")
    cons = cons_for(data, {**hon, "pZ": pad["Z"], "pX": pad["X"]}, R, min_circuit_distance=d)
    rep = check_l0(pad, code, "both", cons)
    print("padded L0 passed:", rep.passed, "d_circ", rep.d_circ)
    for boundary in ("paper", "flat"):   # noisy 口径直接拒绝 R+I 的制备
        a = build_joint_circuit(code, hon, data, p=0.005, boundary=boundary)
        b = build_joint_circuit(code, pad, data, p=0.005, boundary=boundary)
        sa, na = total_prior(a)
        sb, nb = total_prior(b)
        print(f"{boundary:6s}: honest Σprior={sa:.4f} ({na} mech)  I-padded Σprior={sb:.4f} ({nb} mech)  "
              f"ratio={sb / sa:.4f}")

    if "--l2" in sys.argv:
        stop = StopRule(max_shots=400_000, max_errors=2000, min_sector_errors=1000, batch_size=4000)
        for name, circs in (("honest", hon), ("I-padded", pad)):
            res = sample_l2(code, circs, data, p=0.007, rounds=R, boundary="paper",
                            decoder=DecoderConfig("pymatching"), seed=7, stop=stop, num_workers=3)
            print("===", name)
            print(res.summary())


if __name__ == "__main__":
    main()
