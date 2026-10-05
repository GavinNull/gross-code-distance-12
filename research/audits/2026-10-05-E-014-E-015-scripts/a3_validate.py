"""A3/A4: validation of the 128-bit DFS port (search/experiments/e014/dfs128.c) and of the split mechanism.

(a) Embedding test: E-013 BB108 instance (54 rows, 64-bit format) -> 128-bit format with an order-preserving row
    spreading (row i -> 2i, rows up to 106) and with a shift (row i -> i + 70, rows 70..123).  dfs64 (E-013 auditor's
    dfs.c) on the original and dfs128 on the embedded instances must give identical node counts and FOUND counts.
(b) Brute force on random instances with > 64 rows (100 rows, 150 columns, a Z_25 symmetry), Python
    meet-in-the-middle enumeration of ALL logicals of weight <= 6, no pruning: DFS (no symmetry and with symmetry)
    must find 0 below the minimum and exactly the predicted number at the minimum.
(c) Split test: for several (case, W) the sum over split_idx of nodes equals unsplit nodes + (split_mod - 1)
    (each split run counts the root once) and found counts add up.
usage: a3_validate.py a|b|c
"""
import itertools
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

R = Path("results/E-014-E-015-audit")
sys.path.insert(0, str(Path(__file__).parent))
D64 = str(R / "dfs64")
D128 = str(R / "dfs128")


def run(binary, inst, W, case, sm=1, si=0):
    args = [binary, str(inst), str(W), str(case)] + ([str(sm), str(si)] if sm > 1 else [])
    out = subprocess.run(args, capture_output=True, text=True, check=True).stdout
    m = re.search(r"nodes=(\d+) found=(\d+)", out)
    return int(m.group(1)), int(m.group(2)), [l for l in out.splitlines() if l.startswith("FOUND")]


def part_a():
    res = []
    for side in "ZX":
        src = Path(f"results/E-013-audit/inst_{side}.txt").read_text().split("\n")
        r, N, NO = map(int, src[0].split())
        cols = [tuple(map(int, src[1 + j].split())) for j in range(N)]
        reps = src[1 + N]
        for name, f in (("spread2", lambda i: 2 * i), ("shift70", lambda i: i + 70)):
            p = R / f"a3_bb108_{side}_{name}.txt"
            with open(p, "w") as fh:
                fh.write(f"{f(r - 1) + 1} {N} {NO}\n")
                for h, lm, o in cols:
                    H = sum(1 << f(i) for i in range(r) if (h >> i) & 1)
                    fh.write(f"{H & ((1 << 64) - 1)} {H >> 64} {lm} {o}\n")
                fh.write(reps + "\n")
            for W, cases in ((9, [3, 5, 7, 8, 9]), (10, [6, 7, 8, 9])):
                for c in cases:
                    a = run(D64, f"results/E-013-audit/inst_{side}.txt", W, c)
                    b = run(D128, p, W, c)
                    res.append(dict(side=side, emb=name, W=W, case=c, nodes64=a[0], nodes128=b[0], found64=a[1],
                                    found128=b[1], same_found_lines=a[2] == b[2]))
                    print(res[-1], flush=True)
    ok = all(x["nodes64"] == x["nodes128"] and x["found64"] == x["found128"] and x["same_found_lines"] for x in res)
    return {"all_identical": ok, "runs": res}


def make_random(seed, nb=25, rb=4, cb=6, colws=(2, 2, 2, 3, 3, 3)):
    """Rows: rb blocks of nb (row (b, t)), columns: cb orbits of nb; group Z_nb shifts t.
    Base column of orbit o: colw random (block, offset) entries.  Le: one row per column orbit pair (parity of the
    number of chosen columns in orbits {o, o'}) -> invariant under the group."""
    rng = np.random.default_rng(seed)
    r, N = rb * nb, cb * nb
    He = np.zeros((r, N), np.uint8)
    base = []
    for o in range(cb):
        ent = set()
        while len(ent) < colws[o]:
            ent.add((int(rng.integers(rb)), int(rng.integers(nb))))
        base.append(sorted(ent))
        for t in range(nb):
            for b, s in ent:
                He[b * nb + (s + t) % nb, o * nb + t] ^= 1
    orb = np.repeat(np.arange(cb), nb)
    Le = []
    for _ in range(3):
        S = rng.choice(cb, size=2, replace=False)
        Le.append(np.isin(orb, S).astype(np.uint8))
    Le = np.array(Le)
    return He, Le, orb


