"""攻击 N1：SI1000 的 ResonatorIdle（2p）只加在“本层没被任何操作作用”的比特上；显式 I 门算“操作”，
只付 p/10。所以在每个含测量/复位的层里给所有空闲比特写一个 I，就把这些层里 2p 的空闲噪声换成 p/10。
I 是恒等，逻辑电路不变；L0 默认门集允许 I。

电路：stim 旋转表面码改写为 SI1000 原生门（CX(c,t) -> H t; CZ c t; H t），两个基底。
用法：uv run python a_si1000_identity.py [d] [rounds] [--l2]
"""
import sys

import stim

from common import cons_for, honest

from evaluators.l0 import check_l0
from evaluators.l2 import DecoderConfig, StopRule, build_joint_circuit, sample_l2
from evaluators.noise import split_layers

ANN = ("DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS")


def to_cz(c: stim.Circuit) -> stim.Circuit:
    out = stim.Circuit()
    for li, layer in enumerate(split_layers(c)):
        if li:
            out.append("TICK")
        cx = [inst for inst in layer if inst.name == "CX"]
        rest = [inst for inst in layer if inst.name != "CX"]
        if cx:
            assert not [i for i in rest if i.name not in ANN]
            tg = [g[1].value for inst in cx for g in inst.target_groups()]
            pairs = [t.value for inst in cx for g in inst.target_groups() for t in g]
            out.append("H", tg); out.append("TICK")
            out.append("CZ", pairs); out.append("TICK")
            out.append("H", tg)
            for inst in rest:
                out.append(inst)
        else:
            for inst in layer:
                out.append(inst)
    return out


def pad_identity_in_mr_layers(c: stim.Circuit) -> stim.Circuit:
    layers = split_layers(c)
    allq = {t.value for L in layers for i in L if i.name not in ANN for t in i.targets_copy() if t.is_qubit_target}
    out = stim.Circuit()
    for li, layer in enumerate(layers):
        if li:
            out.append("TICK")
        touched = {t.value for i in layer if i.name not in ANN for t in i.targets_copy() if t.is_qubit_target}
        has_mr = any(stim.gate_data(i.name).is_reset or stim.gate_data(i.name).produces_measurements
                     for i in layer if i.name not in ANN)
        for i in layer:          # 保持原顺序（detector 的 rec[-k] 依赖它）；I 不产生测量记录，放在层尾
            out.append(i)
        if has_mr and allq - touched:
            out.append("I", sorted(allq - touched))
    return out


def prior(jc):
    return sum(i.args_copy()[0] for i in jc.circuit.detector_error_model().flattened() if i.type == "error")


def main():
    d = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    R = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    code, data, hon = honest(d, R)
    cz = {b: to_cz(hon[b]) for b in "ZX"}
    padded = {b: pad_identity_in_mr_layers(cz[b]) for b in "ZX"}
    cons = cons_for(data, {**cz, "pz": padded["Z"], "px": padded["X"]}, R, min_circuit_distance=d)
    for name, circs in (("CZ circuit", cz), ("CZ circuit + I on idle qubits in M/R layers", padded)):
        rep = check_l0(circs, code, "both", cons)
        print(f"{name}: L0 passed={rep.passed} d_circ={rep.d_circ}")
    for b in ("paper", "flat"):
        a, p_ = build_joint_circuit(code, cz, data, p=0.002, noise_model="si1000", boundary=b), \
            build_joint_circuit(code, padded, data, p=0.002, noise_model="si1000", boundary=b)
        print(f"si1000 {b}: Σprior honest {prior(a):.4f}  I-padded {prior(p_):.4f}  ratio {prior(p_) / prior(a):.3f}")
    a, p_ = build_joint_circuit(code, cz, data, p=0.002, noise_model="sd6"), \
        build_joint_circuit(code, padded, data, p=0.002, noise_model="sd6")
    print(f"sd6 paper (control): Σprior honest {prior(a):.4f}  I-padded {prior(p_):.4f}")
    if "--l2" in sys.argv:
        stop = StopRule(max_shots=2_000_000, max_errors=2000, min_sector_errors=600, batch_size=10000)
        for name, circs in (("honest", cz), ("I-padded", padded)):
            res = sample_l2(code, circs, data, p=0.002, rounds=R, noise_model="si1000",
                            decoder=DecoderConfig("pymatching"), seed=5, stop=stop, num_workers=3)
            print("===", name)
            print(res.summary())




def direct():
    """不经 L0 / L2（两者都拒绝“数据比特在 CZ 前后有 H”的 SI1000 原生电路，见报告 N2），
    直接用 evaluators.noise.add_noise 给单基底 Z memory 加 si1000 噪声，比较 DEM 与逻辑错误率。"""
    import sinter
    from evaluators.noise import add_noise
    d = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    code, data, hon = honest(d, d)
    base = to_cz(hon["Z"])
    pad = pad_identity_in_mr_layers(base)
    tasks = []
    for name, c in (("honest", base), ("I-padded", pad)):
        noisy = add_noise(c, "si1000", 0.002)
        s = sum(i.args_copy()[0] for i in noisy.detector_error_model(decompose_errors=False).flattened()
                if i.type == "error")
        n_res = str(noisy).count("DEPOLARIZE1") 
        print(f"{name}: Σprior={s:.4f}")
        tasks.append(sinter.Task(circuit=noisy, json_metadata={"name": name}))
    stats = sinter.collect(num_workers=3, tasks=tasks, decoders=["pymatching"], max_shots=2_000_000,
                           max_errors=1500)
    for st in stats:
        print(f"=== {st.json_metadata['name']}: {st.errors}/{st.shots} = {st.errors / st.shots:.4e}")


if __name__ == "__main__":
    direct() if "--direct" in sys.argv else main()
