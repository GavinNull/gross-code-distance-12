"""E-039 audit a3: independent re-derivation of "N(S) cannot reach d_circ = 4 at R = 1" with my own model and encoding.
Nothing from e038 / e039 is imported (term convention via fcore only).

Model (R = 1, memory basis b; readers = measured b-checks, spreaders = the other type; relevant Pauli X for b = Z):
  D(q, t), t = 0..S : relevant Pauli on data q appearing right after layer t (t = 0: after the reset, t = S: after
                      the last CNOT, i.e. before the readout).  Reader c on q sees it in its round-0 syndrome iff
                      tau(c, q) > t.  (A cut parametrised by layer, NOT by a reader event as in E-039.)
  H(k, U)           : spreader-ancilla Pauli after its p-th CNOT, U = its 6 - p latest terms (|U| = 2..5).  Reader c
                      on u in U sees it iff tau(c, u) > tau(k, u).
  M(c)              : flips reader c's round-0 outcome.
  Detectors: D(c, 0) = s-flip(c), D(c, 1) = s-flip(c) ^ <residual, c>; observable = residual . logicals.
  Witness: <= 3 faults, residual commutes with all readers and is non-trivial (own GF(2)), all s-flips cancel.
  The model is checked against the stim DEM of my own circuit (fcore) on random schedules (mechanism sets equal).
CNF (own): one-hot x[e, t]; g[e, t] <-> tau_e > t; lt(e1, e2) pointwise from the one-hot variables; legality as in
samp.py; for every witness candidate (types with a valid residual, every cut vector) one clause
    OR_{H} not suffix(k, U)  OR  OR_{readers c} XOR_c
with Tseitin XOR literals (own cache).  Cubes on tau(Z0, term 0), tau(Z0, term 1) (E-039 split on X0).
usage: uv run python -m search.experiments.e039_audit.a3_own_r1 validate --n 20
       uv run python -m search.experiments.e039_audit.a3_own_r1 build --S 7 --out results/E-039-audit/own_R1_S7.cnf
       uv run python -m search.experiments.e039_audit.a3_own_r1 cubes results/E-039-audit/own_R1_S7.cnf --S 7"""
import argparse
import itertools
import json
import os
import sys

import numpy as np

from search.experiments.e039_audit import fcore as F

KS = F.KS
LEAN = os.environ.get('A3_LEAN') == '1'   # lean cut parametrisation (after-reader cuts)


def readers(b):
    return [k for k in KS if k[0] == b]


def spreaders(b):
    return [k for k in KS if k[0] != b]


def onq(b):
    return {q: [(k, F.SUPP[k].index(q)) for k in readers(b) if q in F.SUPP[k]] for q in range(F.ND)}


def logmasks(b):
    return [sum(1 << int(q) for q in np.nonzero(v)[0]) for v in F.logicals(b)]


def faults(tau, S, b):
    """my symbolic R=1 fault list: (sflip mask over readers, residual mask, tag)."""
    rd = readers(b)
    ri = {c: i for i, c in enumerate(rd)}
    oq = onq(b)
    out = []
    for q in range(F.ND):
        for t in range(S + 1):
            sf = 0
            for c, a in oq[q]:
                if tau[(c, a)] > t:
                    sf ^= 1 << ri[c]
            out.append((sf, 1 << q, ("D", q, t)))
    for k in spreaders(b):
        order = sorted(range(6), key=lambda a: tau[(k, a)])
        for p in range(1, 5):
            U = order[p:]
            sf = res = 0
            for a in U:
                u = F.SUPP[k][a]
                res ^= 1 << u
                for c, ac in oq[u]:
                    if tau[(c, ac)] > tau[(k, a)]:
                        sf ^= 1 << ri[c]
            out.append((sf, res, ("H", k, tuple(sorted(U)))))
    for c in rd:
        out.append((1 << ri[c], 0, ("M", c)))
    return out