def brute(He, Le, wmax):
    """All x with He x = 0, Le x != 0, |x| <= wmax (wmax <= 6) by meet in the middle.  Returns dict w -> list."""
    r, N = He.shape
    hv = [int("".join(map(str, He[::-1, j])), 2) for j in range(N)]
    lv = [int("".join(map(str, Le[::-1, j])), 2) for j in range(N)]
    half = {}
    for a in range(0, 4):
        for B in itertools.combinations(range(N), a):
            s = 0
            for j in B:
                s ^= hv[j]
            half.setdefault((a, s), []).append(B)
    out = {}
    for w in range(1, wmax + 1):
        a = (w + 1) // 2
        b = w - a
        sols = []
        for A in itertools.combinations(range(N), a):
            s = 0
            for j in A:
                s ^= hv[j]
            for B in half.get((b, s), ()):
                if b and B[0] <= A[-1]:
                    continue
                x = A + B
                lm = 0
                for j in x:
                    lm ^= lv[j]
                if lm:
                    sols.append(x)
        out[w] = sols
    return out


def dump(He, Le, orb, reps, path):
    r, N = He.shape
    with open(path, "w") as f:
        f.write(f"{r} {N} {len(reps)}\n")
        for j in range(N):
            hm = sum(1 << int(i) for i in np.nonzero(He[:, j])[0])
            lm = sum(1 << int(i) for i in np.nonzero(Le[:, j])[0])
            f.write(f"{hm & ((1 << 64) - 1)} {hm >> 64} {lm} {int(orb[j])}\n")
        f.write(" ".join(map(str, reps)) + "\n")


def part_b(seeds):
    res = []
    for sd in seeds:
        He, Le, orb = make_random(sd)
        bf = brute(He, Le, 6)
        ws = [w for w in bf if bf[w]]
        if not ws:
            res.append({"seed": sd, "skip": "no logical <= 6"})
            print(res[-1], flush=True)
            continue
        d = min(ws)
        N = He.shape[1]
        # no symmetry
        p0 = R / f"a3_rand_{sd}_nosym.txt"
        dump(He, Le, np.arange(N), list(range(N)), p0)
        f_below = sum(run(D128, p0, d - 1, j)[1] for j in range(N)) if d > 1 else 0
        found = set()
        for j in range(N):
            _, f, lines = run(D128, p0, d, j)
            assert f <= 50
            for l in lines:
                found.add(tuple(sorted(int(x) for x in l.split("cols:")[1].split())))
        nosym_ok = found == set(bf[d]) and f_below == 0
        # with symmetry: reps = first column of each orbit; prediction: solutions with rep(min orbit) in x
        reps = [int(np.nonzero(orb == o)[0][0]) for o in range(orb.max() + 1)]
        p1 = R / f"a3_rand_{sd}_sym.txt"
        dump(He, Le, orb, reps, p1)
        pred = {}
        for x in bf[d]:
            o = min(orb[j] for j in x)
            if reps[o] in x:
                pred.setdefault(int(o), set()).add(tuple(sorted(x)))
        sym_ok, sym_counts = True, {}
        for o in range(len(reps)):
            _, f, lines = run(D128, p1, d, o)
            got = {tuple(sorted(int(x) for x in l.split("cols:")[1].split())) for l in lines}
            sym_counts[o] = (f, len(pred.get(o, ())))
            if f != len(pred.get(o, ())) or (f <= 50 and got != pred.get(o, set())):
                sym_ok = False
            if d > 1 and run(D128, p1, d - 1, o)[1] != 0:
                sym_ok = False
        res.append({"seed": sd, "rows": He.shape[0], "max_row_used": int(np.nonzero(He.any(1))[0].max()),
                    "d": d, "n_min_logicals": len(bf[d]), "brute_counts": {w: len(v) for w, v in bf.items()},
                    "nosym_found": len(found), "nosym_ok": nosym_ok, "sym_counts(found,pred)": sym_counts,
                    "sym_ok": sym_ok})
        print(res[-1], flush=True)
    return res


def part_c():
    res = []
    jobs = [(R / "gross_lat_X.txt", 9, 0), (R / "gross_lat_Z.txt", 9, 1), (R / "a3_dsum_sym.txt", 5, 5), (R / "a3_dsum_nosym.txt", 5, 0),
            (R / "a3_bb108_Z_shift70.txt", 10, 3)]
    for inst, W, c in jobs:
        if not Path(inst).exists():
            continue
        n0, f0, _ = run(D128, inst, W, c)
        for sm in (2, 4):
            parts = [run(D128, inst, W, c, sm, si) for si in range(sm)]
            res.append(dict(inst=str(inst), W=W, case=c, split=sm, unsplit_nodes=n0, sum_split_nodes=sum(p[0] for p in parts),
                            unsplit_found=f0, sum_split_found=sum(p[1] for p in parts),
                            ok=(sum(p[0] for p in parts) == n0 + sm - 1 and sum(p[1] for p in parts) == f0)))
            print(res[-1], flush=True)
    return res


