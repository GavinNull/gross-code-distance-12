"""E-038: completeness of the legality CNF (needed for UNSAT claims): every legal schedule, normalised, satisfies it.
Schedules tested: Kunlun (N7), the E-036 P8 circuits (N6), our N8 circuit (N8), IBM's pipelined P8 order (V8 delta 7,
W8), and random legal schedules produced WITHOUT the CNF: random prep times / offsets repaired by local moves until
model.legal() holds AND the evaluator's validate_schedule (independent determinism check) reports nothing.
Normalisation (W, V): shift all times by -pi(first check), then move every check by a multiple of P so that pi is in
0..P-1 (relabelling of instances; a symmetry of legality and of the bulk model).
For each schedule: fix every integer variable with eq-literal assumptions and require SAT; also require the CNF
model's decode to equal the schedule.
usage: uv run python -m search.experiments.e038.legal_complete --n 40"""
import argparse
import json
import random

from pysat.solvers import Solver

from evaluators import candidate as cand
from search.experiments.e036.common import code, ibm_spec, kunlun_spec
from search.experiments.e036_audit.core import checks, support
from search.experiments.e038.enc import Enc
from search.experiments.e038.model import Sched, legal


def from_spec(spec, variant):
    """evaluator spec -> Sched (absolute times: prep in 0..P-1, events/meas after prep, unwrapped)."""
    P = spec.period
    ks = checks(variant)
    xs = [k for k in ks if k[0] == "X"]
    zs = [k for k in ks if k[0] == "Z"]
    pi, mu, tau = {}, {}, {}
    for lst, rows in ((xs, spec.x_checks), (zs, spec.z_checks)):
        for k, row in zip(lst, rows):
            p = row.prep % P
            pi[k] = p
            mu[k] = p + (row.meas - p) % P
            lay = dict(row.cnots)
            for a, q in enumerate(support(k)):
                tau[(k, a)] = p + (lay[q] - p) % P
    return Sched(variant, P, pi, mu, tau)