def to_dem(fl, b):
    rd = readers(b)
    cm = [sum(1 << q for q in F.SUPP[c]) for c in rd]
    lm = logmasks(b)
    n = len(rd)
    out = set()
    for sf, res, _ in fl:
        d = 0
        for i in range(n):
            s = (sf >> i) & 1
            par = bin(res & cm[i]).count("1") & 1
            # detector index layout of fcore.circuit at R = 1: (c, 0) -> i, (c, 1) -> n + i
            d |= s << i
            d |= (s ^ par) << (n + i)
        o = sum((bin(res & l).count("1") & 1) << j for j, l in enumerate(lm))
        if d or o:
            out.add((d, o))
    return out


def valid_residual_table(b):
    rd = [sum(1 << q for q in F.SUPP[c]) for c in readers(b)]
    lm = logmasks(b)
    m = np.arange(1 << F.ND, dtype=np.int64)

    def par(x):
        x = x.copy()
        p = np.zeros_like(x)
        while x.any():
            p ^= x & 1
            x >>= 1
        return p
    ok = np.ones(1 << F.ND, bool)
    for r in rd:
        ok &= par(m & r) == 0
    anyl = np.zeros(1 << F.ND, bool)
    for l in lm:
        anyl |= par(m & l) == 1
    return ok & anyl


def candidates(b):
    """all slot multisets of size <= 3 (slots D(q), H(k, U) with |U| 2..5 as a term set, M(c)) with a valid residual;
    D slots carry no cut here (cuts are expanded in the CNF).  Returns dict type -> list of slot tuples."""
    V = valid_residual_table(b)
    Ds = [(("D", q), 1 << q) for q in range(F.ND)]
    Hs = []
    for k in spreaders(b):
        for n in range(2, 6):
            for U in itertools.combinations(range(6), n):
                Hs.append((("H", k, U), sum(1 << F.SUPP[k][a] for a in U)))
    Ms = [(("M", c), 0) for c in readers(b)]
    allslots = Ds + Hs + Ms
    out = {}
    idx = list(range(len(allslots)))
    masks = np.array([m for _, m in allslots], dtype=np.int64)
    for w in (1, 2, 3):
        if w < 3:
            for comb in itertools.combinations(idx, w):
                m = 0
                for i in comb:
                    m ^= int(masks[i])
                if V[m]:
                    tp = "".join(sorted(allslots[i][0][0] for i in comb))
                    out.setdefault(tp, []).append(tuple(allslots[i][0] for i in comb))
        else:
            for i, j in itertools.combinations(idx, 2):
                mij = int(masks[i]) ^ int(masks[j])
                ks = np.arange(j + 1, len(allslots))
                good = ks[V[mij ^ masks[j + 1:]]]
                for kk in good:
                    comb = (i, j, int(kk))
                    tp = "".join(sorted(allslots[x][0][0] for x in comb))
                    out.setdefault(tp, []).append(tuple(allslots[x][0] for x in comb))
    # repeated identical slots cancel -> never minimal; combinations() already excludes them
    return out


