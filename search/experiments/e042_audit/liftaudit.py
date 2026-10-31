"""E-042 audit, item 2: the link from the 250 DRAT/LRAT batches to "no list element lifts at R = 13".

  coverage   parse results/E-042-g10-cert/lift/R13/results.jsonl myself: per basis splits 0..124 of K = 125,
             batch s holds exactly the indices s, s+125, ... of 124,308 = 3,204 + 121,104 (no orbit reduction),
             three verdicts per batch, list files / sha256 / audit cross-check flags, R = 13.
  groups     E-042's CNF input (e032 lift.build_groups on the augmented SD6 DEM at R = 13, the zero-image terms)
             converted to detector coordinates, compared with MY step-index model parsed from the stim circuit
             (model.py): for every extended column the set of realisations' detector sets is identical, and the
             zero-image terms are exactly my readout flips.
  own        my own CP-SAT lift (model.py fault model, independent encoding) on list items at R = 13.
  decode     single-instance CNFs written by E-042's encoder (liftcert.add_instance): (a) list items -> CaDiCaL UNSAT,
             (b) a weight-12 data logical of g10 (must lift) -> SAT, the CaDiCaL model is decoded back to DEM terms
             (by replaying the variable allocation) and checked against my model: one term per column, XOR = 0.
  regen      regenerate batches s (E-042 code, deterministic), compare CNF sha256 with the record, then run
             CaDiCaL -> drat-trim -> cake_lpr myself (tools/), verdict lines only.

    uv run python -m search.experiments.e042_audit.liftaudit coverage|groups|own N|decode|regen BASIS S [S ...]
"""
from __future__ import annotations

import hashlib
import json
import pickle
import random
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from search.experiments.e042_audit.model import ROOT, Model

for p in (str(ROOT / "search/experiments/e031"), str(ROOT / "search/experiments/e027")):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = ROOT / "results/E-042-audit"
REC = ROOT / "results/E-042-g10-cert/lift/R13/results.jsonl"
SPEC = "search/experiments/e040/g10_d12_spec.json"
AUD = ROOT / "results/E-040-audit-circ"
TOOLS = {"cadical": ROOT / "tools/cadical/build/cadical", "drat": ROOT / "tools/drat-trim/drat-trim",
         "cake": ROOT / "tools/cake_lpr/cake_lpr"}
N10, N11 = 3204, 121104


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def log(rec):
    print(json.dumps(rec), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "liftaudit.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")


def coverage():
    recs = [json.loads(l) for l in open(REC)]
    by = defaultdict(list)
    for r in recs:
        by[r["basis"]].append(r)
    out = {"records": len(recs)}
    for b, rs in sorted(by.items()):
        K = {r["split"][1] for r in rs}
        assert K == {125}
        ss = sorted(r["split"][0] for r in rs)
        n = N10 + N11
        cov = Counter()
        for r in rs:
            s = r["split"][0]
            exp = len(range(s, n, 125))
            assert r["instances"] == exp and r["first_index"] == s, (s, r["instances"], exp)
            cov[s] += 1
        okv = all(r["solver"]["answer"] == "UNSAT" and r["drat_trim"]["verdict"] == "VERIFIED" and
                  r["cake_lpr"]["verdict"] == "VERIFIED UNSAT" and r["ok"] for r in rs)
        metas = {json.dumps({k: r["dem"][k] for k in ("nA", "nB", "w10_file", "w10_sha256", "w11_file", "w11_sha256",
                                                     "audit_lists_set_equal", "zero_terms", "aug_terms", "detectors")},
                            sort_keys=True) for r in rs}
        out[b] = {"batches": len(rs), "splits_complete": ss == list(range(125)), "no_duplicates": max(cov.values()) == 1,
                  "instances_sum": sum(r["instances"] for r in rs), "R": sorted({r["R"] for r in rs}),
                  "all_three_verdicts": okv, "distinct_meta": [json.loads(m) for m in metas],
                  "max_solver_cpu_s": max(r["solver"]["cpu_s"] for r in rs)}
    # list file hashes now on disk
    for k in ("X", "Z"):
        for f in (f"list_gross_{k}_A1A2B1A3B2B3.pkl", f"list11_gross_{k}_A1A2B1A3B2B3.pkl"):
            out[f] = sha(ROOT / "results/E-040-min-period" / f)
    log({"check": "coverage", **out})


