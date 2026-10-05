"""B8b: spot check of E-015's [[90,8,10]] negative claim (all mod-3 LRCs, two-class and three-class, d_ext <= 8).

Own construction (l, m) = (15, 3), A = x^9 + y + y^2, B = 1 + x^2 + x^7 (evaluator task bb90-dcirc), own colourings
colour(g) = (u i + v j) mod 3, own LRC orders (A block perm then B block perm for X; B then A for Z).
For a random sample of (colouring, kind, class, block order) class tests and of proper three-colour states, find a
logical of weight <= 8 (heur_min as finder, then dfs128 with the colour-preserving translation symmetry if the
heuristic fails) and verify it with the auditor's own He / Le.
usage: b9_bb90.py <seed> <n_class_samples> <n_state_samples>
"""
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import b_ibm  # noqa: E402
import extx  # noqa: E402
from gf2 import logical_basis  # noqa: E402

OUT = Path("results/E-014-E-015-audit")
l, m, n2 = 15, 3, 45
AT = [(9, 0), (0, 1), (0, 2)]
BT = [(0, 0), (2, 0), (7, 0)]
HX, HZ = b_ibm.bb_mats(l, m, AT, BT)
LX = logical_basis(HZ, HX)
LZ = logical_basis(HX, HZ)
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


