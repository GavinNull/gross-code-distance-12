"""Audit claim 4: re-encode the family + MY dumped nogoods (event-level literals only) with a different CNF encoding
(ladder / order encoding of the layer variables) and solve with two more SAT solvers.  Also run a positive control
(no nogoods -> SAT) and report the CNF size."""
import itertools
import json
import sys

from pysat.solvers import Solver

from search.experiments.e036_audit.core import checks, support


def build(variant, S, nogoods):
    nv = [0]

    def new():
        nv[0] += 1
        return nv[0]
    ks = checks(variant)
    ev = [(k, a) for k in ks for a in range(6)]
    x = {(e, t): new() for e in ev for t in range(1, S + 1)}
    u = {(e, t): new() for e in ev for t in range(1, S + 1)}  # u[e,t] <-> layer(e) <= t
    cl = []
    for e in ev:
        cl.append([x[(e, t)] for t in range(1, S + 1)])
        for t in range(1, S + 1):
            # ladder
            if t > 1:
                cl.append([-u[(e, t - 1)], u[(e, t)]])
            # x[e,t] <-> u[e,t] & ~u[e,t-1]
            cl.append([-x[(e, t)], u[(e, t)]])
            if t > 1:
                cl.append([-x[(e, t)], -u[(e, t - 1)]])
                cl.append([x[(e, t)], -u[(e, t)], u[(e, t - 1)]])
            else:
                cl.append([x[(e, t)], -u[(e, t)]])
        cl.append([u[(e, S)]])
    groups = []
    for k in ks:
        groups.append([(k, a) for a in range(6)])
    onq = {}
    for k in ks:
        for a, q in enumerate(support(k)):
            onq.setdefault(q, []).append((k, a))
    groups += list(onq.values())
    for g in groups:
        for t in range(1, S + 1):
            for e1, e2 in itertools.combinations(g, 2):
                cl.append([-x[(e1, t)], -x[(e2, t)]])
    lt = {}

    def LT(a, b):
        if (a, b) in lt:
            return lt[(a, b)]
        v = new()
        for t in range(1, S + 1):
            # v & layer(a) = t  ->  layer(b) > t  (not u[b,t]);   ~v & layer(a) = t -> layer(b) < t (u[b,t-1])
            cl.append([-v, -x[(a, t)], -u[(b, t)]])
            if t > 1:
                cl.append([v, -x[(a, t)], u[(b, t - 1)]])
            else:
                cl.append([v, -x[(a, t)]])
        lt[(a, b)] = v
        return v
    for kx in ks:
        if kx[0] != "X":
            continue
        for kz in ks:
            if kz[0] != "Z":
                continue
            sh = [q for q in support(kx) if q in support(kz)]
            if not sh:
                continue
            vs = [LT((kx, support(kx).index(q)), (kz, support(kz).index(q))) for q in sh]
            # parity even: Tseitin chain
            acc = vs[0]
            for v in vs[1:]:
                y = new()
                cl += [[-y, acc, v], [-y, -acc, -v], [y, -acc, v], [y, acc, -v]]
                acc = y
            cl.append([-acc])
    for ng in nogoods:
        cl.append([-LT(a, b) for a, b in ng])
    return cl, nv[0]


def load(path):
    d = json.load(open(path))
    out = []
    for R, b, w, lits in d["nogoods"]:
        out.append([(((k1[0], k1[1]), a1), ((k2[0], k2[1]), a2)) for k1, a1, k2, a2 in lits])
    return out


if __name__ == "__main__":
    variant, S, path = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    ngs = load(path)
    res = {"variant": variant, "S": S, "nogoods": len(ngs)}
    cl0, _ = build(variant, S, [])
    with Solver(name="cd15", bootstrap_with=cl0) as s:
        res["control_no_nogoods"] = s.solve()
    cl, nv = build(variant, S, ngs)
    res["cnf_vars"], res["cnf_clauses"] = nv, len(cl)
    for name in ("cd15", "m22", "lgl"):
        try:
            with Solver(name=name, bootstrap_with=cl) as s:
                res[name] = "SAT" if s.solve() else "UNSAT"
        except Exception as ex:  # solver not built
            res[name] = f"n/a {ex}"
    with open(path.replace(".json", ".cnf"), "w") as f:
        f.write(f"p cnf {nv} {len(cl)}\n")
        for c in cl:
            f.write(" ".join(map(str, c)) + " 0\n")
    print(json.dumps(res))
    with open("results/E-036-audit/a7_recheck.jsonl", "a") as f:
        f.write(json.dumps(res) + "\n")
