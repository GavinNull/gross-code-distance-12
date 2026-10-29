"""E-040 certificate CNF for class T(P) (see experiments/E-040-min-period.yaml) and a set of bulk witness patterns.

Variables: one-hot CNOT times e[s][l][v]: side s in {X, Z}, label l = A1..B3, X in [0, P-3] (normalised min tX = 0),
Z in [-2P+4, 2P-6] with floor((tX[A1] - tZ[B1]) / P) = 0 (Z instance labelling fixed) and span <= P-3.  Every legal
schedule is equivalent to exactly one such vector (global time shift + relabelling of the Z instances), and the raw
floors (hence every pattern's truth value) depend only on the order type.
Legality: exactly-one; X / Z times distinct; min tX = 0; Z span <= P-3, min tZ <= P-1; on every data qubit the 6 CNOT
times distinct mod P (L: X Ai vs Z Bj, R: X Bj vs Z Ai); determinism floor((tX[Ai]-tZ[Bj])/P) = floor((tX[Bj]-tZ[Ai])/P).
Pattern k (sector X: hook side X, readers Z; sector Z: swapped), with comparison literals lt(a, b, c) <=> t_a < t_b + c:
  hook ('h', c, S, j) present  <=> AND_{m in S, m' not in S} lt(H m', H m, 0);
  hook bit m on q, reader (c', b): flips D(c', j + f + 1), f = floor((tH[m] - tR[b]) / P)
                                   ( f = k  <=>  not lt(H m, R b, kP) and lt(H m, R b, (k+1)P) );
  data ('d', q, b, r), reader (c', b2 != b): flips D(c', r + 1) if lt(R b2, R b, 0) else D(c', r); b2 = b: D(c', r + 1);
  meas ('m', c', r): D(c', r), D(c', r + 1).
  applies(k) <=> all hooks present and every detector flipped an even number of times (Tseitin XOR, full equivalences).
Clause per pattern: NOT applies(k).  UNSAT <=> every legal time vector has a pattern that applies.

    PYTHONPATH=.:tests uv run python -m search.experiments.e040.cnf --code bb90 --P 8 --wit A.jsonl:X B.jsonl:Z --out f.cnf
"""
from __future__ import annotations

import argparse
import json

from search.experiments.e040.codes import MOD

AL, BL = (0, 1, 2), (3, 4, 5)


