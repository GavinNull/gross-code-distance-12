"""Audit claim 4: independent CEGAR (own SAT encoding with pysat Glucose4, own symbolic fault model, own nogoods).

Family F(variant, S): every measured check gets its own assignment of its 6 CNOTs to layers 1..S (injective),
one gate per data qubit per layer, determinism parity, all checks prepared at layer 0 and measured at S+1, the
same schedule every round, rounds do not overlap.  Question: is there a member with no undetectable logical of
weight <= d-1 (both memory bases, all R)?

Nogood: for a weight <= d-1 witness found by Sym at some R, the union of Sym.literals(tag) over its mechanisms.
Soundness (argued in the audit report): if a schedule of F satisfies all those order literals, every mechanism of
the witness exists in it with the same detector/observable effect (data cuts: there is a CNOT-fault / data
init / data readout location between any two consecutive reader CNOTs on a qubit; spreader cuts: same suffix set
and the same reader order around each suffix CNOT).  Compression: a weight-w logical needs faults in <= w rounds,
and fault-free rounds can be removed, so R = 1..w (checked: 1..d) decides all R.
"""
import argparse
import itertools
import json
import random
import time

from pysat.solvers import Solver

from search.experiments.e036_audit.core import Sym, checks, legal, min_weight_le, support


class Enc:
    def __init__(self, variant, S):
        self.variant, self.S = variant, S
        self.ks = checks(variant)
        self.ev = [(k, a) for k in self.ks for a in range(6)]
        self.nv = 0
        self.x = {}
        for e in self.ev:
            for t in range(1, S + 1):
                self.x[(e, t)] = self.new()
        self.cl = []
        for e in self.ev:
            xs = [self.x[(e, t)] for t in range(1, S + 1)]
            self.cl.append(xs)
            self.amo(xs)
        for k in self.ks:
            for t in range(1, S + 1):
                self.amo([self.x[((k, a), t)] for a in range(6)])
        self.onq = {}
        for k in self.ks:
            for a, q in enumerate(support(k)):
                self.onq.setdefault(q, []).append((k, a))
        for q, evs in self.onq.items():
            for t in range(1, S + 1):
                self.amo([self.x[(e, t)] for e in evs])
        self.ltv = {}
        # determinism parity
        for kx in self.ks:
            if kx[0] != "X":
                continue
            for kz in self.ks:
                if kz[0] != "Z":
                    continue
                sx, sz = support(kx), support(kz)
                sh = [q for q in sx if q in sz]
                if not sh:
                    continue
                lits = [self.lt((kx, sx.index(q)), (kz, sz.index(q))) for q in sh]
                self.xor_even(lits)

    def new(self):
        self.nv += 1
        return self.nv

    def amo(self, xs):
        for a, b in itertools.combinations(xs, 2):
            self.cl.append([-a, -b])

    def xor_even(self, lits):
        # direct CNF of XOR(lits) = 0 (lits are few: shared qubits of an X/Z pair)
        n = len(lits)
        for signs in itertools.product([0, 1], repeat=n):
            if sum(signs) % 2 == 1:  # forbid assignments with odd parity
                self.cl.append([(-l if s else l) for l, s in zip(lits, signs)])

    def lt(self, e1, e2):
        """literal 'layer(e1) < layer(e2)' for two events on a common qubit or check (distinct layers)."""
        if e1 == e2:
            raise ValueError
        key = (e1, e2) if e1 < e2 else (e2, e1)
        if key not in self.ltv:
            v = self.new()
            a, b = key
            S = self.S
            for t1 in range(1, S + 1):
                for t2 in range(1, S + 1):
                    if t1 >= t2:   # v -> layer(a) < layer(b)
                        self.cl.append([-v, -self.x[(a, t1)], -self.x[(b, t2)]])
                    if t1 <= t2:   # not v -> layer(a) > layer(b)
                        self.cl.append([v, -self.x[(a, t1)], -self.x[(b, t2)]])
            self.ltv[key] = v
        v = self.ltv[key]
        return v if key == (e1, e2) else -v

    def decode(self, model):
        pos = set(l for l in model if l > 0)
        T = {k: [None] * 6 for k in self.ks}
        for (e, t), v in self.x.items():
            if v in pos:
                T[e[0]][e[1]] = t
        return T


