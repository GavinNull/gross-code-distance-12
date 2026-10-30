"""Item (2): d_ext and the complete lists of extended-code logicals of weight <= W, by the auditor's own pipeline:
extended code from B_audit.Bulk (the schedule's own CNOT orders: data columns + writer hook suffixes, merged by
H||L image), the 72-element translation group verified on columns, mitmsearch (E-032 auditor's C program, enum mode,
MITM terminal look = 2) with orbit root cases, orbit expansion, every set re-verified.  Completeness: the search
prunes at zero syndrome, which is exact for |S| < d_ext + 3 (theory-B audit section 4); here W <= d_ext + 1.

Output pickles are in the B_audit format {"keys": [[key,...],...], "colset": [...]} (one per weight), so
B_audit.lift can read them.  Optional comparison (as sets of frozensets of keys) with E-040's pickles.

  uv run python -m search.experiments.e040_audit_circ.lists g10 Z 11 --cmp 10:results/.../list_gross_X_A1A2B1A3B2B3.pkl
"""
from __future__ import annotations

import argparse
import pickle
import subprocess
import time
from collections import Counter

import numpy as np

from search.experiments.e040_audit_circ.common import OUT, ROOT, gross, jdump, load


def build(name, basis):
    from search.theory.B_audit.common import Bulk
    from search.theory.B_audit.enum_driver import translations
    from search.theory.B_audit.lift import bulk_columns
    sd = load(name)
    B = Bulk(sd, gross(), basis)
    cols, zero = bulk_columns(B)
    keys = sorted(cols)
    kidx = {k: i for i, k in enumerate(keys)}
    perms = translations("gross", B, sd)
    colperm = []
    for qp, cp in perms:
        pm = []
        for k in keys:
            kind, ident, _ = cols[k][0]
            img = B.key([qp[ident]]) if kind == "d" else B.key([qp[q] for q in B.wr[ident[0]][0][ident[1] - 1:]])
            # the translated hook suffix is the suffix of the translated check (verified in translations())
            pm.append(kidx[img])
        assert sorted(pm) == list(range(len(keys)))
        colperm.append(pm)
    return B, cols, zero, keys, colperm


def run(name, basis, W, procs=1):
    B, cols, zero, keys, colperm = build(name, basis)
    nh = B.H.shape[0]
    orb = [-1] * len(keys)
    reps = []
    for j in range(len(keys)):
        if orb[j] < 0:
            for pm in colperm:
                orb[pm[j]] = len(reps)
            reps.append(j)
    lines = [f"{len(keys)} {nh}"]
    for k in keys:
        v = np.frombuffer(k, np.uint8)
        hs = np.flatnonzero(v[:nh]).tolist()
        ls = np.flatnonzero(v[nh:]).tolist()
        lines.append(f"{len(hs)} {' '.join(map(str, hs))} {len(ls)} {' '.join(map(str, ls))}")
    lines.append(str(len(reps)))
    lines.append(" ".join(map(str, orb)))
    lines.append(" ".join(map(str, reps)))
    inp = OUT / f"ext_{name}_{basis}.txt"
    inp.write_text("\n".join(lines) + "\n")
    t0 = time.time()
    exe = str(OUT / "mitm_nw2")
    outs = []
    pending = list(range(len(reps)))
    running = []
    while pending or running:
        while pending and len(running) < procs:
            o = pending.pop(0)
            running.append(subprocess.Popen([exe, str(W), "enum", "2", str(o), str(o)], stdin=open(inp),
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        p = running.pop(0)
        outs.append(p.communicate())
    found = set()
    logs = []
    for so, se in outs:
        logs += [l for l in se.splitlines() if l.startswith(("CASE", "DONE"))]
        for ln in so.splitlines():
            if ln.startswith("SOL"):
                S = tuple(sorted(map(int, ln.split()[2:])))
                for pm in colperm:
                    found.add(tuple(sorted(pm[j] for j in S)))
    for S in found:
        v = np.zeros(len(keys[0]), np.uint8)
        for j in S:
            v ^= np.frombuffer(keys[j], np.uint8)
        assert not v[:nh].any() and v[nh:].any() and len(set(S)) == len(S)
    byw = Counter(len(S) for S in found)
    for w in sorted(byw):
        L = sorted(S for S in found if len(S) == w)
        pickle.dump({"keys": [[keys[j] for j in S] for S in L], "colset": keys},
                    open(OUT / f"list_{name}_{basis}_w{w}.pkl", "wb"))
    rec = {"spec": name, "basis": basis, "W": W, "ncols": len(keys), "zero_key_hooks": len(zero),
           "orbits": len(reps), "group": len(colperm), "by_weight": dict(sorted(byw.items())),
           "sec": round(time.time() - t0, 1), "log": logs}
    return rec, keys


def compare(name, basis, w, path, keys):
    mine = pickle.load(open(OUT / f"list_{name}_{basis}_w{w}.pkl", "rb"))["keys"]
    theirs = pickle.load(open(ROOT / path, "rb"))["keys"]
    A = {frozenset(S) for S in mine}
    Bs = {frozenset(S) for S in theirs}
    ks = set(keys)
    their_cols = set().union(*Bs) if Bs else set()
    return {"w": w, "theirs_path": path, "mine": len(A), "theirs": len(Bs), "theirs_raw": len(theirs),
            "equal": A == Bs, "only_mine": len(A - Bs), "only_theirs": len(Bs - A),
            "their_cols_subset_of_my_colset": their_cols <= ks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("basis")
    ap.add_argument("W", type=int)
    ap.add_argument("--procs", type=int, default=1)
    ap.add_argument("--cmp", default="", help="w:path,w:path")
    a = ap.parse_args()
    rec, keys = run(a.name, a.basis, a.W, a.procs)
    for item in [x for x in a.cmp.split(",") if x]:
        w, p = item.split(":", 1)
        rec[f"cmp_w{w}"] = compare(a.name, a.basis, int(w), p, keys)
    jdump(rec, "lists.jsonl")


if __name__ == "__main__":
    main()
