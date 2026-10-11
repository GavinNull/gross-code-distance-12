"""Audit E-024b (t0): completeness of gsat's family encoding (no over-constraint => no false UNSAT from the family).
(a) P = 8 colour-symmetric, wrap: enumerate ALL models of gsat.Enc with NO logical nogoods (blocking clauses on the
    times), map to specs, compare canonical hashes with the 944 circuits of the E-021 audit (b9_p8.py, independent
    backtracking; its set equals results/E-021-gross-new-orders/p8class_H24_spec*.json).
(b) P in {17 wrap, 20 nowrap, 12 wrap}: draw legal + deterministic colour-symmetric circuits with an OWN CP-SAT model
    (own order list: 8 positional variants of the unit's canonical order; own determinism = floor equality;
    randomised objective), confirm each with evaluator validate_schedule + stim DEM construction, then ask gsat.Enc
    (no logical nogoods) whether that exact time assignment is a model (solve under assumptions).
    PYTHONPATH=.:tests uv run python research/audits/2026-10-11-E-024b-scripts/t0_enc.py
"""
import glob, json, random, sys, time
sys.path.insert(0, "tests")
import numpy as np
from ortools.sat.python import cp_model
from evaluators.tasks import build_code, get_task
from evaluators.candidate import parse_schedule, validate_schedule, build_circuits
import search.experiments.e024b.gsat as G
from search.experiments.e024b.gen import Cls, build_family
from search.experiments.e021.mono import table

X = "A1A2A3B3B1B2,A1A2A3B1B2B3,A1A3A2B3B1B2"; Z = "A1A3A2B3B1B2,A1A2A3B1B2B3,A1A2A3B3B1B2"
col = (3, 1, 1)
code, _ = build_code(get_task("gross-dcirc"), None)
C = Cls(col, X, Z); F, ccol = build_family(col); T = table()
out = {}
which = sys.argv[1] if len(sys.argv) > 1 else "ab"

if "a" in which:
    t0 = time.time()
    M = G.Enc(F, C, ccol, 8, 0)
    hs = set(); n = 0
    while M.S.solve():
        t, st = M.times(M.S.get_model())
        hs.add(parse_schedule(G.spec_of(F, t, st, 8)).hash()); n += 1
        M.S.add_clause([-M.x[(i, v)] for i, v in t.items()])
    ref = {parse_schedule(json.load(open(f))).hash() for f in glob.glob("results/E-021-gross-new-orders/p8class_H24_spec*.json")}
    out["P8"] = {"models": n, "distinct_hash": len(hs), "ref": len(ref), "equal": hs == ref,
                 "only_enc": len(hs - ref), "only_ref": len(ref - hs), "sec": round(time.time() - t0)}
    print(out["P8"], flush=True)


def variants(o):
    res = []
    for v in range(8):
        p = list(o)
        if v & 4: p = p[::-1]
        if v & 1: p[0], p[1] = p[1], p[0]
        if v & 2: p[4], p[5] = p[5], p[4]
        res.append(p)
    return res


def own_sample(P, nowrap, seed):
    rng = random.Random(seed)
    m = cp_model.CpModel()
    units = [(ty, k) for ty in "XZ" for k in range(F.nc)]
    s = {u: m.NewIntVar(0, 0 if nowrap else P - 1, "") for u in units}
    m.Add(s[("X", 0)] == 0)
    t = {}
    for u in units:
        o = C.orders[u[0]][ccol[u[1]]]           # canonical label order of the unit's colour
        vs = variants(o)
        b = [m.NewBoolVar("") for _ in vs]; m.AddExactlyOne(b)
        tl = {lab: m.NewIntVar(1, 2 * P - 2, "") for lab in range(6)}
        for lab in range(6):
            m.Add(tl[lab] >= s[u] + 1); m.Add(tl[lab] <= s[u] + P - 2)
            t[F.idx[(u[0], u[1], lab)]] = tl[lab]
        for bv, p in zip(b, vs):
            for k in range(5):
                m.Add(tl[p[k]] < tl[p[k + 1]]).OnlyEnforceIf(bv)
    # legality: per data qubit 6 CNOT times distinct mod P
    md = {}
    for i, v in t.items():
        r = m.NewIntVar(0, P - 1, ""); m.AddModuloEquality(r, v, P); md[i] = r
    for q in range(144):
        its = sorted({F.item(ty, c, lab) for ty, c, lab in F.touch[q]})
        m.AddAllDifferent([md[i] for i in its])
    # determinism (own): X check a, Z check c sharing {u, v}: floor((tx-tz)/P) equal on u and v
    for a in range(72):
        for c in range(72):
            sh = sorted(set(map(int, T["X"][a])) & set(map(int, T["Z"][c])))
            if not sh: continue
            fs = []
            for q in sh:
                ix = F.item("X", a, F.label_of("X", a, q)); iz = F.item("Z", c, F.label_of("Z", c, q))
                f = m.NewIntVar(-3, 3, ""); m.Add(P * f <= t[ix] - t[iz]); m.Add(t[ix] - t[iz] <= P * f + P - 1)
                fs.append(f)
            for f in fs[1:]: m.Add(f == fs[0])
    m.Maximize(sum(rng.randint(-5, 5) * v for v in t.values()) + sum(rng.randint(-5, 5) * v for v in s.values()))
    sol = cp_model.CpSolver(); sol.parameters.num_workers = 1; sol.parameters.random_seed = seed
    sol.parameters.max_time_in_seconds = 60
    st = sol.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE): return None
    return {i: sol.Value(v) for i, v in t.items()}, {u: sol.Value(v) for u, v in s.items()}


if "b" in which:
    for P, nowrap in ((17, 0), (20, 1), (12, 0)):
        M = G.Enc(F, C, ccol, P, nowrap)
        rec = {"drawn": 0, "legal": 0, "deterministic": 0, "enc_accepts": 0, "distinct": 0}
        seen = set()
        for seed in range(1, 26):
            r = own_sample(P, nowrap, seed)
            if r is None: continue
            t, st = r; rec["drawn"] += 1
            d = G.spec_of(F, t, st, P); sp = parse_schedule(d)
            if sp.hash() in seen: continue
            seen.add(sp.hash()); rec["distinct"] += 1
            if validate_schedule(sp, code): continue
            rec["legal"] += 1
            try:
                for c in build_circuits(sp.canonical(), code, 3).values(): c.detector_error_model()
            except Exception:
                continue
            rec["deterministic"] += 1
            ass = [M.x[(i, v)] for i, v in t.items()] + [M.s[(u, w)] for u, w in st.items()]
            rec["enc_accepts"] += int(M.S.solve(assumptions=ass))
        out[f"P{P}_nowrap{nowrap}"] = rec
        print(P, nowrap, rec, flush=True)
json.dump(out, open(f"results/E-024b-audit/t0_enc_{which}.json", "w"), indent=1)
