"""E-036: independent re-check of a CEGAR UNSAT with a different encoding and solver.

Reads results/E-036-bb18/nogoods_<variant>_S<S>_d<d>.json and builds a pure CNF (one-hot time variables x[e, v],
v = 1..S; at-most-one per check and per data qubit; order variables g(e1, e2) <-> t(e1) > t(e2) by direct clauses;
determinism parities expanded to CNF; each nogood = OR of g(e1, e2) for its literals lt(e1, e2)).  Solved with
CaDiCaL 1.5.3 (pysat); also writes the CNF in DIMACS so an external DRAT check is possible.
"""
import itertools
import json
import sys

from pysat.card import CardEnc, EncType
from pysat.formula import CNF
from pysat.solvers import Cadical153

from search.experiments.e036.cegar import Fam
from search.experiments.e036.common import OUT


def main(variant, S, d):
    F = Fam(variant, S)
    ngs = json.loads((OUT / f"nogoods_{variant}_S{S}_d{d}.json").read_text())
    cnf = CNF()
    nv = [0]

    def new():
        nv[0] += 1
        return nv[0]
    evs = [(k, a) for k in F.cks for a in range(6)]
    x = {(e, v): new() for e in evs for v in range(1, S + 1)}
    for e in evs:
        cnf.append([x[e, v] for v in range(1, S + 1)])
        for v1, v2 in itertools.combinations(range(1, S + 1), 2):
            cnf.append([-x[e, v1], -x[e, v2]])
    groups = [[(k, a) for a in range(6)] for k in F.cks] + [evs_q for evs_q in F.ev_on_q.values()]
    for gr in groups:
        for v in range(1, S + 1):
            for e1, e2 in itertools.combinations(gr, 2):
                cnf.append([-x[e1, v], -x[e2, v]])
    gcache = {}

    def g(e1, e2):  # t(e1) > t(e2); e1, e2 never share a time (same check or same qubit)
        key = (e1, e2)
        if key not in gcache:
            var = new()
            for v1 in range(1, S + 1):
                for v2 in range(1, S + 1):
                    if v1 == v2:
                        continue
                    cnf.append([-x[e1, v1], -x[e2, v2], var if v1 > v2 else -var])
            gcache[key] = var
        return gcache[key]
    # determinism: number of shared qubits with t_X < t_Z is even  <=>  XOR of g(eZ, eX) == 0
    for kx, kz, sh in F.pairs:
        lits = [g((kz, b), (kx, a)) for a, b in sh]
        for signs in itertools.product([0, 1], repeat=len(lits)):
            if sum(signs) % 2 == 1:  # forbid assignments with odd parity
                cnf.append([(-l if s else l) for l, s in zip(lits, signs)])
    for ng in ngs:
        cl = []
        for k1, a1, k2, a2 in ng:
            e1 = ((k1[0], k1[1]), a1)
            e2 = ((k2[0], k2[1]), a2)
            cl.append(g(e1, e2))  # not lt(e1, e2)  ==  t(e1) > t(e2)
        cnf.append(cl)
    path = OUT / f"recheck_{variant}_S{S}_d{d}.cnf"
    cnf.to_file(str(path))
    with Cadical153(bootstrap_with=cnf.clauses) as s:
        sat = s.solve()
    rec = {"variant": variant, "S": S, "d": d, "nogoods": len(ngs), "vars": nv[0], "clauses": len(cnf.clauses),
           "cadical": "SAT" if sat else "UNSAT", "cnf": str(path)}
    print(json.dumps(rec))
    with open(OUT / "recheck.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
