"""测试用：给任意 CSSCode 生成一个简单（不追求距离）的 memory 电路，并支持各种“作弊”变体。

布局：数据比特 0..n-1；Z 辅助比特 n..n+mz-1；X 辅助比特 n+mz..n+mz+mx-1。
每轮：复位辅助比特 → H(X 辅助) → 所有 Z 检查的 CNOT（贪心分层）→ 所有 X 检查的 CNOT → H → 测量。
Z 检查全部完成后才开始 X 检查，所以任意 CSS 码都对易、确定。这不是一个好调度（hook 方向随意），
只用于 L0 的合法性/攻击测试。
"""
from __future__ import annotations

import numpy as np
import stim

from evaluators.codes import CSSCode


def _layers(pairs):
    layers: list[list[tuple[int, int]]] = []
    busy: list[set[int]] = []
    for a, b in pairs:
        for li, used in enumerate(busy):
            if a not in used and b not in used:
                layers[li].append((a, b))
                used.update((a, b))
                break
        else:
            layers.append([(a, b)])
            busy.append({a, b})
    return layers


def build_memory(code: CSSCode, basis: str, rounds: int, *,
                 skip: set[tuple[int, str, int]] = frozenset(),
                 skip_type: str | None = None,
                 detectors: str = "basis",
                 destroy_after_round: int | None = None,
                 observable_rows=None) -> tuple[stim.Circuit, list[int]]:
    """skip: {(round, 'X'|'Z', check_index)} 不测量的检查（detector 会跳过它，与上一次测量比较）。
    skip_type: 整类检查永远不测（例如 'X'：只测 Z 的“重复码”式作弊）。
    destroy_after_round: 该轮之后把数据比特测量再复位（摧毁逻辑信息），只保留 basis 型 detector。
    observable_rows: 覆盖 observable 的数据列集合（list of list）。
    """
    n = code.n
    mz, mx = code.HZ.shape[0], code.HX.shape[0]
    data = list(range(n))
    zanc = [n + i for i in range(mz)]
    xanc = [n + mz + i for i in range(mx)]
    c = stim.Circuit()
    c.append("R" if basis == "Z" else "RX", data)
    c.append("TICK")
    meas = 0
    last: dict[tuple[str, int], int] = {}

    def checks(typ):
        if skip_type == typ:
            return []
        H = code.HZ if typ == "Z" else code.HX
        return list(range(H.shape[0]))

    for r in range(rounds):
        zs = [i for i in checks("Z") if (r, "Z", i) not in skip]
        xs = [i for i in checks("X") if (r, "X", i) not in skip]
        za = [zanc[i] for i in zs]
        xa = [xanc[i] for i in xs]
        if za + xa:
            c.append("R", za + xa)
            c.append("TICK")
        if xa:
            c.append("H", xa)
            c.append("TICK")
        zpairs = [(q, zanc[i]) for i in zs for q in np.flatnonzero(code.HZ[i])]
        for layer in _layers(zpairs):
            c.append("CX", [x for pr in layer for x in pr])
            c.append("TICK")
        xpairs = [(xanc[i], q) for i in xs for q in np.flatnonzero(code.HX[i])]
        for layer in _layers(xpairs):
            c.append("CX", [x for pr in layer for x in pr])
            c.append("TICK")
        if xa:
            c.append("H", xa)
            c.append("TICK")
        order = [("Z", i) for i in zs] + [("X", i) for i in xs]
        if order:
            c.append("M", za + xa)
        base = meas
        meas += len(order)
        for j, (typ, i) in enumerate(order):
            cur = base + j
            want = typ == basis or (detectors == "both")
            if want:
                prev = last.get((typ, i))
                if prev is not None:
                    c.append("DETECTOR", [stim.target_rec(cur - meas), stim.target_rec(prev - meas)])
                elif typ == basis:
                    c.append("DETECTOR", [stim.target_rec(cur - meas)])
            last[(typ, i)] = cur
        c.append("TICK")
        if destroy_after_round == r:
            c.append("M" if basis == "Z" else "MX", data)
            meas += n
            c.append("TICK")
            c.append("R" if basis == "Z" else "RX", data)
            c.append("TICK")
            # 摧毁后对面类型检查的历史作废
            for key in [k for k in last if k[0] != basis]:
                del last[key]
    c.append("M" if basis == "Z" else "MX", data)
    meas += n
    H = code.HZ if basis == "Z" else code.HX
    for i in range(H.shape[0]):
        if (basis, i) not in last:
            continue
        tg = [stim.target_rec(q - n) for q in np.flatnonzero(H[i])]
        tg.append(stim.target_rec(last[(basis, i)] - meas))
        c.append("DETECTOR", tg)
    L = code.LZ if basis == "Z" else code.LX
    rows = observable_rows if observable_rows is not None else [np.flatnonzero(L[j]).tolist() for j in range(L.shape[0])]
    for j, cols in enumerate(rows):
        c.append("OBSERVABLE_INCLUDE", [stim.target_rec(q - n) for q in cols], j)
    return c, data