def normalise(s):
    P = s.P
    k0 = s.ks[0]
    sh = s.pi[k0]
    pi, mu, tau = {}, {}, {}
    for k in s.ks:
        p = s.pi[k] - sh
        m = (p // P) * P
        pi[k] = p - m
        mu[k] = s.mu[k] - sh - m
        for a in range(6):
            tau[(k, a)] = s.tau[(k, a)] - sh - m
    return Sched(s.variant, P, pi, mu, tau)


def accepts(E, s):
    ass = []
    for k in s.ks:
        for iv, v in ((E.pi[k], s.pi[k]), (E.mu[k], s.mu[k])):
            l = iv.eq(v)
            if l is False:
                return False
            if l is not True:
                ass.append(l)
        for a in range(6):
            l = E.tau[(k, a)].eq(s.tau[(k, a)])
            if l is False:
                return False
            if l is not True:
                ass.append(l)
    for c in E.cl[E._ptr:]:
        E._s.add_clause(c)
    E._ptr = len(E.cl)
    if not E._s.solve(assumptions=ass):
        return False
    d = E.decode(E._s.get_model())
    return d.tau == s.tau and d.pi == s.pi and d.mu == s.mu


def violations(s):
    P = s.P
    v = 0
    onq = {}
    for k in s.ks:
        for a, q in enumerate(support(k)):
            onq.setdefault(q, []).append(s.tau[(k, a)] % P)
    for q, rs in onq.items():
        v += len(rs) - len(set(rs))
    for kx in s.ks:
        if kx[0] != "X":
            continue
        for kz in s.ks:
            if kz[0] != "Z":
                continue
            sx, sz = support(kx), support(kz)
            sh = [q for q in sx if q in sz]
            for i in range(-3, 4):
                v += sum(s.tau[(kx, sx.index(q))] < s.tau[(kz, sz.index(q))] + i * P for q in sh) % 2
    return v


def random_legal(variant, P, rng, steps=40000):
    """simulated annealing on (collisions + odd parities) with moves inside each check's window; prep / window
    length random per check and occasionally re-drawn."""
    import math
    ks = checks(variant)
    s = Sched(variant, P, {}, {}, {})

    def rnd_check(k):
        p = rng.randrange(P)
        L = rng.randrange(7, P)
        offs = rng.sample(range(1, L), 6)
        s.pi[k], s.mu[k] = p, p + L
        for a in range(6):
            s.tau[(k, a)] = p + offs[a]
    for k in ks:
        rnd_check(k)
    cur = violations(s)
    T = 2.0
    for it in range(steps):
        if cur == 0:
            ok, _ = legal(s)
            spec = cand.parse_schedule(s.spec())
            if ok and not cand.validate_schedule(spec, code(variant)):
                return s
        k = rng.choice(ks)
        old = (s.pi[k], s.mu[k], [s.tau[(k, a)] for a in range(6)])
        if rng.random() < 0.1:
            rnd_check(k)
        else:   # swap two events or move one to a free offset in the window
            L = s.mu[k] - s.pi[k]
            used = {s.tau[(k, a)] - s.pi[k] for a in range(6)}
            a = rng.randrange(6)
            free = [o for o in range(1, L) if o not in used]
            if free and rng.random() < 0.5:
                s.tau[(k, a)] = s.pi[k] + rng.choice(free)
            else:
                b = rng.randrange(6)
                s.tau[(k, a)], s.tau[(k, b)] = s.tau[(k, b)], s.tau[(k, a)]
        new = violations(s)
        if new <= cur or rng.random() < math.exp((cur - new) / T):
            cur = new
        else:
            s.pi[k], s.mu[k] = old[0], old[1]
            for a in range(6):
                s.tau[(k, a)] = old[2][a]
        T = max(0.05, T * 0.9997)
    return None


def main(n, seed):
    rng = random.Random(seed)
    res = []
    tests = []
    tests.append(("kunlun", "N", 7, from_spec(kunlun_spec("bb18"), "bb18")))
    for nm in ("search/experiments/e036/bb18_p8_d3_spec.json",):
        tests.append(("bb18_p8_d3", "N", 6, from_spec(cand.parse_schedule(json.load(open(nm))), "bb18")))
    tests.append(("n8", "N", 8, Sched.from_json(json.load(open("search/experiments/e038/n8_found.json")))))
    ibm = normalise(from_spec(ibm_spec("bb18"), "bb18"))
    tests.append(("ibm_W8", "W", 8, ibm))
    for P in (8, 9, 10):
        for i in range(n):
            s = random_legal("bb18", P, rng)
            if s is not None:
                tests.append((f"rand{P}_{i}", "W", P, normalise(s)))
    encs = {}
    out = {"tested": 0, "rejected": [], "seed": seed}
    for name, cls, arg, s in tests:
        key = (cls, arg)
        if key not in encs:
            E = Enc("bb18", cls, arg)
            E._s = Solver(name="cd15", bootstrap_with=E.cl)
            E._ptr = len(E.cl)
            encs[key] = E
        ok = legal(s)[0] and accepts(encs[key], s)
        out["tested"] += 1
        if not ok:
            out["rejected"].append(name)
    # IBM order also in V8 delta = pi(Z) after normalisation
    dz = {ibm.pi[k] for k in ibm.ks if k[0] == "Z"}
    if len(dz) == 1:
        E = Enc("bb18", "V", 8, dz.pop())
        E._s = Solver(name="cd15", bootstrap_with=E.cl)
        E._ptr = len(E.cl)
        out["ibm_V8"] = accepts(E, ibm)
    out["names"] = [t[0] for t in tests]
    print(json.dumps(out))
    with open("results/E-038-bb18-d4/legal_complete.json", "w") as f:
        json.dump(out, f)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=5)
    a = ap.parse_args()
    main(a.n, a.seed)