def their_groups(basis, R=13):
    from evaluators.candidate import parse_schedule
    from search.experiments.e032 import common as C
    from search.experiments.e032 import lift as L
    spec = parse_schedule(json.loads((ROOT / SPEC).read_text())).canonical()
    lo = L.label_orders(spec)
    kind = L.KIND_OF_BASIS[basis]
    E = C.ext_general(kind, lo[kind], group=[(0, 0)])
    zeros = set()
    groups, st = L.build_groups(spec, R, basis, E, zeros=zeros)
    keys = [E["He"][:, j].tobytes() + E["Le"][:, j].tobytes() for j in range(E["N"])]
    return E, groups, zeros, keys


def coords(R, basis):
    from evaluators import candidate as cand
    from search.experiments.e042_audit.model import circuit
    _, circ, _ = circuit("g10", R, basis)
    c = circ.get_detector_coordinates()
    return {d: (int(v[0]), int(v[1])) for d, v in c.items()}


def mask2set(m, co):
    out = set()
    d = 0
    while m:
        if m & 1:
            out.add(co[d])
        m >>= 1
        d += 1
    return frozenset(out)


def my_groups(M):
    from search.experiments.e042_audit.lemma_test import groups
    return groups(M)


def groups_check():
    for basis in ("Z", "X"):
        E, G, zeros, keys = their_groups(basis)
        co = coords(13, basis)
        M = Model("g10", 13, basis)
        g, flips = my_groups(M)
        mine = {k: {f[2] for f in v} for k, v in g.items()}
        theirs = {keys[j]: {mask2set(m, co) for m in ms} for j, ms in G.items()}
        eq_cols = set(mine) == set(theirs)
        diff = [k for k in theirs if theirs[k] != mine.get(k)]
        zf = {mask2set(m, co) for m in zeros}
        myf = {f[2] for f in flips}
        log({"check": "groups", "basis": basis, "columns_theirs": len(theirs), "columns_mine": len(mine),
             "column_keys_equal": eq_cols, "columns_with_different_realisation_sets": len(diff),
             "realisations_theirs": sum(len(v) for v in theirs.values()),
             "realisations_mine": sum(len(v) for v in mine.values()),
             "zero_terms_theirs": len(zf), "my_flips": len(myf), "zero_terms_equal_flips": zf == myf})


def load_list(basis, w):
    return pickle.load(open(AUD / f"list_g10_{basis}_w{w}.pkl", "rb"))["keys"]


def own(nsample, seed=20261101):
    from search.experiments.e042_audit.lemma_test import solve
    rng = random.Random(seed)
    for basis in ("Z", "X"):
        M = Model("g10", 13, basis)
        g, flips = my_groups(M)
        for w, F in ((10, 1), (11, 0)):
            L = load_list(basis, w)
            idx = list(range(len(L))) if (w == 10 and nsample >= len(L)) else sorted(rng.sample(range(len(L)), min(nsample, len(L))))
            t0 = time.time()
            lifted = [i for i in idx if solve(L[i], g, flips, F) is not None]
            log({"check": "own_lift_R13", "basis": basis, "w": w, "flips<=": F, "tested": len(idx),
                 "all": len(idx) == len(L), "lifted": len(lifted), "sec": round(time.time() - t0, 1), "seed": seed})


class RecB:
    """Builder replica that records which variable is which DEM term (replays add_instance)."""