def part_d():
    """Direct sum of the IBM BB72 X-type and Z-type extended codes (each d_ext = 5): 72 rows placed at 0..35 and
    64..99, 360 columns.  Brute force (no pruning, own MITM from b_ibm.all_logicals) of ALL logicals of weight <= 5
    vs dfs128 without symmetry and with the block-wise translation symmetry (orbits of G x G, |G| = 36)."""
    sys.path.insert(0, "tests")
    import b_ibm
    import extx
    from gf2 import logical_basis
    HX, HZ = b_ibm.bb_mats(6, 6, [(3, 0), (0, 1), (0, 2)], [(0, 3), (1, 0), (2, 0)])
    from evaluators.candidate import build_circuits
    from evaluators.tasks import build_code, get_task
    css, _ = build_code(get_task("bb72-dcirc"), None)
    xo, zo, _ = b_ibm.orders_from_circuit(build_circuits(b_ibm.ibm_spec(), css, 1)["Z"], 72, HX, HZ)
    LX = logical_basis(HZ, HX); LZ = logical_basis(HX, HZ)
    blocks = [extx.build(HZ, LZ, xo, 72), extx.build(HX, LX, zo, 72)]
    perms = []
    for a in range(6):
        for b in range(6):
            p = np.array([((i // 6 + a) % 6) * 6 + (i % 6 + b) % 6 for i in range(36)])
            perms.append(np.concatenate([p, p + 36]))
    orbs = []
    for e, (H, oo) in zip(blocks, ((HZ, xo), (HX, zo))):
        # the IBM orders are translation invariant: check, then orbits
        for pd in perms:
            pr = pd[:36]
            assert all(list(oo[pr[i]]) == [int(pd[j]) for j in oo[i]] for i in range(36))
        orbs.append(extx.orbits(e, perms)[0])
    r1, N1 = blocks[0]["He"].shape
    r2, N2 = blocks[1]["He"].shape
    He = np.zeros((100, N1 + N2), np.uint8)
    He[:36, :N1] = blocks[0]["He"]
    He[64:100, N1:] = blocks[1]["He"]
    Le = np.zeros((24, N1 + N2), np.uint8)
    Le[:12, :N1] = blocks[0]["Le"]
    Le[12:, N1:] = blocks[1]["Le"]
    orb = np.concatenate([orbs[0], orbs[1] + orbs[0].max() + 1])
    t0 = time.time()
    bf = b_ibm.all_logicals(He, Le, 5)
    tb = time.time() - t0
    d = min(w for w in bf if bf[w])
    N = N1 + N2
    p0 = R / "a3_dsum_nosym.txt"
    dump(He, Le, np.arange(N), list(range(N)), p0)
    found, below = set(), 0
    for j in range(N):
        below += run(D128, p0, d - 1, j)[1]
        _, f, lines = run(D128, p0, d, j)
        assert f <= 50
        for l in lines:
            found.add(tuple(sorted(int(x) for x in l.split("cols:")[1].split())))
    reps = [int(np.nonzero(orb == o)[0][0]) for o in range(orb.max() + 1)]
    p1 = R / "a3_dsum_sym.txt"
    dump(He, Le, orb, reps, p1)
    pred = {}
    for x in bf[d]:
        o = min(orb[j] for j in x)
        if reps[o] in x:
            pred.setdefault(int(o), set()).add(tuple(sorted(x)))
    sym = {}
    sym_ok = True
    for o in range(len(reps)):
        _, f, lines = run(D128, p1, d, o)
        got = {tuple(sorted(int(x) for x in l.split("cols:")[1].split())) for l in lines}
        sym[o] = (f, len(pred.get(o, ())))
        sym_ok &= f == len(pred.get(o, ())) and (f > 50 or got == pred.get(o, set()))
        sym_ok &= run(D128, p1, d - 1, o)[1] == 0
    return {"rows": 100, "cols": N, "brute_counts": {w: len(v) for w, v in bf.items()}, "brute_sec": round(tb, 1),
            "d": d, "nosym_below": below, "nosym_found": len(found), "nosym_equal_brute": found == set(bf[d]),
            "n_orbits": len(reps), "sym_counts(found,pred)": sym, "sym_ok": bool(sym_ok)}


if __name__ == "__main__":
    what = sys.argv[1]
    if what == "a":
        r = part_a()
    elif what == "d":
        r = part_d()
    elif what == "b":
        r = part_b([int(s) for s in sys.argv[2].split(",")])
    else:
        r = part_c()
    (R / f"a3_{what}.json").write_text(json.dumps(r, indent=1, default=str))
    print(json.dumps({k: v for k, v in (r.items() if isinstance(r, dict) else [])}, default=str)[:300])

