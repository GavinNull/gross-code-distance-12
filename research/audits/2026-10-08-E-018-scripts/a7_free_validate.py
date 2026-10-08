"""Audit E-018 (a7): per-check-free (non-symmetric) pipelined schedules with gaps.
 (1) determinism criterion vs stim on conflict-free schedules generated WITHOUT any determinism constraint
     (CP-SAT, random objective) -- the criterion is not used to generate them;
 (2) model-lift => real undetected logical (stim injection) on deterministic per-check-free schedules (generated with
     the determinism constraint), 5 lifting logicals each, plus one-fault-removed negative controls.
    PYTHONPATH=.:tests uv run python research/audits/2026-10-08-E-018-scripts/a7_free_validate.py P n seed
"""
import itertools, json, random, sys
sys.argv += []
sys.path.insert(0, "research/audits/2026-10-08-E-018-scripts")
from ortools.sat.python import cp_model
from a1_common import xo, zo, code
from a3_model import single_hook_logicals, lifts
P = int(sys.argv[1]); N = int(sys.argv[2]); seed = int(sys.argv[3])
sys.argv = [sys.argv[0], str(P), "0", str(seed)]
import a4_validate as A          # reuses to_spec / stim_det / my_det / inject (module-level P = this P)
rng = random.Random(seed)
ORD = {("X", i): xo[i] for i in range(72)} | {("Z", j): zo[j] for j in range(72)}


def gen(det, sd):
    m = cp_model.CpModel(); var = {}
    for chk in ORD:
        s = m.NewIntVar(0, P - 1, ""); o = [m.NewIntVar(1, P - 2, "") for _ in range(6)]
        for i in range(5): m.Add(o[i + 1] > o[i])
        var[chk] = (s, o)
    T = {}
    for chk, ords in ORD.items():
        for k, q in enumerate(ords):
            t = m.NewIntVar(1, 2 * P - 3, ""); m.Add(t == var[chk][0] + var[chk][1][k]); T[(chk, q)] = t
    touch = {}
    for chk, ords in ORD.items():
        for q in ords: touch.setdefault(q, []).append(chk)
    for q, l in touch.items():
        for c1, c2 in itertools.combinations(l, 2):
            for d in (-P, 0, P): m.Add(T[(c1, q)] - T[(c2, q)] != d)
    if det:
        def fl(c1, c2, q):
            f = m.NewIntVar(-2, 1, ""); x = T[(c1, q)] - T[(c2, q)]
            m.Add(x >= f * P); m.Add(x <= f * P + P - 1); return f
        for i in range(72):
            for j in range(72):
                sh = sorted(set(xo[i]) & set(zo[j]))
                if sh:
                    u, v = sh; m.Add(fl(("X", i), ("Z", j), u) == fl(("X", i), ("Z", j), v))
    r = random.Random(sd)
    if not det:
        m.Maximize(sum(r.randint(-5, 5) * x for s, o in var.values() for x in [s] + o))
    else:   # feasibility only, randomised: random hints
        for s_, o in var.values():
            m.AddHint(s_, r.randrange(P))
    sol = cp_model.CpSolver(); sol.parameters.max_time_in_seconds = 120; sol.parameters.num_workers = 1
    sol.parameters.random_seed = sd; sol.parameters.randomize_search = True
    st = sol.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE): return None
    return {chk: (sol.Value(s), tuple(sol.Value(x) for x in o)) for chk, (s, o) in var.items()}


out = {"P": P, "det_agree": 0, "det_disagree": 0, "nondet": 0, "det": 0, "inject_ok": 0, "inject_bad": 0,
       "neg_fired": 0, "neg_total": 0, "model_blocked_counts": []}
LOG = single_hook_logicals("X")
for k in range(N):
    sch = gen(False, seed * 1000 + k)
    if sch:
        a, b = A.my_det(sch), A.stim_det(A.to_spec(sch))
        out["det_agree" if a == b else "det_disagree"] += 1
        out["det" if b else "nondet"] += 1
    sch = gen(True, seed * 1000 + 500 + k)
    if sch:
        assert A.stim_det(A.to_spec(sch)), "criterion-generated schedule not deterministic in stim"
        out["det_agree"] += 1; out["det"] += 1
        lif = [L for L in LOG if lifts(sch, P, L, "Z")]
        out["model_blocked_counts"].append(len(LOG) - len(lif))
        for L in rng.sample(lif, min(5, len(lif))):
            nd, no = A.inject(sch, P, L)
            out["inject_ok" if (nd == 0 and no > 0) else "inject_bad"] += 1
            nd2, _ = A.inject(sch, P, L, drop=("hook", L[1]))
            out["neg_total"] += 1; out["neg_fired"] += nd2 > 0
print(json.dumps(out))
json.dump(out, open(f"results/E-018-audit/a7_P{P}_s{seed}.json", "w"))