def find_cex(T, variant, d, Rs, per_case=8, limit=400):
    """returns list of (R, basis, w, literal-set) for witnesses of weight <= d-1 (smallest literal sets)."""
    out = []
    for R in Rs:
        for b in ("Z", "X"):
            sy = Sym(variant, b, T, R)
            ms = sy.mechs()
            w, wits = min_weight_le(ms, d - 1, want_all=True, limit=limit)
            if w is None:
                continue
            cand = []
            for wt in wits:
                lits = set()
                for i in wt:
                    lits |= sy.literals(ms[i][2])
                cand.append(frozenset(lits))
            cand = sorted(set(cand), key=len)[:per_case]
            out += [(R, b, w, c) for c in cand]
        if out:
            return out
    return out


def run(variant, S, d, seed, max_iter, solver_name, per_case, dump):
    E = Enc(variant, S)
    s = Solver(name=solver_name, bootstrap_with=E.cl)
    ptr = len(E.cl)  # clauses defining order variables created later must be pushed to the solver too
    rng = random.Random(seed)
    nogoods = []
    t0 = time.time()
    for it in range(max_iter):
        # randomise phases a little for diversity
        ok = s.solve()
        if not ok:
            res = {"variant": variant, "S": S, "d": d, "result": "UNSAT", "iters": it, "nogoods": len(nogoods),
                   "vars": E.nv, "sec": round(time.time() - t0, 1), "solver": solver_name}
            break
        T = E.decode(s.get_model())
        lg, why = legal(T, variant, S)
        assert lg, why
        cex = find_cex(T, variant, d, range(1, d + 1), per_case=per_case)
        if not cex:
            res = {"variant": variant, "S": S, "d": d, "result": "FOUND", "iters": it, "T": {str(k): v for k, v in T.items()},
                   "sec": round(time.time() - t0, 1)}
            break
        for R, b, w, lits in cex:
            if not lits:
                res = {"variant": variant, "S": S, "d": d, "result": "UNSAT(schedule-independent witness)", "R": R,
                       "basis": b, "w": w, "iters": it}
                print(json.dumps(res))
                return res
            clause = [-E.lt(e1, e2) for e1, e2 in sorted(lits)]
            E.cl.append(clause)
            for c_ in E.cl[ptr:]:
                s.add_clause(c_)
            ptr = len(E.cl)
            nogoods.append((R, b, w, sorted(lits)))
        if it % 50 == 0:
            print(json.dumps([it, len(nogoods), round(time.time() - t0, 1), [(R, b, w, len(l)) for R, b, w, l in cex[:3]]]),
                  flush=True)
    else:
        res = {"variant": variant, "S": S, "d": d, "result": "MAXITER", "iters": max_iter, "nogoods": len(nogoods)}
    if dump:
        json.dump({"clauses": E.cl, "nv": E.nv,
                   "nogoods": [[R, b, w, [[list(e1[0]), e1[1], list(e2[0]), e2[1]] for e1, e2 in l]]
                               for R, b, w, l in nogoods]},
                  open(f"results/E-036-audit/cegar_{variant}_S{S}_d{d}_{solver_name}.json", "w"))
    print(json.dumps(res), flush=True)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("variant")
    ap.add_argument("S", type=int)
    ap.add_argument("--d", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20261026)
    ap.add_argument("--max-iter", type=int, default=200000)
    ap.add_argument("--solver", default="g4")
    ap.add_argument("--per-case", type=int, default=8)
    ap.add_argument("--dump", action="store_true")
    a = ap.parse_args()
    r = run(a.variant, a.S, a.d, a.seed, a.max_iter, a.solver, a.per_case, a.dump)
    with open("results/E-036-audit/a3_cegar.jsonl", "a") as f:
        f.write(json.dumps(r) + "\n")