def build_pipelined_memory(code: CSSCode, basis: str, rounds: int, *,
                           skip: set[tuple[int, str, int]] = frozenset(),
                           drop_cnot: tuple[int, str, int, int] | None = None,
                           drop_final_flush: bool = False,
                           drop_first_round_detectors: bool = False) -> tuple[stim.Circuit, list[int]]:
    """跨轮流水（没有“干净切口”）的 memory 电路，用于测试 L0 的 flow 覆盖检查。

    与 build_memory 同一布局、同样的 Z 相 → X 相顺序，但辅助比特的测量推迟到下一相：
      第 r 轮：[R Z辅助 + H X辅助(r-1)] → [M X辅助(r-1) + 第 1 层 Z CNOT] → 其余 Z CNOT 层
              → [R X辅助] → [H X辅助] → [M Z辅助 + 第 1 层 X CNOT] → 其余 X CNOT 层
    所以任何 TICK 处都至少有一类辅助比特处于纠缠中（最后一轮之后才排空：H、M X 辅助比特，再读出数据）。
    detector 约定同 build_memory（basis 型：首轮单独、相邻轮比较、末轮与读出比较）。

    作弊变体：
      skip: {(round, 'X'|'Z', i)} 该轮不做这个检查（detector 跨轮比较）。
      drop_cnot: (round, type, i, data_col) 该轮检查 i 少做一个 CNOT（只测到 s 去掉一个比特）；
                 basis 型在第 0 轮仍是确定的（单独 detector），下一轮重新从单独 detector 开始，全部确定。
      drop_final_flush: 排空阶段不测最后一轮的 X 辅助比特（X 型稳定子少测一轮）。
      drop_first_round_detectors: 删掉灌入阶段（第 0 轮）basis 型的单独 detector。
    """
    n = code.n
    mz, mx = code.HZ.shape[0], code.HX.shape[0]
    data = list(range(n))
    zanc = [n + i for i in range(mz)]
    xanc = [n + mz + i for i in range(mx)]
    c = stim.Circuit()
    c.append("R" if basis == "Z" else "RX", data)
    c.append("TICK")
    meas = 0
    last: dict[tuple[str, int], int] = {}
    pending_x: list[int] = []      # 上一轮 X 检查的编号（辅助比特尚未测量）
    pending_x_round = -1
    corrupted: set[tuple[int, str, int]] = set()

    def emit_detectors(typ: str, idxs: list[int], r: int):
        nonlocal meas
        base = meas
        meas += len(idxs)
        for j, i in enumerate(idxs):
            cur = base + j
            if typ != basis:
                prev = last.get((typ, i))
                if (r, typ, i) in corrupted:
                    last.pop((typ, i), None)
                    continue
                last[(typ, i)] = cur
                continue
            prev = last.get((typ, i))
            if (r, typ, i) in corrupted:
                if r == 0 and not drop_first_round_detectors:
                    c.append("DETECTOR", [stim.target_rec(cur - meas)])
                last.pop((typ, i), None)
                continue
            if prev is not None:
                c.append("DETECTOR", [stim.target_rec(cur - meas), stim.target_rec(prev - meas)])
            elif not (drop_first_round_detectors and r == 0):
                c.append("DETECTOR", [stim.target_rec(cur - meas)])
            last[(typ, i)] = cur

    def pairs(typ: str, idxs: list[int], r: int):
        out = []
        for i in idxs:
            if typ == "Z":
                prs = [(q, zanc[i]) for q in np.flatnonzero(code.HZ[i])]
            else:
                prs = [(xanc[i], q) for q in np.flatnonzero(code.HX[i])]
            if drop_cnot is not None and drop_cnot[:3] == (r, typ, i):
                dq = drop_cnot[3]
                prs = [pr for pr in prs if dq not in pr]
                corrupted.add((r, typ, i))
            out.extend(prs)
        return _layers(out)

    for r in range(rounds):
        zs = [i for i in range(mz) if (r, "Z", i) not in skip]
        xs = [i for i in range(mx) if (r, "X", i) not in skip]
        # [R Z 辅助 + H X 辅助(上一轮)]
        c.append("R", [zanc[i] for i in zs])
        if pending_x:
            c.append("H", [xanc[i] for i in pending_x])
        c.append("TICK")
        zl = pairs("Z", zs, r) or [[]]
        for li, layer in enumerate(zl):
            if li == 0 and pending_x:
                c.append("M", [xanc[i] for i in pending_x])
                emit_detectors("X", pending_x, pending_x_round)
                pending_x = []
            if layer:
                c.append("CX", [x for pr in layer for x in pr])
            c.append("TICK")
        if xs:
            c.append("R", [xanc[i] for i in xs])
            c.append("TICK")
            c.append("H", [xanc[i] for i in xs])
            c.append("TICK")
        xl = pairs("X", xs, r) or [[]]
        for li, layer in enumerate(xl):
            if li == 0 and zs:
                c.append("M", [zanc[i] for i in zs])
                emit_detectors("Z", zs, r)
            if layer:
                c.append("CX", [x for pr in layer for x in pr])
            c.append("TICK")
        pending_x, pending_x_round = xs, r
    # 排空：最后一轮的 X 辅助比特
    if pending_x and not drop_final_flush:
        c.append("H", [xanc[i] for i in pending_x])
        c.append("TICK")
        c.append("M", [xanc[i] for i in pending_x])
        emit_detectors("X", pending_x, pending_x_round)
        c.append("TICK")
    c.append("M" if basis == "Z" else "MX", data)
    meas += n
    H = code.HZ if basis == "Z" else code.HX
    for i in range(H.shape[0]):
        if (basis, i) not in last:
            continue
        tg = [stim.target_rec(q - n) for q in np.flatnonzero(H[i])]
        tg.append(stim.target_rec(last[(basis, i)] - meas))
        c.append("DETECTOR", tg)
    L = code.LZ if basis == "Z" else code.LX
    for j in range(L.shape[0]):
        c.append("OBSERVABLE_INCLUDE", [stim.target_rec(q - n) for q in np.flatnonzero(L[j])], j)
    return c, data