def decode():
    from lift_cnf import Builder, write
    from liftcert import add_instance
    import numpy as np
    for basis in ("Z", "X"):
        E, G, zeros, keys = their_groups(basis)
        co = coords(13, basis)
        k2j = {k: j for j, k in enumerate(keys)}
        M = Model("g10", 13, basis)
        g, flips = my_groups(M)
        tests = []
        L10, L11 = load_list(basis, 10), load_list(basis, 11)
        for i in (0, 1601, 3203):
            tests.append(("w10", i, L10[i], True))
        for i in (0, 60551):
            tests.append(("w11", i, L11[i], False))
        tests = tests if "--sat-only" not in sys.argv else []
        # weight-12 data logical: a weight-12 L-row-equivalent?  use the minimum-weight logical of the code found by
        # brute force over L rows + stabilizer combos is costly; instead take any data set S with H S = 0, L S != 0 of
        # weight 12 built from E-042's own upper-bound idea: the code's logical operator rows of weight 12.
        # an X-type logical operator (rows of LX) is an undetectable X error in the Z-basis memory (and LZ in X):
        # placed right after the data reset it must lift (SAT) -- a positive control on the g10 DEM itself
        Lmat = (np.asarray(M.code.LX if basis == "Z" else M.code.LZ) % 2).astype(np.uint8)
        assert not (M.H.astype(np.int64) @ Lmat.T.astype(np.int64) % 2).any()
        cand_rows = sorted((np.flatnonzero(r).tolist() for r in Lmat
                            if (M.L.astype(np.int64) @ r.astype(np.int64) % 2).any()), key=len)
        if cand_rows:
            qs = cand_rows[0]
            tests.append((f"dataL{len(qs)}", -1, [M.image([q]) for q in qs], False))
        for name, i, S, withzero in tests:
            js = [k2j[k] for k in S]
            sup = 0
            for j in js:
                for m in G[j]:
                    sup |= m
            z = sorted(m for m in zeros if m and m & ~sup == 0) if withzero else []
            inst = ([list(dict.fromkeys(G[j])) for j in js], z)
            b = Builder()
            add_instance(b, inst, [])
            # replay variable allocation: add_instance allocates per column one var per mask, then exactly_one aux,
            # so record var ids by diffing b.n around the same calls
            b2 = Builder()
            varmap = {}
            for col, masks in zip(js, inst[0]):
                vs = []
                for mm in masks:
                    v = b2.new(); vs.append(v); varmap[v] = ("col", col, mm)
                b2.exactly_one(vs, [])
            for mm in inst[1]:
                v = b2.new(); varmap[v] = ("zero", None, mm)
            cnf = OUT / "decode" / f"{basis}_{name}_{i}.cnf"
            cnf.parent.mkdir(parents=True, exist_ok=True)
            write(cnf, b, [f"audit decode {basis} {name} {i}"])
            p = subprocess.run([str(TOOLS["cadical"]), "-q", str(cnf)], capture_output=True, text=True)
            ans = "SAT" if p.returncode == 10 else "UNSAT" if p.returncode == 20 else f"rc{p.returncode}"
            mine = solve_mine(S, g, flips, 1 if withzero else 0)
            rec = {"check": "decode", "basis": basis, "item": name, "index": i, "cadical": ans,
                   "my_cpsat": "SAT" if mine is not None else "UNSAT", "vars": b.n, "clauses": len(b.clauses)}
            if ans == "SAT":
                model = set()
                for l in p.stdout.splitlines():
                    if l.startswith("v "):
                        model |= {int(x) for x in l[2:].split() if int(x) > 0}
                chosen = [varmap[v] for v in model if v in varmap]
                cols = Counter(c for t, c, _ in chosen if t == "col")
                acc = set()
                real = True
                for t, c, mm in chosen:
                    s = mask2set(mm, co)
                    acc ^= s
                    if t == "col":
                        real &= s in {f[2] for f in g[keys[c]]}
                    else:
                        real &= s in {f[2] for f in flips}
                rec.update(decoded_terms=len(chosen), one_per_column=all(v == 1 for v in cols.values()) and len(cols) == len(js),
                           xor_empty=not acc, terms_are_my_faults=bool(real))
            log(rec)
            cnf.unlink()


def solve_mine(S, g, flips, F):
    from search.experiments.e042_audit.lemma_test import solve
    return solve(S, g, flips, F)


