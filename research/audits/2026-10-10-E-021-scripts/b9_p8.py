"""Audit E-021 (b9): independent re-enumeration of the colour-symmetric P = 8 family inside Fig. 12's
extended-code class, comparison with the experimenter's 944 specs, and own exact lift (R = 1, Z basis, CP-SAT,
stop at first lifting logical, witness re-checked) on every one of them.
Family: each (type, colour) class picks one of the 8 orders {Fig.12 order, reversed} x {swap pos 0-1} x {swap 4-5}
(applied positionally to every check of the class) and a start s in Z_8; prep = s, CNOT k at s+k (k=1..6),
meas = s+7.  Legal = no data qubit used twice at one time mod 8; deterministic = for every overlapping X/Z check
pair and every instance offset k, #{shared q : floor((T_x(q)-T_z(q))/8) < k} is even.  Final arbiter for
determinism: stim DEM construction on the evaluator's circuit.
    PYTHONPATH=.:tests uv run python research/audits/2026-10-10-E-021-scripts/b9_p8.py
"""
import json, sys, glob, itertools, random, time
sys.path.insert(0, "research/audits/2026-10-10-E-021-scripts")
from b_common import *
from evaluators.candidate import validate_schedule
from ortools.sat.python import cp_model

P = 8
xo, zo, xc, zc = A1.xo, A1.zo, A1.xcol, A1.zcol
checks = [("X", i, xo[i], xc[i]) for i in range(72)] + [("Z", i, zo[i], zc[i]) for i in range(72)]
classes = [(t, c) for t in "XZ" for c in range(3)]
cls_of = [classes.index((t, c)) for t, _, _, c in checks]


def variant(o, v):
    o = list(o)
    if v & 4: o = o[::-1]
    if v & 1: o[0], o[1] = o[1], o[0]
    if v & 2: o[4], o[5] = o[5], o[4]
    return o


def times(ci, opt):           # opt = (v, s): data qubit -> absolute CNOT time of instance 0
    v, s = opt
    return {q: s + k + 1 for k, q in enumerate(variant(checks[ci][2], v))}


OPTS = [(v, s) for v in range(8) for s in range(P)]
sup = [set(ch[2]) for ch in checks]
pairs = [(a, b) for a in range(144) for b in range(a + 1, 144) if sup[a] & sup[b]]


def ok_pair(a, b, Ta, Tb):
    sh = sup[a] & sup[b]
    if any((Ta[q] - Tb[q]) % P == 0 for q in sh):
        return False
    if checks[a][0] != checks[b][0]:
        Tx, Tz = (Ta, Tb) if checks[a][0] == "X" else (Tb, Ta)
        fl = [(Tx[q] - Tz[q]) // P for q in sh]
        for k in range(min(fl), max(fl) + 2):
            if sum(f < k for f in fl) % 2:
                return False
    return True


# class-pair compatibility tables (all check pairs, no symmetry shortcut)
t0 = time.time()
pc = {}
for a, b in pairs:
    pc.setdefault((cls_of[a], cls_of[b]), []).append((a, b))
comp = {}
for (ca, cb), lst in pc.items():
    tab = np.zeros((64, 64), bool)
    for i, oa in enumerate(OPTS):
        Ta = {a: times(a, oa) for a, _ in lst}
        for j, ob in enumerate(OPTS):
            if ca == cb and i != j:
                continue
            Tb = {b: times(b, ob) for _, b in lst}
            tab[i, j] = all(ok_pair(a, b, Ta[a], Tb[b]) for a, b in lst)
    comp[(ca, cb)] = tab
print("tables", round(time.time() - t0), "s", flush=True)


def compat(ca, i, cb, j):
    if (ca, cb) in comp: return comp[(ca, cb)][i, j]
    if (cb, ca) in comp: return comp[(cb, ca)][j, i]
    return True


sols = []
def bt(k, ch):
    if k == 6:
        sols.append(tuple(ch)); return
    for i in range(64):
        if k == 0 and OPTS[i][1] != 0:      # fix global time shift: class 0 starts at 0
            continue
        if not compat(k, i, k, i):
            continue
        if all(compat(j, ch[j], k, i) for j in range(k)):
            ch.append(i); bt(k + 1, ch); ch.pop()
bt(0, [])
print("enumerated", len(sols), flush=True)


def spec_of(sol):
    d = {"format": "qec-schedule/v1", "period": P, "x_checks": [], "z_checks": []}
    for ci, (t, i, o, c) in enumerate(checks):
        v, s = OPTS[sol[cls_of[ci]]]
        T = times(ci, (v, s))
        d["x_checks" if t == "X" else "z_checks"].append(
            {"prep": s % P, "meas": (s + 7) % P, "cnots": [[q, T[q] % P] for q in sorted(T)]})
    return parse_schedule(d)


mine = {}
for sol in sols:
    sp = spec_of(sol)
    mine[sp.hash()] = sp
theirs = {}
for f in glob.glob("results/E-021-gross-new-orders/p8class_H24_spec*.json"):
    sp = parse_schedule(json.load(open(f)))
    theirs[sp.hash()] = (f, sp)
info = {"enumerated": len(sols), "distinct_mine": len(mine), "theirs": len(theirs),
        "equal": set(mine) == set(theirs), "only_mine": len(set(mine) - set(theirs)),
        "only_theirs": len(set(theirs) - set(mine))}
print(info, flush=True)

lists, kb = audit018_lists("X")
fkeys = set(ext_keys("X", xo, zo))


def first_lift(groups):
    for S in lists:
        M = cp_model.CpModel(); one = M.NewConstant(1); dl = {}; vs_all = []
        for key in S:
            vs = []
            for dets in groups[key]:
                v = M.NewBoolVar(""); vs.append((v, dets))
                for d in dets: dl.setdefault(d, []).append(v)
            M.AddExactlyOne([v for v, _ in vs]); vs_all.append(vs)
        for d, ls in dl.items(): M.AddBoolXOr(ls + [one])
        s = cp_model.CpSolver(); s.parameters.num_workers = 1
        if s.Solve(M) in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            chosen = [d for vs in vs_all for v, d in vs if s.Value(v)]
            acc = set()
            for d in chosen: acc ^= set(d)
            Lsum = np.zeros(12, np.uint8)
            for key in S: Lsum ^= np.frombuffer(key[72:], np.uint8)
            assert len(chosen) == 11 and not acc and Lsum.any()
            return S
    return None


res = {"legal": 0, "deterministic": 0, "ext_equal": 0, "lifts": 0, "no_lift": []}
universe = mine if mine else {h: t[1] for h, t in theirs.items()}
for h, sp in universe.items():
    if validate_schedule(sp, code): continue
    res["legal"] += 1
    try:
        g, st = dem_groups(sp, 1, "Z")
    except Exception:
        continue
    res["deterministic"] += 1
    xo2, zo2 = orders(sp)
    res["ext_equal"] += int(set(ext_keys("X", xo2, zo2)) == fkeys and set(ext_keys("Z", xo2, zo2)) == set(ext_keys("Z", xo, zo)))
    if first_lift(g) is not None: res["lifts"] += 1
    else: res["no_lift"].append(h)
info.update(res)
print(info, flush=True)
json.dump(info, open(f"{OUT}/b9_p8.json", "w"), indent=1)
