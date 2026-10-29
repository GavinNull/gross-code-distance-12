"""d_ext probe for a translation-invariant BB template schedule, with the audited E-014 DFS (dfs128_all.c, orbit case
split).  Single worker, wall-clock cap.

  uv run python -m search.theory.B.dext_probe --code bb108 --spec results/theoryB/specs/bb108_u11tpl.json --W 8 --cap 300
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time

import numpy as np

from search.theory.B.bulk import ROOT, Sched, code_mats, load_spec
from search.theory.B.template import code_params

BIN = ROOT / "results/theoryB/dfs128_all"


def ext_with_orbits(sch, l, m):
    cols, _ = sch.ext()
    keys = sorted(cols)
    kidx = {k: i for i, k in enumerate(keys)}
    N2 = l * m

    def tq(q, ta, tb):
        blk, r = divmod(q, N2)
        a, b = divmod(r, m)
        return blk * N2 + ((a + ta) % l) * m + (b + tb) % m
    # supports of realisations
    sup = {}
    for k, reals in cols.items():
        r = reals[0]
        if r[0] == "d":
            sup[k] = [r[1]]
        else:
            sup[k] = sch.writers[r[1]]["order"][r[2] - 1:]
    perms = []
    for ta in range(l):
        for tb in range(m):
            P = [kidx[sch.key([tq(q, ta, tb) for q in sup[k]])] for k in keys]
            assert sorted(P) == list(range(len(keys)))
            perms.append(P)
    orb = [-1] * len(keys)
    reps = []
    for j in range(len(keys)):
        if orb[j] < 0:
            for P in perms:
                orb[P[j]] = len(reps)
            reps.append(j)
    nh = sch.H.shape[0]
    He = np.array([np.frombuffer(k, np.uint8)[:nh] for k in keys]).T
    Le = np.array([np.frombuffer(k, np.uint8)[nh:] for k in keys]).T
    return keys, He, Le, orb, reps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--basis", default="Z")
    ap.add_argument("--W", type=int, required=True)
    ap.add_argument("--cap", type=float, default=300)
    a = ap.parse_args()
    if not BIN.exists():
        subprocess.run(["cc", "-O3", "-o", str(BIN), str(ROOT / "search/experiments/e014/dfs128_all.c")], check=True)
    l, m, _, _ = code_params(a.code)
    sch = Sched(load_spec(a.spec), code_mats(a.code), a.basis)
    keys, He, Le, orb, reps = ext_with_orbits(sch, l, m)
    r, N = He.shape
    f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, dir=ROOT / "results/theoryB")
    f.write(f"{r} {N} {len(reps)}\n")
    for j in range(N):
        hm = sum(1 << int(i) for i in np.nonzero(He[:, j])[0])
        lm = sum(1 << int(i) for i in np.nonzero(Le[:, j])[0])
        f.write(f"{hm & ((1 << 64) - 1)} {hm >> 64} {lm} {orb[j]}\n")
    f.write(" ".join(map(str, reps)) + "\n")
    f.close()
    t0 = time.time()
    res = {"code": a.code, "spec": a.spec, "basis": a.basis, "W": a.W, "N": N, "orbits": len(reps), "cases": []}
    for c in range(len(reps)):
        left = a.cap - (time.time() - t0)
        if left <= 0:
            res["cases"].append({"case": c, "status": "not run (cap)"}); continue
        try:
            p = subprocess.run([str(BIN), f.name, str(a.W), str(c)], capture_output=True, text=True, timeout=left,
                               env={"STOPFIRST": "1"})
            found = [ln for ln in p.stdout.splitlines() if ln.startswith("FOUND")]
            summ = [ln for ln in p.stdout.splitlines() if ln.startswith("SUMMARY")]
            res["cases"].append({"case": c, "found": len(found), "first": found[:1], "summary": summ[:1]})
            if found:
                break
        except subprocess.TimeoutExpired:
            res["cases"].append({"case": c, "status": "timeout"})
    res["sec"] = round(time.time() - t0, 1)
    print(json.dumps(res))


if __name__ == "__main__":
    main()


def build_list(code, spec, basis, w, out):
    """complete list of weight-w extended logicals (all orbit cases, every solution, orbit-expanded, verified)."""
    import pickle
    l, m, _, _ = code_params(code)
    sch = Sched(load_spec(spec), code_mats(code), basis)
    keys, He, Le, orb, reps = ext_with_orbits(sch, l, m)
    if not BIN.exists():
        subprocess.run(["cc", "-O3", "-o", str(BIN), str(ROOT / "search/experiments/e014/dfs128_all.c")], check=True)
    r, N = He.shape
    f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, dir=ROOT / "results/theoryB")
    f.write(f"{r} {N} {len(reps)}\n")
    for j in range(N):
        hm = sum(1 << int(i) for i in np.nonzero(He[:, j])[0])
        lm = sum(1 << int(i) for i in np.nonzero(Le[:, j])[0])
        f.write(f"{hm & ((1 << 64) - 1)} {hm >> 64} {lm} {orb[j]}\n")
    f.write(" ".join(map(str, reps)) + "\n")
    f.close()
    sols, summ = [], []
    for c in range(len(reps)):
        p = subprocess.run([str(BIN), f.name, str(w), str(c)], capture_output=True, text=True, check=True)
        for ln in p.stdout.splitlines():
            if ln.startswith("FOUND"):
                sols.append(tuple(sorted(int(x) for x in ln.split("cols:")[1].split())))
            if ln.startswith("SUMMARY"):
                summ.append(ln)
    assert len(summ) == len(reps)
    # orbit expansion with the same permutations
    N2 = l * m
    cols, _ = sch.ext()
    kidx = {k: i for i, k in enumerate(keys)}

    def tq(q, ta, tb):
        blk, rr = divmod(q, N2)
        a_, b_ = divmod(rr, m)
        return blk * N2 + ((a_ + ta) % l) * m + (b_ + tb) % m
    sup = {}
    for k, reals in cols.items():
        r0 = reals[0]
        sup[k] = [r0[1]] if r0[0] == "d" else sch.writers[r0[1]]["order"][r0[2] - 1:]
    perms = [[kidx[sch.key([tq(q, ta, tb) for q in sup[k]])] for k in keys] for ta in range(l) for tb in range(m)]
    allS = set()
    for s in sols:
        if len(s) != w:
            continue
        for P in perms:
            allS.add(tuple(sorted(P[j] for j in s)))
    for s in allS:
        assert len(set(s)) == w and not (He[:, list(s)].sum(1) % 2).any() and (Le[:, list(s)].sum(1) % 2).any()
    L = [[keys[j] for j in s] for s in sorted(allS)]
    pickle.dump({"keys": L, "colset": sorted(keys), "meta": {"code": code, "spec": spec, "basis": basis, "w": w,
                                                             "n": len(L), "dfs": summ}}, open(ROOT / out, "wb"))
    return len(L), sum(int(x.split("nodes=")[1].split()[0]) for x in summ)