class CNF:
    def __init__(self, S):
        self.S = S
        self.nv = 0
        self.cl = []
        self.ev = [(k, a) for k in KS for a in range(6)]
        self.x = {(e, t): self.new() for e in self.ev for t in range(1, S + 1)}
        for e in self.ev:
            xs = [self.x[(e, t)] for t in range(1, S + 1)]
            self.cl.append(xs)
            for i, j in itertools.combinations(xs, 2):
                self.cl.append([-i, -j])
        for k in KS:
            for t in range(1, S + 1):
                for a1, a2 in itertools.combinations(range(6), 2):
                    self.cl.append([-self.x[((k, a1), t)], -self.x[((k, a2), t)]])
        for q in range(F.ND):
            eq = [(k, a) for k in KS for a in range(6) if F.SUPP[k][a] == q]
            for t in range(1, S + 1):
                for e1, e2 in itertools.combinations(eq, 2):
                    self.cl.append([-self.x[(e1, t)], -self.x[(e2, t)]])
        self.ltc = {}
        self.gc = {}
        self.xc = {}
        for kx in KS:
            if kx[0] != "X":
                continue
            for kz in KS:
                if kz[0] != "Z":
                    continue
                sh = sorted(set(F.SUPP[kx]) & set(F.SUPP[kz]))
                if not sh:
                    continue
                ls = [self.lt((kx, F.SUPP[kx].index(q)), (kz, F.SUPP[kz].index(q))) for q in sh]
                for signs in itertools.product([0, 1], repeat=len(ls)):
                    if sum(signs) % 2:
                        self.cl.append([(-l if s else l) for l, s in zip(ls, signs)])
        self.nlegal = len(self.cl)

    def new(self):
        self.nv += 1
        return self.nv

    def lt(self, e1, e2):
        key = (e1, e2)
        if key not in self.ltc:
            v = self.new()
            for t1 in range(1, self.S + 1):
                for t2 in range(1, self.S + 1):
                    self.cl.append([-self.x[(e1, t1)], -self.x[(e2, t2)], v if t1 < t2 else -v])
            self.ltc[key] = v
        return self.ltc[key]

    def gt(self, e, t):
        """literal tau_e > t, or True/False."""
        if t < 1:
            return True
        if t >= self.S:
            return False
        key = (e, t)
        if key not in self.gc:
            v = self.new()
            hi = [self.x[(e, u)] for u in range(t + 1, self.S + 1)]
            self.cl.append([-v] + hi)
            for h in hi:
                self.cl.append([v, -h])
            self.gc[key] = v
        return self.gc[key]

    def xor(self, lits, const):
        c = const
        cnt = {}
        for l in lits:
            if l is True:
                c ^= 1
                continue
            if l is False:
                continue
            cnt[abs(l)] = cnt.get(abs(l), 0) ^ 1
            if l < 0:
                c ^= 1
        vs = tuple(sorted(v for v, n in cnt.items() if n))
        if not vs:
            return bool(c)
        if vs not in self.xc:
            acc = vs[0]
            for v in vs[1:]:
                y = self.new()
                self.cl += [[-y, acc, v], [-y, -acc, -v], [y, -acc, v], [y, acc, -v]]
                acc = y
            self.xc[vs] = acc
        a = self.xc[vs]
        return -a if c else a

    def witness_clauses(self, b, slots):
        rd = readers(b)
        oq = onq(b)
        dsl = [s for s in slots if s[0] == "D"]
        cond = []
        base = {c: [] for c in rd}
        for s in slots:
            if s[0] == "H":
                _, k, U = s
                for xa in range(6):
                    if xa in U:
                        continue
                    for u in U:
                        cond.append(self.lt((k, xa), (k, u)))
                for a in U:
                    u = F.SUPP[k][a]
                    for c, ac in oq[u]:
                        base[c].append(self.lt((k, a), (c, ac)))
            elif s[0] == "M":
                base[s[1]].append(True)
        out = []
        if LEAN:
            # cut "before every reader" (None) or "right after reader event f" -- covers every cut position
            opts = [[None] + oq[s[1]] for s in dsl]
        else:
            opts = [range(self.S + 1)] * len(dsl)
        for cuts in itertools.product(*opts):
            par = {c: list(v) for c, v in base.items()}
            for s, t in zip(dsl, cuts):
                for c, ac in oq[s[1]]:
                    if not LEAN:
                        par[c].append(self.gt((c, ac), t))
                    elif t is None:
                        par[c].append(True)
                    elif t == (c, ac):
                        continue
                    else:
                        par[c].append(self.lt(t, (c, ac)))
            cl = [-l for l in cond]
            sat = False
            for c in rd:
                y = self.xor(par[c], 0)
                if y is True:
                    sat = True
                    break
                if y is False:
                    continue
                cl.append(y)
            if not sat:
                out.append(cl)
        return out

    def dimacs(self, path):
        with open(path, "w") as f:
            f.write(f"p cnf {self.nv} {len(self.cl)}\n")
            for c in self.cl:
                f.write(" ".join(map(str, c)) + " 0\n")


