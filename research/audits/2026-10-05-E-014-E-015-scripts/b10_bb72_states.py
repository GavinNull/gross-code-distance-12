"""B6b: E-015 claim "all proper two-colour LRC states on [[72,12,6]] (3 homs x 2 kinds x 144) have d_ext >= 6".
Own family construction (as b9), own symmetry / orbits, dfs128 at W = 5 for every state (complete)."""
import itertools
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import b_ibm  # noqa: E402
import extx  # noqa: E402
from gf2 import logical_basis  # noqa: E402

OUT = Path("results/E-014-E-015-audit")
l, m, n2 = 6, 6, 36
AT = [(3, 0), (0, 1), (0, 2)]
BT = [(0, 3), (1, 0), (2, 0)]
HX, HZ = b_ibm.bb_mats(l, m, AT, BT)
LX = logical_basis(HZ, HX); LZ = logical_basis(HX, HZ)
S3 = list(itertools.permutations(range(3)))
BLOCKS = [(p, s) for p in S3 for s in S3]


def add(g, t, sgn=1):
    i, j = divmod(g, m)
    return ((i + sgn * t[0]) % l) * m + (j + sgn * t[1]) % m


def nb(kind, g):
    if kind == "X":
        return [add(g, a) for a in AT], [n2 + add(g, b) for b in BT]
    return [n2 + add(g, a, -1) for a in AT], [add(g, b, -1) for b in BT]


for g in range(n2):
    a, b = nb("X", g); assert sorted(a + b) == list(np.nonzero(HX[g])[0])
    a, b = nb("Z", g); assert sorted(a + b) == list(np.nonzero(HZ[g])[0])


def order(kind, g, blk):
    pi, sg = blk
    A, B = nb(kind, g)
    a = [A[pi[k]] for k in range(3)]; b = [B[sg[k]] for k in range(3)]
    return a + b if kind == "X" else b + a


def proper(kind, col, blocks):
    used = set()
    for g in range(n2):
        for k, d in enumerate(order(kind, g, blocks[col[g]])):
            if (d, k) in used:
                return False
            used.add((d, k))
    return True


res = {}
tot_found = 0
for u, v in [(1, 0), (0, 1), (1, 1)]:
    col = [(u * (g // m) + v * (g % m)) % 2 for g in range(n2)]
    perms = []
    for a in range(l):
        for b in range(m):
            p = np.array([add(g, (a, b)) for g in range(n2)])
            if all(col[p[g]] == col[g] for g in range(n2)):
                perms.append(np.concatenate([p, p + n2]))
    for kind in "XZ":
        H, L = (HZ, LZ) if kind == "X" else (HX, LX)
        states = [(e, o) for e in range(36) for o in range(36) if proper(kind, col, {0: BLOCKS[e], 1: BLOCKS[o]})]
        bad = []
        for e, o in states:
            oo = [order(kind, g, BLOCKS[e] if col[g] == 0 else BLOCKS[o]) for g in range(n2)]
            ex = extx.build(H, L, oo, 2 * n2)
            assert all(extx.logical_transform_ok(H, L, p) for p in perms)
            orb, reps, _ = extx.orbits(ex, perms)
            path = OUT / "b10_tmp.txt"
            extx.dump128(ex["He"], ex["Le"], orb, reps, path)
            f = 0
            for c in range(len(reps)):
                out = subprocess.run([str(OUT / "dfs128"), str(path), "5", str(c)], capture_output=True, text=True).stdout
                f += int(out.split("found=")[1].split()[0])
            if f:
                bad.append((e, o, f))
        res[f"{u}{v}_{kind}"] = dict(sym=len(perms), n_states=len(states), states_with_logical_le5=bad)
        print(f"{u}{v} {kind}: {len(states)} proper states, {len(bad)} with a logical of weight <= 5", flush=True)
(OUT / "b10_bb72_states.json").write_text(json.dumps(res, indent=1))
