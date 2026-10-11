"""E-024b step 3 (fast): incremental-SAT version of gen.py's CEGAR (same family, same frame model, same nogoods),
for colour-symmetric circuits of period P in a given extended-code class (any colouring, any per-colour orders).

Family (as e021/cegarP.py): per unit u = (type, colour): start s_u in [0, P) (0 if --nowrap), the 6 CNOTs at
absolute times t = s_u + o, o in [1, P-2] distinct, measurement at s_u + P - 1; per unit the order is any of the 8
orders of the unit's extended-code type (rev Boolean + "first-set" constraints).  Legality: on every data qubit the 6
times are distinct mod P.  Determinism: floor((t_x - t_z)/P) equal on the two shared qubits of each overlapping X/Z
pair (criterion audited 2026-10-08).  Encoding: one-hot t_i, ge[i][k] <=> t_i >= k, difference literals
D(i,j,M) <=> t_j - t_i >= M (defined both ways).
Frame model and nogoods: identical to e021/cegarP.py (bf with weight floor((t_i2-t_i1)/P)+1, clause = OR of
"violating" difference literals).  UNSAT => every circuit of the family has a modelled bulk weight-11 logical.
Model candidates go to the exact lift (gen.lift_screen, R = 1..rmax both bases); failures are blocked exactly.

    PYTHONPATH=.:tests uv run python -m search.experiments.e024b.gsat --col 3,1,1 --x ... --z ... --P 12
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
import time

from pysat.formula import IDPool
from pysat.solvers import Cadical153

import search.experiments.e021.nwfull as NF
from search.experiments.e021.mono import table
from search.experiments.e024b.common import OUT
from search.experiments.e024b.gen import Cls, bf_P, build_family, lift_screen, prepare

N2 = 72


class Enc:
    def __init__(self, F, C, ccol, P, nowrap):
        self.F, self.P = F, P
        self.pool = IDPool()
        self.S = Cadical153()
        self.units = [(ty, k) for ty in "XZ" for k in range(F.nc)]
        hi = P - 2 if nowrap else 2 * P - 2
        self.dom = list(range(1, hi + 1))
        self.lo, self.hi = 1, hi
        n = len(F.items)
        self.x = {(i, v): self.pool.id(("x", i, v)) for i in range(n) for v in self.dom}
        S = self.S
        for i in range(n):
            S.add_clause([self.x[(i, v)] for v in self.dom])
            for v, w in itertools.combinations(self.dom, 2):
                S.add_clause([-self.x[(i, v)], -self.x[(i, w)]])
            for k in range(self.lo + 1, self.hi + 1):
                g = self.ge(i, k)
                for v in self.dom:
                    if v >= k:
                        S.add_clause([-self.x[(i, v)], g])
                    else:
                        S.add_clause([-self.x[(i, v)], -g])
        sdom = [0] if nowrap else list(range(P))
        self.s = {(u, w): self.pool.id(("s", u, w)) for u in self.units for w in sdom}
        for u in self.units:
            S.add_clause([self.s[(u, w)] for w in sdom])
            for w1, w2 in itertools.combinations(sdom, 2):
                S.add_clause([-self.s[(u, w1)], -self.s[(u, w2)]])
            its = [F.idx[(u[0], u[1], l)] for l in range(6)]
            for i in its:
                for v in self.dom:
                    S.add_clause([-self.x[(i, v)]] + [self.s[(u, w)] for w in sdom if 1 <= v - w <= P - 2])
            for i, j in itertools.combinations(its, 2):
                for v in self.dom:
                    S.add_clause([-self.x[(i, v)], -self.x[(j, v)]])
            # order class
            ordr = C.orders[u[0]][ccol[u[1]]]
            rev = self.pool.id(("rev", u))
            it_ = lambda lab: F.idx[(u[0], u[1], lab)]  # noqa: E731

            def first(U, guard):
                for a in U:
                    for b in range(6):
                        if b not in U:
                            S.add_clause(guard + [self.D(it_(a), it_(b), 1)])
            first(ordr[:2], [rev]); first(ordr[:3], [rev]); first(ordr[:4], [rev])
            first(ordr[4:], [-rev]); first(ordr[3:], [-rev]); first(ordr[2:], [-rev])
        S.add_clause([self.s[(("X", 0), 0)]])
        # legality
        pairs = set()
        for q in range(144):
            its = sorted({F.item(ty, c, lab) for ty, c, lab in F.touch[q]})
            assert len(its) == 6
            pairs.update(itertools.combinations(its, 2))
        for i, j in pairs:
            for v in self.dom:
                for w in self.dom:
                    if (v - w) % P == 0:
                        S.add_clause([-self.x[(i, v)], -self.x[(j, w)]])
        # determinism
        T = table()
        seen = set()
        for ia in range(N2):
            qa = set(int(q) for q in T["X"][ia])
            for ic in range(N2):
                ov = sorted(qa & set(int(q) for q in T["Z"][ic]))
                if not ov:
                    continue
                pr = tuple((F.item("X", ia, F.label_of("X", ia, q)), F.item("Z", ic, F.label_of("Z", ic, q)))
                           for q in ov)
                if pr in seen:
                    continue
                seen.add(pr)
                (x1, z1), (x2, z2) = pr
                for k in (-1, 0, 1):
                    a, b = self.D(z1, x1, k * P), self.D(z2, x2, k * P)
                    S.add_clause([-a, b]); S.add_clause([a, -b])
        self.ndet = len(seen)

    def ge(self, i, k):
        return self.pool.id(("ge", i, k))

    def gelit(self, i, k):
        """literal for t_i >= k, or True/False constants"""
        if k <= self.lo:
            return True
        if k > self.hi:
            return False
        return self.ge(i, k)

    def D(self, i, j, M):
        """literal <=> t_j - t_i >= M"""
        key = ("D", i, j, M)
        if key in self.pool.obj2id:
            return self.pool.obj2id[key]
        d = self.pool.id(key)
        for v in self.dom:
            g = self.gelit(j, v + M)
            xv = self.x[(i, v)]
            if g is True:
                self.S.add_clause([-xv, d])
            elif g is False:
                self.S.add_clause([-xv, -d])
            else:
                self.S.add_clause([-xv, -g, d]); self.S.add_clause([-xv, g, -d])
        return d

    def times(self, model):
        ms = set(l for l in model if l > 0)
        t = {}
        for (i, v), var in self.x.items():
            if var in ms:
                t[i] = v
        st = {}
        for (u, w), var in self.s.items():
            if var in ms:
                st[u] = w
        return t, st


def spec_of(F, t, st, P):
    T = table()
    d = {"format": "qec-schedule/v1", "period": P, "x_checks": [], "z_checks": []}
    for ty, key in (("X", "x_checks"), ("Z", "z_checks")):
        for i in range(N2):
            u = (ty, F.cls[i])
            sv = st[u]
            cn = [[int(T[ty][i][l]), t[F.idx[(ty, F.cls[i], l)]] % P] for l in range(6)]
            d[key].append({"prep": sv % P, "meas": (sv + P - 1) % P, "cnots": cn})
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--col", required=True)
    ap.add_argument("--x", required=True)
    ap.add_argument("--z", required=True)
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--nowrap", type=int, default=0)
    ap.add_argument("--max_sec", type=float, default=3600)
    ap.add_argument("--rmax", type=int, default=6)
    ap.add_argument("--tag", default="")
    ap.add_argument("--nologic", type=int, default=0, help="classical control: no logical nogoods")
    ap.add_argument("--maxcand", type=int, default=100000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--stop_on_cert", type=int, default=1)
    a = ap.parse_args()
    P = a.P
    t0 = time.time()
    col = tuple(int(v) for v in a.col.split(","))
    C = Cls(col, a.x, a.z)
    F, ccol = build_family(col)
    recs, skipped = prepare(F, C)
    M = Enc(F, C, ccol, P, a.nowrap)
    rng = random.Random(a.seed)
    print(f"P={P} nowrap={a.nowrap} col={col} reps {len(recs)} skipped {skipped} det {M.ndet} vars {M.pool.top} "
          f"{time.time() - t0:.0f}s", flush=True)
    tag = a.tag or f"gs_{col[0]}{col[1]}{col[2]}_P{P}{'_nw' if a.nowrap else ''}"
    log = {"P": P, "col": col, "x": a.x, "z": a.z, "nowrap": a.nowrap, "reps": len(recs), "skipped": skipped,
           "nologic": a.nologic, "iters": 0, "nogoods": 0, "cands": []}
    status, it, ncand = "UNKNOWN", 0, 0
    while time.time() - t0 < a.max_sec:
        it += 1
        if a.seed:
            M.S.set_phases([v if rng.random() < 0.5 else -v for v in range(1, M.pool.top + 1)])
        if not M.S.solve():
            status = "UNSAT"; break
        t, st = M.times(M.S.get_model())
        if a.nologic:
            lif = []
        else:
            NF.bf_general = lambda cons, rank: bf_P(cons, t, P)  # noqa: E731
            lif = NF.evaluate_full(F, recs, None)
        if not lif:
            ncand += 1
            d = spec_of(F, t, st, P)
            sp = OUT / f"{tag}_cand{ncand}.json"
            sp.write_text(json.dumps(d))
            r = lift_screen(d, C, a.rmax)
            rr = {"n": ncand, "it": it, "status": r["status"], "R": r.get("R"), "basis": r.get("basis"),
                  "spec": str(sp), "sec": round(time.time() - t0, 1)}
            log["cands"].append(rr)
            print("cand", json.dumps(rr), flush=True)
            if r["status"] == "CERTIFIED":
                status = "CERTIFIED"
                if a.stop_on_cert:
                    break
            else:
                sp.unlink()
            if ncand >= a.maxcand:
                status = status if status == "CERTIFIED" else "MAXCAND"; break
            M.S.add_clause([-M.x[(i, v)] for i, v in t.items()])
            continue
        for r_, cons, pi in lif:
            lits = set()
            for u_, w_, kd, (i1, i2) in cons:
                K = pi[u_] - pi[w_]
                if kd in ("free", "hook+"):
                    lits.add(-M.D(i1, i2, (K - 1) * P))       # t_i2 - t_i1 <= (K-1)P - 1
                else:
                    lits.add(M.D(i1, i2, -K * P))              # t_i2 - t_i1 >= -KP
            M.S.add_clause(sorted(lits))
            log["nogoods"] += 1
        if it % 50 == 0 or it < 3:
            print({"it": it, "lifting": len(lif), "nogoods": log["nogoods"], "sec": round(time.time() - t0, 1)},
                  flush=True)
    log.update(status=status, iters=it, sec=round(time.time() - t0, 1), ncand=ncand)
    print(f"STATUS P={P} {status} it={it} cands={ncand} {log['sec']}s", flush=True)
    (OUT / f"{tag}.json").write_text(json.dumps(log))


if __name__ == "__main__":
    main()