class Enc:
    def __init__(self, P):
        self.P = P
        self.nv = 0
        self.cl = []
        self.D = {"X": list(range(0, P - 2)), "Z": list(range(-2 * P + 4, 2 * P - 5))}
        self.e = {}
        for s in "XZ":
            for l in range(6):
                for v in self.D[s]:
                    self.e[(s, l, v)] = self.new()
        self.ltc = {}
        self.andc = {}
        self.TRUE = self.new()
        self.cl.append([self.TRUE])
        self.blocking = []
        self.legal()

    def new(self):
        self.nv += 1
        return self.nv

    def legal(self):
        P, D, e = self.P, self.D, self.e
        for s in "XZ":
            for l in range(6):
                vs = [e[(s, l, v)] for v in D[s]]
                self.cl.append(vs)
                for i in range(len(vs)):
                    for j in range(i + 1, len(vs)):
                        self.cl.append([-vs[i], -vs[j]])
            for l in range(6):
                for l2 in range(l + 1, 6):
                    for v in D[s]:
                        self.cl.append([-e[(s, l, v)], -e[(s, l2, v)]])
        self.cl.append([e[("X", l, 0)] for l in range(6)])
        # Z labelling: tX[A1] - P < tZ[B1] <= tX[A1]
        self.cl.append([self.lt(("Z", 3), ("X", 0), 1)])
        self.cl.append([-self.lt(("Z", 3), ("X", 0), -P + 1)])
        for l in range(6):
            for l2 in range(6):
                if l == l2:
                    continue
                for u in D["Z"]:
                    for w in D["Z"]:
                        if u - w > P - 3:
                            self.cl.append([-e[("Z", l, u)], -e[("Z", l2, w)]])
        for xs, zs in ((AL, BL), (BL, AL)):
            for a in xs:
                for b in zs:
                    for u in D["X"]:
                        for w in D["Z"]:
                            if (u - w) % P == 0:
                                self.cl.append([-e[("X", a, u)], -e[("Z", b, w)]])
        for i in range(3):
            for j in range(3):
                for k in range(-4, 5):
                    x = self.lt(("X", AL[i]), ("Z", BL[j]), k * P)
                    y = self.lt(("X", BL[j]), ("Z", AL[i]), k * P)
                    self.cl.append([-x, y])
                    self.cl.append([x, -y])

    def lt(self, a, b, c):
        """literal <=> t_a < t_b + c (constant-folded to TRUE / -TRUE)."""
        key = (a, b, c)
        if key in self.ltc:
            return self.ltc[key]
        Da, Db = self.D[a[0]], self.D[b[0]]
        tr = [(u, w) for u in Da for w in Db if u < w + c]
        if len(tr) == len(Da) * len(Db):
            lit = self.TRUE
        elif not tr:
            lit = -self.TRUE
        else:
            lit = self.new()
            for u in Da:
                for w in Db:
                    ea, eb = self.e[(a[0], a[1], u)], self.e[(b[0], b[1], w)]
                    self.cl.append([lit if u < w + c else -lit, -ea, -eb])
        self.ltc[key] = lit
        return lit

    def AND(self, x, y):
        if x == -self.TRUE or y == -self.TRUE:
            return -self.TRUE
        if x == self.TRUE:
            return y
        if y == self.TRUE:
            return x
        key = (min(x, y), max(x, y))
        if key in self.andc:
            return self.andc[key]
        z = self.new()
        self.cl += [[-z, x], [-z, y], [z, -x, -y]]
        self.andc[key] = z
        return z

    def XOR(self, x, y):
        if x == self.TRUE:
            return -y
        if x == -self.TRUE:
            return y
        if y == self.TRUE:
            return -x
        if y == -self.TRUE:
            return x
        z = self.new()
        self.cl += [[-z, x, y], [-z, -x, -y], [z, -x, y], [z, x, -y]]
        return z

    def pattern(self, sector, faults, C):
        """add the clause NOT applies(pattern); returns the list of condition literals (all true <=> applies)."""
        T = C.table()
        hk, rk = ("X", "Z") if sector == "X" else ("Z", "X")
        TH, TR = T[hk], T[rk]
        readers = [[] for _ in range(C.NQ)]
        for c in range(C.N2):
            for b in range(6):
                readers[int(TR[c][b])].append((c, b))
        conds = []
        flips = {}

        def add(det, lit):
            flips.setdefault(det, []).append(lit)

        P = self.P
        for f in faults:
            if f[0] == "d":
                _, q, b, r = f
                for c2, b2 in readers[q]:
                    if b2 == b:
                        add((c2, r + 1), self.TRUE)
                    else:
                        L = self.lt((rk, b2), (rk, b), 0)
                        add((c2, r + 1), L)
                        add((c2, r), -L)
            elif f[0] == "h":
                _, c, S, j = f
                S = set(S)
                for m in S:
                    for m2 in range(6):
                        if m2 not in S:
                            conds.append(self.lt((hk, m2), (hk, m), 0))
                for m in S:
                    q = int(TH[c][m])
                    for c2, b2 in readers[q]:
                        for k in range(-4, 4):
                            lit = self.AND(-self.lt((hk, m), (rk, b2), k * P), self.lt((hk, m), (rk, b2), (k + 1) * P))
                            if lit != -self.TRUE:
                                add((c2, j + k + 1), lit)
            else:
                _, c2, r = f
                add((c2, r), self.TRUE)
                add((c2, r + 1), self.TRUE)
        for det, lits in sorted(flips.items()):
            s = -self.TRUE
            for x in lits:
                s = self.XOR(s, x)
            conds.append(-s)            # even parity
        blk = [-x for x in conds if x != self.TRUE] if all(x != -self.TRUE for x in conds) else [self.TRUE]
        self.cl.append(blk)
        self.blocking.append(blk)
        return conds

    def write(self, path, comments=()):
        with open(path, "w") as f:
            for c in comments:
                f.write(f"c {c}\n")
            f.write(f"p cnf {self.nv} {len(self.cl)}\n")
            for c in self.cl:
                f.write(" ".join(map(str, c)) + " 0\n")


def load_patterns(specs):
    out = []
    for sp in specs:
        path, sector = sp.rsplit(":", 1)
        for l in open(path):
            w = json.loads(l)
            out.append((sector, [tuple(x) for x in w["faults"]]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--wit", nargs="*", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--shifts", default="0",
                    help="hook-instance shifts j -> j + delta added per pattern: one circuit has several normal forms "
                         "whose Z-instance labelling relative to X differs (same signature, raw G shifted)")
    a = ap.parse_args()
    C = MOD[a.code]
    E = Enc(a.P)
    nleg = len(E.cl)
    pats = load_patterns(a.wit)
    shifts = [int(v) for v in a.shifts.split(",")]
    npat = 0
    for sector, f in pats:
        for d in shifts:
            g = [(x[0], x[1], x[2], x[3] + d) if x[0] == "h" else x for x in f]
            E.pattern(sector, g, C)
            npat += 1
    E.write(a.out, [f"E-040 T({a.P}) {a.code} patterns={len(pats)} shifts={a.shifts} legality_clauses={nleg}"])
    print(json.dumps({"vars": E.nv, "clauses": len(E.cl), "patterns": len(pats), "with_shifts": npat,
                      "legal_clauses": nleg}))


if __name__ == "__main__":
    main()