def regen(basis, splits):
    from lift_cnf import Builder, write
    from liftcert import add_instance
    from search.experiments.e042 import lift as E42
    recs = {(r["basis"], r["split"][0]): r for r in map(json.loads, open(REC))}
    insts, meta = E42.setup(SPEC, 13, basis)
    assert meta["nA"] == N10 and meta["nB"] == N11 and len(insts) == N10 + N11
    K = 125
    for s in splits:
        r = recs[(basis, s)]
        idx = list(range(s, len(insts), K))
        b = Builder()
        sel = [b.new() for _ in idx]
        b.clauses.append(list(sel))
        for t, i in zip(sel, idx):
            add_instance(b, insts[i], [-t])
        name = r["name"]
        cnf = OUT / "regen" / f"{name}.cnf"
        cnf.parent.mkdir(parents=True, exist_ok=True)
        write(cnf, b, [f"E-042 lift batch: g10_d12_spec, {basis}-basis memory, R = 13, instances i = {s} mod {K} of "
                       f"{len(insts)} (first {meta['nA']}: weight-10 list with optional zero-image term; then "
                       f"weight-11 list); selectors 1..{len(idx)}; UNSAT iff no instance lifts"])
        h = sha(cnf)
        drat = cnf.with_suffix(".drat")
        lrat = cnf.with_suffix(".lrat")
        t0 = time.time()
        p = subprocess.run([str(TOOLS["cadical"]), "-q", "--binary=true", str(cnf), str(drat)], capture_output=True, text=True)
        t1 = time.time()
        q = subprocess.run([str(TOOLS["drat"]), str(cnf), str(drat), "-L", str(lrat)], capture_output=True, text=True)
        t2 = time.time()
        dv = [l for l in q.stdout.splitlines() if l.startswith("s ")]
        c = subprocess.run([str(TOOLS["cake"]), str(cnf), str(lrat)], capture_output=True, text=True)
        cv = [l for l in c.stdout.splitlines() if l.startswith("s ")]
        rec = {"check": "regen", "basis": basis, "split": s, "cnf_sha_equal_record": h == r["cnf_sha256"],
               "cnf_sha256": h, "cadical_rc": p.returncode, "drat_trim": dv, "cake_lpr": cv,
               "drat_sha_equal_record": sha(drat) == r["drat_sha256"] if drat.exists() else None,
               "sec": [round(t1 - t0, 1), round(t2 - t1, 1), round(time.time() - t2, 1)]}
        for f in (cnf, drat, lrat):
            if f.exists():
                f.unlink()
        log(rec)


def ctl():
    """E-042's 14 positive controls: the same list items on the segmented-timing control (segctl_g10.json), my
    solver at R = 13 must find a lift for each single item, and for >= 1 of the 200-item batch (here: count all)."""
    from search.experiments.e042_audit.lemma_test import solve
    picks = [0, 1601, 3203, 3204, 3204 + 60551, 3204 + 121103]
    b200 = list(range(0, 124308, 621))[:200]
    for basis in ("Z", "X"):
        M = Model("segctl_g10", 13, basis)
        g, flips = my_groups(M)
        kind = {"Z": "X", "Z_": None, "X": "Z"}[basis]      # E-042's own index order: the E-040 files
        E40 = ROOT / "results/E-040-min-period"
        L = pickle.load(open(E40 / f"list_gross_{kind}_A1A2B1A3B2B3.pkl", "rb"))["keys"] + \
            pickle.load(open(E40 / f"list11_gross_{kind}_A1A2B1A3B2B3.pkl", "rb"))["keys"]
        F = lambda i: 1 if i < N10 else 0
        single = {i: solve(L[i], g, flips, F(i)) is not None for i in picks}
        nb = sum(solve(L[i], g, flips, F(i)) is not None for i in b200)
        log({"check": "ctl_segctl_R13_my_solver", "basis": basis, "single_items_lift": single, "b200_lifting": nb})


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "ctl":
        ctl()
    if a[0] == "coverage":
        coverage()
    elif a[0] == "groups":
        groups_check()
    elif a[0] == "own":
        own(int(a[1]))
    elif a[0] == "decode":
        decode()
    elif a[0] == "regen":
        regen(a[1], [int(x) for x in a[2:]])
