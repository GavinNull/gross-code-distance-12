"""E-036: empirical soundness test of the CEGAR nogoods.  For a nogood extracted from schedule T1 at (R, basis, w),
sample other legal schedules T2 in which every literal of the nogood HOLDS (forced via CP-SAT) and check that T2 has
an undetectable logical of weight <= w at the same (R, basis) (exact meet-in-the-middle).  Any violation = unsound."""
import json, random, sys
import stim  # noqa
from search.experiments.e036 import common as _c  # noqa
from ortools.sat.python import cp_model
from search.experiments.e036.cegar import Fam
from search.experiments.e036.common import OUT, dem_mechs, min_weight, sd6

def forced_solve(F, lits, seed, T1):
    m = cp_model.CpModel(); S = F.S
    T = {k: [m.NewIntVar(1, S, "") for _ in range(6)] for k in F.cks}
    for k in F.cks: m.AddAllDifferent(T[k])
    for q, evs in F.ev_on_q.items(): m.AddAllDifferent([T[k][a] for k, a in evs])
    for kx, kz, sh in F.pairs:
        bs = []
        for a, b in sh:
            v = m.NewBoolVar(""); m.Add(T[kx][a] < T[kz][b]).OnlyEnforceIf(v); m.Add(T[kx][a] > T[kz][b]).OnlyEnforceIf(v.Not()); bs.append(v)
        z = m.NewIntVar(0, len(bs), ""); m.Add(sum(bs) == 2 * z)
    for (k1, a1), (k2, a2) in lits: m.Add(T[k1][a1] < T[k2][a2])
    rng = random.Random(seed)
    # push away from T1
    diff = []
    for k in F.cks:
        for a in range(6):
            b = m.NewBoolVar(""); m.Add(T[k][a] != T1[k][a]).OnlyEnforceIf(b); diff.append(b)
            m.AddHint(T[k][a], rng.randint(1, S))
    m.Add(sum(diff) >= 10)
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = 20; s.parameters.num_workers = 1
    s.parameters.random_seed = seed; s.parameters.randomize_search = True
    st = s.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE): return None
    return {k: [s.Value(T[k][a]) for a in range(6)] for k in F.cks}

variant, S, d, n = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
F = Fam(variant, S)
tested = viol = skipped = 0
rng = random.Random(7)
for trial in range(n):
    T1 = F.solve([], 1000 + trial, 20)
    cex = F.check(T1, (1, 2), d, max_wit=4)
    for R, b, w, ng in cex:
        T2 = forced_solve(F, ng, trial * 10 + R, T1)
        if T2 is None: skipped += 1; continue
        mechs, _ = dem_mechs(sd6(F.spec(T2), variant, b, R))
        w2, _ = min_weight(mechs, w)
        tested += 1
        if w2 is None or w2 > w:
            viol += 1; print("VIOLATION", R, b, w, w2, flush=True)
res = {"variant": variant, "S": S, "tested": tested, "violations": viol, "skipped_infeasible": skipped}
print(json.dumps(res))
with open(OUT / "cegar_validate.jsonl", "a") as f: f.write(json.dumps(res) + "\n")
