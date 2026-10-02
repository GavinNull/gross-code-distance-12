"""G1 评估器攻击：共用的电路构造器（只读调用 evaluators/，不修改）。"""
from __future__ import annotations

import sys
from pathlib import Path

import stim

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from evaluators.codes import rotated_surface_code_from_stim  # noqa: E402
from evaluators.l0 import L0Constraints  # noqa: E402

FAST_DIST = dict(distance_bposd_trials=300, distance_lns_starts=16)


def edges(*circs):
    out = set()
    for c in circs:
        for i in c.flattened():
            if i.name in ("CX", "CZ"):
                for g in i.target_groups():
                    out.add(tuple(t.value for t in g))
    return out


def honest(d: int, rounds: int):
    """stim 生成的旋转表面码 memory 电路（无噪声），两个基底。"""
    code, data, cz = rotated_surface_code_from_stim(d, "Z", rounds)
    _, _, cx = rotated_surface_code_from_stim(d, "X", rounds)
    return code, data, {"Z": cz, "X": cx}


def cons_for(data, circs, rounds, **kw):
    allc = list(circs.values())
    base = dict(data_qubits=data, max_qubits=max(c.num_qubits for c in allc), allowed_edges=edges(*allc),
                rounds=rounds, require_opposite_type_detectors=True, **FAST_DIST)
    base.update(kw)
    return L0Constraints(**base)


def fake_rounds(d: int, basis: str, rounds: int) -> stim.Circuit:
    """攻击 A1：只做 1 轮真正的 syndrome 提取（辅助比特用 M 而不是 MR），之后 rounds-1 轮
    只是把同一批辅助比特再测一遍（不再与数据比特相互作用）。每次重测都与上一次比较作为 detector。"""
    c = stim.Circuit.generated("surface_code:rotated_memory_" + basis.lower(), distance=d, rounds=1).flattened()
    out = stim.Circuit()
    anc: list[int] | None = None
    pending_insert = False
    for inst in c:
        if inst.name == "MR":
            anc = [t.value for t in inst.targets_copy()]
            out.append("M", anc)
            pending_insert = True
            continue
        if pending_insert and inst.name != "DETECTOR":
            # 第一轮的 detector 已经写完：插入 rounds-1 层“重测”
            na = len(anc)
            for _ in range(rounds - 1):
                out.append("TICK")
                out.append("M", anc)
                for i in range(na):
                    out.append("DETECTOR", [stim.target_rec(-na + i), stim.target_rec(-2 * na + i)])
            out.append("TICK")
            pending_insert = False
        out.append(inst)
    return out


def fake_pair(d: int, rounds: int):
    code, data, _ = honest(d, 2)
    return code, data, {"Z": fake_rounds(d, "Z", rounds), "X": fake_rounds(d, "X", rounds)}


def fake_rounds_early_readout(d: int, basis: str, rounds: int) -> stim.Circuit:
    """攻击 A1b：同 A1，但数据比特在唯一一轮真提取后立刻最终读出，rounds-1 层“重测辅助比特”放在读出之后。
    paper 口径去掉数据比特读出层之后的全部噪声，所以“假轮次”期间数据比特完全无噪声。"""
    c = stim.Circuit.generated("surface_code:rotated_memory_" + basis.lower(), distance=d, rounds=1).flattened()
    out = stim.Circuit()
    anc = None
    for inst in c:
        if inst.name == "MR":
            anc = [t.value for t in inst.targets_copy()]
            out.append("M", anc)
        else:
            out.append(inst)
    na = len(anc)
    # 最后一层：辅助比特 M + 数据 M。之后再加 rounds-1 层辅助比特重测。
    for r in range(rounds - 1):
        out.append("TICK")
        out.append("M", anc)
        # 与上一次辅助比特测量比较（第一次重测要跨过数据读出的 n 个记录）
        back = na + (len(set(range(c.num_qubits))) and 0)
        for i in range(na):
            prev = -2 * na + i if r > 0 else None
            if r == 0:
                n_data = d * d
                prev = -(na + n_data + na) + i
            out.append("DETECTOR", [stim.target_rec(-na + i), stim.target_rec(prev)])
    return out


def fake_early_pair(d: int, rounds: int):
    code, data, _ = honest(d, 2)
    return code, data, {b: fake_rounds_early_readout(d, b, rounds) for b in "ZX"}
