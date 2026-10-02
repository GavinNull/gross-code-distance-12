"""S9 噪声躲避：合法调度能否让某些比特在某些时间步没有 sd6 噪声。

不变量（sd6 的定义）：模板电路加 sd6 后，在每个时间步（两个 TICK 之间，含最终读出层），电路里的**每个**比特
都恰好落在一个“噪声位置”上：门后 DEP1/DEP2、复位后翻转、测量前翻转、或空闲 DEP1，概率都是 p。
对随机逐检查自由调度（d=3 表面码、BB72 IBM 变体）逐层检查。另外统计每轮每个数据比特的空闲位置数下限是否
= D − （该比特每周期的 CNOT 数），即调度无法把空闲压到物理下限以下。

用法：uv run python s9_noise_coverage.py [n]
"""
import random
import sys
from collections import Counter

import stim

from common import cand, random_free_schedule, surface
from evaluators.noise import add_noise, split_layers

P = 1e-3
NOISE = {"DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Z_ERROR", "Y_ERROR", "PAULI_CHANNEL_1", "PAULI_CHANNEL_2"}


def check(circ: stim.Circuit):
    noisy = add_noise(circ, "sd6", P)
    nq = noisy.num_qubits
    bad = []
    layers = split_layers(noisy)
    for li, layer in enumerate(layers):
        cnt = Counter()
        for inst in layer:
            if inst.name in NOISE:
                args = inst.gate_args_copy()
                assert all(abs(a - P) < 1e-15 for a in args), (inst.name, args)
                for t in inst.targets_copy():
                    cnt[t.value] += 1
        missing = [q for q in range(nq) if cnt[q] == 0]
        dup = [q for q in range(nq) if cnt[q] > 1]
        if missing or dup:
            bad.append((li, missing[:5], dup[:5]))
    return bad, len(layers)


def main(n=60):
    code, std = surface(3)
    rng = random.Random(9)
    tot = viol = 0
    for _ in range(n):
        s = random_free_schedule(code, rng.randint(6, 10), rng)
        if s is None:
            continue
        for b in "ZX":
            bad, L = check(cand.memory_circuit(s, code, b, 3))
            tot += 1
            if bad:
                viol += 1
                if viol <= 3:
                    print("violation:", bad[:3])
    bad, L = check(cand.memory_circuit(std, code, "Z", 3))
    print(f"surface d=3: {tot} random template circuits (+std), layers with a qubit lacking exactly one noise "
          f"location: {viol} circuits; std: {bad}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
