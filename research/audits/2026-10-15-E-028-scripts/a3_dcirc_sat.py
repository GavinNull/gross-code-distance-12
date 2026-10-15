"""A3: exact circuit distance by SAT directly on the (own-encoder) DEM, no extended code / lift theory.
Question per (spec, basis, R, W): is there a set of <= W DEM errors with zero detectors and odd parity on some observable?
UNSAT => d_circ >= W+1 at that R.   Usage: a3_dcirc_sat.py SPEC BASIS W R1 R2 ... [--cnf DIR]"""
import sys, time, json, os
sys.path.insert(0, "research/audits/2026-10-15-E-028-scripts")
import numpy as np
from alib import *
from pysat.card import CardEnc, EncType
from pysat.solvers import Solver

def build_cnf(cols, nd, no, W):
    n = len(cols)
    top = n
    cls = []
    det_of = [[] for _ in range(nd)]
    obs_of = [[] for _ in range(no)]
    for j, (d, o) in enumerate(cols):
        for x in d: det_of[x].append(j + 1)
        for x in o: obs_of[x].append(j + 1)
    def chain(vs):
        nonlocal top, cls
        cur = vs[0]
        for v in vs[1:]:
            top += 1; y = top
            cls += [[-cur, -v, -y], [cur, v, -y], [cur, -v, y], [-cur, v, y]]
            cur = y
        return cur
    for vs in det_of:
        if vs:
            cls.append([-chain(vs)])
    outs = [chain(vs) for vs in obs_of if vs]
    cls.append(outs)
    card = CardEnc.atmost(list(range(1, n + 1)), bound=W, top_id=top, encoding=EncType.totalizer)
    cls += card.clauses
    return cls, max(top, card.nv)

def run(spec_path, basis, W, R, cnfdir=None):
    spec = load_spec(spec_path)
    circ = memory_circuit(spec, basis, R)
    cols, nd, no = dem_matrix(circ)
    cls, nv = build_cnf(cols, nd, no, W)
    t0 = time.time()
    if cnfdir:
        os.makedirs(cnfdir, exist_ok=True)
        fn = f"{cnfdir}/{os.path.basename(spec_path)[:3]}_{basis}_R{R}_W{W}.cnf"
        with open(fn, "w") as f:
            f.write(f"p cnf {nv} {len(cls)}\n")
            for c in cls: f.write(" ".join(map(str, c)) + " 0\n")
    with Solver(name="cd15", bootstrap_with=cls) as s:
        r = s.solve()
        wit = None
        if r:
            m = s.get_model()
            wit = [j for j in range(len(cols)) if m[j] > 0]
            # verify
            dd, oo = set(), set()
            for j in wit:
                dd ^= set(cols[j][0]); oo ^= set(cols[j][1])
            assert not dd and oo
    out = {"spec": spec_path, "basis": basis, "R": R, "W": W, "errs": len(cols), "dets": nd, "sat": bool(r),
           "wit_weight": None if wit is None else len(wit), "sec": round(time.time() - t0, 1)}
    print(json.dumps(out), flush=True)
    with open("results/E-028-audit/a3_dcirc_sat.jsonl", "a") as f:
        f.write(json.dumps(out) + "\n")
    return out

if __name__ == "__main__":
    a = sys.argv[1:]
    cnfdir = None
    if "--cnf" in a:
        i = a.index("--cnf"); cnfdir = a[i + 1]; a = a[:i] + a[i + 2:]
    spec, basis, W = a[0], a[1], int(a[2])
    for R in map(int, a[3:]):
        run(spec, basis, W, R, cnfdir)