def build(S, types=None):
    C = CNF(S)
    counts = {}
    for b in "ZX":
        cand = candidates(b)
        for tp, lst in sorted(cand.items()):
            counts[f"{b}:{tp}"] = len(lst)
            if types and tp not in types:
                continue
            for slots in lst:
                for cl in C.witness_clauses(b, slots):
                    assert cl, ("schedule-independent witness", b, slots)
                    C.cl.append(cl)
    return C, counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("path", nargs="?")
    ap.add_argument("--S", type=int, default=7)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--out", default=None)
    ap.add_argument("--seed", type=int, default=77)
    a = ap.parse_args()
    if a.cmd == "validate":
        from search.experiments.e039_audit.samp import Sampler
        sp = Sampler(a.S, seed=a.seed)
        ok = bad = 0
        for i in range(a.n):
            tau = sp.sample()
            for b in "ZX":
                mine = to_dem(faults(tau, a.S, b), b)
                c, dm = F.circuit(tau, a.S, b, 1, p=1e-3)
                rd = readers(b)
                assert all(dm[(cc, j)] == j * len(rd) + rd.index(cc) for cc in rd for j in (0, 1))
                st = set(F.dem_mechs(c))
                if mine == st:
                    ok += 1
                else:
                    bad += 1
                    print("MISMATCH", i, b, len(mine), len(st), len(mine - st), len(st - mine), flush=True)
        print(json.dumps({"validate_R1": True, "S": a.S, "equal": ok, "unequal": bad}))
    elif a.cmd == "count":
        for b in "ZX":
            print(b, {tp: len(v) for tp, v in sorted(candidates(b).items())}, flush=True)
    elif a.cmd == "build":
        C, counts = build(a.S)
        C.dimacs(a.out)
        json.dump({"S": a.S, "nv": C.nv, "ncl": len(C.cl), "nlegal": C.nlegal, "counts": counts,
                   "x": {f"{e[0][0]}{e[0][1]}_{e[1]}_{t}": v for (e, t), v in C.x.items()}},
                  open(a.out.replace(".cnf", "_map.json"), "w"))
        print(json.dumps({"nv": C.nv, "ncl": len(C.cl), "counts": counts}))
    elif a.cmd == "cubes":
        mp = json.load(open(a.path.replace(".cnf", "_map.json")))
        x = mp["x"]
        base = open(a.path).read().split("\n", 1)
        h = base[0].split()
        pre = a.path[:-4]
        n = 0
        for t0 in range(1, a.S + 1):
            for t1 in range(1, a.S + 1):
                if t0 == t1:
                    continue
                units = [x[f"Z0_0_{t0}"], x[f"Z0_1_{t1}"]]
                with open(f"{pre}_zcube{n}.cnf", "w") as f:
                    f.write(f"p cnf {h[2]} {int(h[3]) + 2}\n")
                    f.write(base[1])
                    for u in units:
                        f.write(f"{u} 0\n")
                n += 1
        print(n)
    elif a.cmd == "control":
        # fix a given schedule (json checks/tau) as units; my CNF must be SAT iff my DEM search finds no weight <= 3
        from pysat.solvers import Solver
        C, _ = build(a.S)
        d = json.load(open(a.path))
        tau = {(tuple(r["check"]), i): t - r["prep"] for r in d["checks"] for i, t in enumerate(r["tau"])}
        units = [[C.x[(e, tau[e])]] for e in C.ev]
        s = Solver(name="cd15", bootstrap_with=C.cl + units)
        res = s.solve()
        w = [F.dist(tau, a.S, b, 1) for b in "ZX"]
        print(json.dumps({"schedule": a.path, "S": a.S, "own_cnf_sat": res, "my_dem_w": w}))