def colour(u, v, two):
    c = [(u * (g // m) + v * (g % m)) % 3 for g in range(n2)]
    return [0 if x == 0 else 1 for x in c] if two else c


def proper(kind, col, blocks):
    used = set()
    for g in range(n2):
        for k, d in enumerate(order(kind, g, blocks[col[g]])):
            if (d, k) in used:
                return False
            used.add((d, k))
    return True


def sym(col):
    out = []
    for a in range(l):
        for b in range(m):
            p = np.array([add(g, (a, b)) for g in range(n2)])
            if all(col[p[g]] == col[g] for g in range(n2)):
                out.append(np.concatenate([p, p + n2]))
    return out


def decide(kind, orders, col, W, tag, nseeds=4):
    H, L = (HZ, LZ) if kind == "X" else (HX, LX)
    e = extx.build(H, L, [o for o in orders if o is not None], 2 * n2)
    He, Le = e["He"], e["Le"]
    from search.noninterleaved.heur import heur_min
    for sd in range(nseeds):
        w, x, _ = heur_min(He, Le, trials=300, seed=sd, lns_starts=16, stop_at=W)
        if x is not None and len(set(x)) <= W:
            v = np.zeros(He.shape[1], int); v[list(set(x))] = 1
            if not ((He @ v) % 2).any() and ((Le @ v) % 2).any():
                return {"method": "heur", "w": int(v.sum())}
    perms = sym(col)
    orb, reps, _ = extx.orbits(e, perms)
    path = OUT / f"b9_{tag}.txt"
    extx.dump128(He, Le, orb, reps, path)
    for c in range(len(reps)):
        out = subprocess.run([str(OUT / "dfs128"), str(path), str(W), str(c)], capture_output=True, text=True).stdout
        for line in out.splitlines():
            if line.startswith("FOUND"):
                cols = [int(t) for t in line.split("cols:")[1].split()]
                v = np.zeros(He.shape[1], int); v[cols] = 1
                assert not ((He @ v) % 2).any() and ((Le @ v) % 2).any()
                return {"method": f"dfs case {c}", "w": len(cols)}
    return {"method": "dfs complete", "w": None}


def full(kinds="XZ", homs=None, nseeds=4):
    """Complete re-derivation of the BB90 negative claims:
    two-class (h = 0 vs h != 0) for all 4 homs: every state is <= 8 iff for each class... we test every block order
    on class 0 and on class 1 (residuals of that class only); a state survives only if both its orders survive.
    three-class: class 0 test suffices (classes are translates); then every proper triple of survivors is decided."""
    res = {}
    homs = homs or [(1, 0), (0, 1), (1, 1), (1, 2)]
    for (u, v) in homs:
        for kind in kinds:
            alive = {}
            for two, cls in ((True, 0), (True, 1)):
                col = colour(u, v, two)
                al = []
                for b in range(36):
                    orders = [order(kind, g, BLOCKS[b]) if col[g] == cls else None for g in range(n2)]
                    r = decide(kind, orders, col, 8, f"full_{u}{v}{kind}", nseeds)
                    if r["w"] is None:
                        al.append(b)
                alive[cls] = al
            # two-class states
            col2 = colour(u, v, True)
            st2 = [(a, b) for a in alive[0] for b in alive[1] if proper(kind, col2, {0: BLOCKS[a], 1: BLOCKS[b]})]
            surv2 = []
            for a, b in st2:
                orders = [order(kind, g, BLOCKS[a] if col2[g] == 0 else BLOCKS[b]) for g in range(n2)]
                if decide(kind, orders, col2, 8, f"full_{u}{v}{kind}", nseeds)["w"] is None:
                    surv2.append((a, b))
            # three-class: class 0 of the 3-colouring is the same set of checks as class 0 of the two-class split
            col3 = colour(u, v, False)
            al3 = alive[0]
            st3 = [t for t in itertools.product(al3, repeat=3)
                   if proper(kind, col3, {0: BLOCKS[t[0]], 1: BLOCKS[t[1]], 2: BLOCKS[t[2]]})]
            surv3 = []
            for t in st3:
                orders = [order(kind, g, BLOCKS[t[col3[g]]]) for g in range(n2)]
                if decide(kind, orders, col3, 8, f"full_{u}{v}{kind}", nseeds)["w"] is None:
                    surv3.append(t)
            res[f"{u}{v}{kind}"] = dict(alive0=alive[0], alive1=alive[1], two_class_states=len(st2), two_class_survivors=surv2,
                                        three_class_states=len(st3), three_class_survivors=surv3)
            print(f"{u}{v} {kind}: alive class0 {len(alive[0])} class1 {len(alive[1])}; two-class states {len(st2)} "
                  f"survive {len(surv2)}; three-class states {len(st3)} survive {len(surv3)}", flush=True)
    (OUT / f"b9_bb90_full_{''.join(str(a)+str(b) for a, b in homs)}_{kinds}.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__" and sys.argv[1] == "full":
    full(sys.argv[3], [tuple(int(c) for c in sys.argv[2])], 1)
elif __name__ == "__main__":
    rng = np.random.default_rng(int(sys.argv[1]))
    ncls, nst = int(sys.argv[2]), int(sys.argv[3])
    homs = [(1, 0), (0, 1), (1, 1), (1, 2)]
    res = {"class_tests": [], "states": []}
    # class tests (two-class scheme: class 0 or class 1; three-class: class 0)
    for _ in range(ncls):
        u, v = homs[rng.integers(4)]
        two = bool(rng.integers(2))
        kind = "XZ"[rng.integers(2)]
        cls = int(rng.integers(2)) if two else 0
        b = int(rng.integers(36))
        col = colour(u, v, two)
        orders = [order(kind, g, BLOCKS[b]) if col[g] == cls else None for g in range(n2)]
        r = decide(kind, orders, col, 8, "cls")
        res["class_tests"].append(dict(hom=(u, v), two=two, kind=kind, cls=cls, block=b, **r))
        print(res["class_tests"][-1], flush=True)
    # three-class states for homs (1,1), (1,2): enumerate proper triples of all 36^3 orders? E-015: 20 alive per class.
    for (u, v) in [(1, 1), (1, 2)]:
        col = colour(u, v, False)
        for kind in "XZ":
            prop = [t for t in itertools.product(range(36), repeat=3)
                    if proper(kind, col, {0: BLOCKS[t[0]], 1: BLOCKS[t[1]], 2: BLOCKS[t[2]]})]
            res.setdefault("n_proper_triples", {})[f"{u}{v}{kind}"] = len(prop)
            pick = [prop[i] for i in rng.choice(len(prop), size=min(nst, len(prop)), replace=False)]
            for t in pick:
                orders = [order(kind, g, BLOCKS[t[col[g]]]) for g in range(n2)]
                r = decide(kind, orders, col, 8, "st")
                res["states"].append(dict(hom=(u, v), kind=kind, triple=t, **r))
                print(res["states"][-1], flush=True)
    print(res.get("n_proper_triples"))
    (OUT / f"b9_bb90_s{sys.argv[1]}.json").write_text(json.dumps(res, indent=1, default=str))

