"""Item 6: independent enumeration of the extended-code logicals of weight <= W for a translation-invariant BB
schedule, using the auditor's own C DFS (enum.c) with orbit representatives of the translation group, then expanding
orbits.  Compares with theory B's pickled lists if given.

  uv run python -m search.theory.B_audit.enum_driver bb108 results/theoryB/specs/bb108_u11tpl.json Z 9 \
        [--cmp results/theoryB/bb108_u11tpl_w8_Z.pkl,results/theoryB/bb108_u11tpl_w9_Z.pkl]
"""
from __future__ import annotations

import argparse
import json
import pickle
import subprocess
import time
from collections import Counter, defaultdict

import numpy as np

from search.theory.B_audit.common import ROOT, Bulk, get_code, load_spec_dict
from search.theory.B_audit.delta_terms import terms
from search.theory.B_audit.lift import bulk_columns


def translations(name, B: Bulk, spec):
    l, m, _, _ = terms(name)
    N2 = l * m
    idx = lambda a, b: (a % l) * m + (b % m)
    perms = []
    for s in range(l):
        for t in range(m):
            qp = [0] * (2 * N2)
            cp = [0] * N2
            for q in range(2 * N2):
                blk, r = divmod(q, N2)
                a, b = divmod(r, m)
                qp[q] = blk * N2 + idx(a + s, b + t)
            for c in range(N2):
                a, b = divmod(c, m)
                cp[c] = idx(a + s, b + t)
            perms.append((qp, cp))
    # verify invariance of code + schedule timing (writers and readers)
    for qp, cp in perms:
        for lst in (B.wr, B.rd):
            for c, (order, tm) in enumerate(lst):
                o2, t2 = lst[cp[c]]
                assert [qp[q] for q in order] == o2, "schedule not translation invariant"
                assert all(t2[qp[q]] - tm[q] == t2[o2[0]] - tm[order[0]] for q in order)
    return perms


def run(name, spec_path, basis, W, cmp_paths=()):
    code = get_code(name)
    spec = load_spec_dict(spec_path)
    B = Bulk(spec, code, basis)
    cols, zero = bulk_columns(B)
    keys = sorted(cols)
    kidx = {k: i for i, k in enumerate(keys)}
    nh = B.H.shape[0]
    # realisation -> column
    real2col = {}
    for k, lst in cols.items():
        for kind, ident, _ in lst:
            real2col[(kind, ident if kind == "h" else ident)] = kidx[k]
    perms = translations(name, B, spec) if not name.startswith("kunlun-") else []
    colperm = [] if perms else [list(range(len(keys)))]
    for qp, cp in perms:
        pm = [None] * len(keys)
        for k, lst in cols.items():
            kind, ident, _ = lst[0]
            img = ("d", qp[ident]) if kind == "d" else ("h", (cp[ident[0]], ident[1]))
            pm[kidx[k]] = real2col[img]
        assert sorted(pm) == list(range(len(keys)))
        colperm.append(pm)
    orbit = [-1] * len(keys)
    reps = []
    for j in range(len(keys)):
        if orbit[j] < 0:
            reps.append(j)
            for pm in colperm:
                orbit[pm[j]] = len(reps) - 1
    # input for C
    lines = []
    K = B.L.shape[0]
    for k in keys:
        v = np.frombuffer(k, np.uint8)
        s = np.flatnonzero(v[:nh]).tolist()
        lv = sum(1 << i for i in np.flatnonzero(v[nh:]).tolist())
        lines.append(f"{len(s)} {' '.join(map(str, s))} {lv}")
    jobs = []
    if not perms:
        reps = list(range(len(keys)))
        orbit = list(range(len(keys)))
    for oi, r in enumerate(reps):
        banned = [j for j in range(len(keys)) if orbit[j] < oi]
        jobs.append(f"{r} {len(banned)} {' '.join(map(str, banned))}")
    inp = f"{len(keys)} {nh} {K} {W}\n" + "\n".join(lines) + f"\n{len(jobs)}\n" + "\n".join(jobs) + "\n"
    t0 = time.time()
    pr = subprocess.run([str(ROOT / "results/theoryB_audit/enum")], input=inp, capture_output=True, text=True,
                        check=True)
    found = set()
    for ln in pr.stdout.splitlines():
        p = ln.split()
        S = tuple(sorted(map(int, p[3:])))
        for pm in colperm:
            found.add(tuple(sorted(pm[j] for j in S)))
    byw = Counter(len(S) for S in found)
    # independent re-check of every found set
    for S in found:
        v = np.zeros(len(keys[0]), np.uint8)
        for j in S:
            v ^= np.frombuffer(keys[j], np.uint8)
        assert not v[:nh].any() and v[nh:].any()
    res = {"code": name, "spec": spec_path, "basis": basis, "W": W, "ncols": len(keys), "zero_key_hooks": len(zero),
           "orbits": len(reps), "group": max(1, len(perms)), "by_weight": dict(sorted(byw.items())),
           "sec": round(time.time() - t0, 1), "c_stderr_tail": pr.stderr.strip().splitlines()[-1:]}
    for cp_ in cmp_paths:
        d = pickle.load(open(ROOT / cp_, "rb"))
        theirs = {tuple(sorted(kidx[k] for k in S)) for S in d["keys"]}
        w = len(next(iter(theirs)))
        mine = {S for S in found if len(S) == w}
        res[f"cmp_{cp_}"] = {"theirs": len(theirs), "mine": len(mine), "equal": theirs == mine,
                             "colset_equal": set(d["colset"]) == set(keys)}
    out = ROOT / f"results/theoryB_audit/list_{name}_{basis}_W{W}.pkl"
    pickle.dump({"keys": [[keys[j] for j in S] for S in sorted(found, key=lambda S: (len(S), S))],
                 "colset": keys, "meta": res}, open(out, "wb"))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("code")
    ap.add_argument("spec")
    ap.add_argument("basis")
    ap.add_argument("W", type=int)
    ap.add_argument("--cmp", default="")
    a = ap.parse_args()
    print(json.dumps(run(a.code, a.spec, a.basis, a.W, [c for c in a.cmp.split(",") if c])), flush=True)


if __name__ == "__main__":
    main()
