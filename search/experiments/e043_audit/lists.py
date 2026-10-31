"""Item (2a): complete lists of extended-code logicals of weight <= W for one circuit and basis, by the auditor's
pipeline: extended code from B_audit.Bulk (data columns + writer hook suffixes k = 2..6, merged by H||L image) of the
schedule itself, translation group verified column by column, mitmsearch enum (orbit root cases, look 2), orbit
expansion, every set re-verified (distinct, H-sum 0, L-image != 0).  Complete for W < d_ext + 3 (zero-syndrome
pruning only cuts sets that contain a proper zero-syndrome subset, impossible below d_ext + 3).

Optional comparison as sets of frozensets of column keys with E-043's pickles (path:weight).

  uv run python -m search.experiments.e043_audit.lists ibm90 Z 8 --cmp 7:results/E-043-table/list_ibm90_spec_Z_w7.pkl
"""
from __future__ import annotations

import argparse
import pickle
import subprocess
import time
from collections import Counter

import numpy as np

from search.experiments.e043_audit.common import OUT, ROOT, code_of, info, jdump, load


def build(name, basis):
    from search.theory.B_audit.common import Bulk
    from search.theory.B_audit.enum_driver import translations
    from search.theory.B_audit.lift import bulk_columns
    cname = info(name)[0]
    sd = load(name)
    B = Bulk(sd, code_of(cname), basis)
    cols, zero = bulk_columns(B)
    keys = sorted(cols)
    kidx = {k: i for i, k in enumerate(keys)}
    perms = translations(cname, B, sd)
    colperm = []
    for qp, cp in perms:
        pm = []
        for k in keys:
            # map every realisation of the column and require all images to agree
            imgs = set()
            for kind, ident, _ in cols[k]:
                if kind == "d":
                    imgs.add(B.key([qp[ident]]))
                else:
                    c, kk = ident
                    imgs.add(B.key([qp[q] for q in B.wr[c][0][kk - 1:]]))
            assert len(imgs) == 1
            pm.append(kidx[imgs.pop()])
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
    lines += [str(len(reps)), " ".join(map(str, orb)), " ".join(map(str, reps))]
    inp = OUT / f"ext_{name}_{basis}.txt"
    inp.write_text("\n".join(lines) + "\n")
    exe = str(OUT / ("mitm_nw2" if nh <= 128 else "mitm_nw4"))
    t0 = time.time()
    pending = list(range(len(reps)))
    running, outs = [], []
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
        logs += [l for l in se.splitlines() if l.startswith("DONE")]
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
    return {"name": name, "basis": basis, "W": W, "ncols": len(keys), "zero_key_hooks": len(zero),
            "orbits": len(reps), "group": len(colperm), "by_weight": dict(sorted(byw.items())),
            "d_ext": min(byw) if byw else None, "sec": round(time.time() - t0, 1),
            "nodes": sum(int(l.split("nodes=")[1].split()[0]) for l in logs)}, keys


def compare(name, basis, w, path, keys):
    mine = pickle.load(open(OUT / f"list_{name}_{basis}_w{w}.pkl", "rb"))["keys"] \
        if (OUT / f"list_{name}_{basis}_w{w}.pkl").exists() else []
    d = pickle.load(open(ROOT / path, "rb"))
    A = {frozenset(S) for S in mine}
    Bs = {frozenset(S) for S in d["keys"]}
    return {"w": w, "theirs": path, "mine": len(A), "n_theirs": len(Bs), "theirs_raw": len(d["keys"]),
            "equal": A == Bs, "only_mine": len(A - Bs), "only_theirs": len(Bs - A),
            "same_colset": set(d["colset"]) == set(keys)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("basis")
    ap.add_argument("W", type=int)
    ap.add_argument("--procs", type=int, default=1)
    ap.add_argument("--cmp", default="")
    a = ap.parse_args()
    rec, keys = run(a.name, a.basis, a.W, a.procs)
    for item in [x for x in a.cmp.split(",") if x]:
        w, p = item.split(":", 1)
        rec[f"cmp_w{w}"] = compare(a.name, a.basis, int(w), p, keys)
    jdump(rec, "lists.jsonl")


if __name__ == "__main__":
    main()
