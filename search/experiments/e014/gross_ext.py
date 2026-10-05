"""E-014：Strikis Fig. 12 gross 电路的扩展码 + 对称群 + DFS 实例导出（128 位）。lead。

扩展码按 Strikis 等 2603.05481 Def. 2 / 本项目 ext.py：数据列 + 每个校验 CNOT 顺序的后缀残余。
对称群不做假设，直接计算：枚举全部 l·m 个平移 T_(a,b)，先验证 T 是码自同构（HX、HZ 在行列同时置换下不变），
再要求 T 把每个校验的 CNOT 顺序映到被映校验的 CNOT 顺序（于是残余集合不变）。
合并相同列之后，检查群作用在合并列上良定义（与 E-013 auditor 的 extcode.py 相同的论证）。

    PYTHONPATH=. uv run python -m search.experiments.e014.gross_ext
"""
import json
from pathlib import Path

import numpy as np

from baselines.bb_code import gross_code
from baselines.strikis import strikis_fig12
from evaluators.codes import CSSCode
from search.noninterleaved.ext import orders_from_schedule, residual_supports
from search.noninterleaved.run import HL

OUT = Path("results/E-014-gross-dcirc11-proof")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    g = gross_code()
    css = CSSCode.from_checks(g.HX, g.HZ)
    sched, _ = strikis_fig12(g)
    xo, zo = orders_from_schedule(sched)
    l, m = 12, 6
    n2 = l * m
    HX, HZ = np.asarray(g.HX, dtype=np.uint8), np.asarray(g.HZ, dtype=np.uint8)

    def tr(a, b):
        p = np.array([((i // m + a) % l) * m + (i % m + b) % m for i in range(n2)])
        return p, np.concatenate([p, p + n2])          # 校验行置换、数据列置换（L、R 两块）

    group = []
    for a in range(l):
        for b in range(m):
            pr, pc = tr(a, b)
            # 码自同构：H[pr[i], pc[j]] == H[i, j]
            ok = all(np.array_equal(H[np.ix_(pr, pc)], H) for H in (HX, HZ))
            if not ok:
                continue
            # 顺序不变：校验 T(i) 的 CNOT 顺序 == 校验 i 的顺序逐项平移
            inv = all(list(o[int(pr[i])]) == [int(pc[j]) for j in o[i]]
                      for o in (xo, zo) for i in range(n2))
            if inv:
                group.append((a, b))
    print(f"code automorphism translations with invariant per-check orders: {len(group)} -> {group}")
    meta = {"group": group}
    for kind, orders in (("X", xo), ("Z", zo)):
        H, L = HL(css, kind)
        H = np.asarray(H, dtype=np.uint8) % 2
        L = np.asarray(L, dtype=np.uint8) % 2
        supports = [(j,) for j in range(2 * n2)] + [tuple(sorted(s)) for o in orders for s in residual_supports(o)]
        key_of, cols, sup_class = {}, [], []
        for S in supports:
            h = (H[:, list(S)].sum(1) % 2).astype(np.uint8)
            lv = (L[:, list(S)].sum(1) % 2).astype(np.uint8)
            if not h.any() and not lv.any():
                sup_class.append(-1)
                continue
            k = h.tobytes() + lv.tobytes()
            if k not in key_of:
                key_of[k] = len(cols)
                cols.append((h, lv))
            sup_class.append(key_of[k])
        He = np.array([h for h, _ in cols]).T
        Le = np.array([lv for _, lv in cols]).T
        supidx = {S: i for i, S in enumerate(supports)}
        perms = []
        for a, b in group:
            _, pc = tr(a, b)
            P = np.full(len(cols), -1)
            for i, S in enumerate(supports):
                T = tuple(sorted(int(pc[j]) for j in S))
                assert T in supidx, f"residual set not invariant under ({a},{b})"
                ci, cj = sup_class[i], sup_class[supidx[T]]
                if ci < 0:
                    assert cj < 0
                    continue
                assert P[ci] in (-1, cj), "action not well defined on merged columns"
                P[ci] = cj
            assert sorted(P.tolist()) == list(range(len(cols)))
            perms.append(P)
        orb = np.full(len(cols), -1)
        reps = []
        for j in range(len(cols)):
            if orb[j] >= 0:
                continue
            o = sorted({int(P[j]) for P in perms})
            orb[o] = len(reps)
            reps.append(j)
        r, N = He.shape
        print(f"{kind}: He {He.shape} Le {Le.shape} orbits {len(reps)} col weights {np.bincount(He.sum(0)).tolist()}")
        assert r <= 128 and Le.shape[0] <= 30
        with open(OUT / f"inst_{kind}.txt", "w") as f:
            f.write(f"{r} {N} {len(reps)}\n")
            for j in range(N):
                hm = sum(1 << int(i) for i in np.nonzero(He[:, j])[0])
                lm = sum(1 << int(i) for i in np.nonzero(Le[:, j])[0])
                f.write(f"{hm & ((1 << 64) - 1)} {hm >> 64} {lm} {orb[j]}\n")
            f.write(" ".join(map(str, reps)) + "\n")
        meta[kind] = {"rows": int(r), "cols": int(N), "orbits": len(reps)}
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
