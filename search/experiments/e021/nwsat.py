"""E-021 step 2: CEGAR over CNOT ORDER + TIMING jointly, symmetric non-wrapping frame circuits, bulk frame model.

Family F(Hs): Hs = subgroup of the 72 translations (given by generators).  Checks of each type are split into
Hs-orbits ("classes"); all checks of a class use the same CNOT times per monomial label (so the per-check CNOT
order is Hs-invariant and is itself a free variable).  Non-wrapping frame: every check does prep, its 6 CNOTs and
measurement inside one frame of length P, frames repeat.  In the bulk frame model (E-018 frame_model.feasible;
audit 2026-10-08 C1) only the relative order of CNOT times on a common data qubit matters, so WLOG the 6*(#X
classes + #Z classes) class-label times form a strict total order (ties can be broken without changing any relation
between two CNOTs on one data qubit); any total order is realisable with P = #items + 2.  So F(Hs) = all strict total
orders of the items, encoded by Boolean lt(x, y) with transitivity.

Constraints (all exact):
  determinism: X check a, Z check c with a∩c = {u,v}:  lt(a_u, c_u) == lt(a_v, c_v)   (E-018 audit 121/121 vs stim)
  d_ext = 11 (necessary part): no class may have a "bad" prefix triple (pairs.py --size 3: triple + 9 data = weight-10
     extended logical); further weight-10 logicals are checked afterwards by DFS on the candidate's orders.
Lifting logicals modelled (lazy): every "10 data + 1 pair hook" logical.  For a class with prefix pair t1 and suffix
  pair t3, the hook of pair t (at a check a of the class) = X (Z) errors on u, v at a's CNOT times on u, v
  (suffix: forward propagation; prefix: ancilla error after CNOT 2 == errors on q1 at tau1 and q2 at tau2 modulo the
  trivial ancilla error at preparation).  Logical = weight-12 code logical containing {u,v} (pairs.py, translated).
  Model (non-wrapping): free qubit w read by c, d: H_c - H_d <= [t_d > t_c];  pinned q: H_c - F = [t_a(q) > t_c(q)].
  Lifts <=> no negative cycle.  Logicals with |Q∩c| > 2 for some reader are skipped (sound for UNSAT).
Nogood for a lifting logical with potential pi: OR of [hook absent] and every relation flip that could violate a
  tight constraint (free/hook+: weight 1 -> 0 when pi_u - pi_w = 1; hook-: weight 0 -> -1 when pi_u - pi_w = 0).
  Valid: if no literal holds, pi stays feasible and the logical still lifts (bulk weight-11 undetected logical).
UNSAT  => every circuit of F(Hs) (any CNOT orders that are Hs-invariant with d_ext-allowed triples) has a bulk
          weight-11 undetected logical  =>  d_circ <= 11 for enough rounds.
SAT, no lifting => CANDIDATE (then: d_ext DFS, exact lift).

    PYTHONPATH=. uv run python -m search.experiments.e021.nwsat --sub "" --kinds XZ
"""
from __future__ import annotations

import argparse
import itertools
import json
import time
from pathlib import Path

from pysat.formula import IDPool
from pysat.solvers import Cadical153

from search.experiments.e018 import common as C
from search.experiments.e021.mono import LAB, table

OUT = Path("results/E-021-gross-new-orders")
N2 = 72


def subgroup(gens):
    Hs = {(0, 0)}
    while True:
        N = Hs | {((h[0] + g[0]) % 12, (h[1] + g[1]) % 6) for h in Hs for g in gens}
        if N == Hs:
            return sorted(Hs)
        Hs = N


def parse_sub(s):
    if not s:
        return [(0, 0)] if s == "" else None
    return [tuple(int(v) for v in g.split(",")) for g in s.split(";")]


class Family:
    def __init__(self, gens, fixed_orders=None):
        """gens: generators of Hs ("" -> trivial... use 'all' for the full group).  fixed_orders: optional dict
        {('X'|'Z', class): label order} to pin orders."""
        self.Hs = subgroup(gens)
        self.T = table()
        # classes = Hs-orbits of check indices (same orbits for X and Z rows)
        cls = [-1] * N2
        reps = []
        for i in range(N2):
            if cls[i] >= 0:
                continue
            for h in self.Hs:
                pr, _ = C.tr(*h)
                cls[int(pr[i])] = len(reps)
            reps.append(i)
        self.cls, self.reps = cls, reps
        self.nc = len(reps)
        self.items = [(ty, k, lab) for ty in "XZ" for k in range(self.nc) for lab in range(6)]
        self.idx = {it: n for n, it in enumerate(self.items)}
        # readers: data qubit -> list of (type, check, label)
        self.touch = [[] for _ in range(144)]
        for ty in "XZ":
            for i in range(N2):
                for lab in range(6):
                    self.touch[int(self.T[ty][i][lab])].append((ty, i, lab))
        self.fixed = fixed_orders or {}

    def item(self, ty, check, lab):
        return self.idx[(ty, self.cls[check], lab)]

    def label_of(self, ty, check, q):
        return int(list(self.T[ty][check]).index(q))


def load_pair_logicals(kind):
    """{pair-type (l1,l2): list of 12-qubit supports at check 0 (data qubits incl. the pair)}"""
    d = json.loads((OUT / f"pairs_{kind}_size2_W11.json").read_text())
    out = {}
    for name, v in d.items():
        t = tuple(sorted(LAB.index(name[i:i + 2]) for i in (0, 2)))
        S = tuple(v["support"])
        out[t] = [tuple(sorted([c for c in sol if c < 144] + list(S))) for sol in v["sols"]]
        for s in out[t]:
            assert len(s) == 12
    return out


def prepare(F: Family, kinds):
    """List of logical records: dict(kind, cls, t, qubits, hook=(a, u, v), cons skeleton)."""
    recs, skipped = [], 0
    for kind in kinds:
        rd = "Z" if kind == "X" else "X"
        PL = load_pair_logicals(kind)
        for k, a in enumerate(F.reps):
            g = divmod(a, 6)
            _, pc = C.tr(*g)
            assert int(C.tr(*g)[0][0]) == a
            for t, sols in PL.items():
                for s in sols:
                    qs = [int(pc[q]) for q in s]
                    u, v = (int(F.T[kind][a][t[0]]), int(F.T[kind][a][t[1]]))
                    assert u in qs and v in qs
                    # readers
                    cnt = {}
                    for q in qs:
                        for ty, c, lab in F.touch[q]:
                            if ty == rd:
                                cnt[c] = cnt.get(c, 0) + 1
                    assert all(x % 2 == 0 for x in cnt.values())
                    if max(cnt.values()) > 2:
                        skipped += 1
                        continue
                    cons = []      # (node_u, node_w, kind, (item1, item2)): H[node_u] - H[node_w] <= wt
                    for q in qs:
                        rds = [(c, F.item(rd, c, lab)) for ty, c, lab in F.touch[q] if ty == rd]
                        if q in (u, v):
                            ia = F.item(kind, a, F.label_of(kind, a, q))
                            for c, ic in rds:
                                # H_c - F = [t_a > t_c]
                                cons.append((("c", c), ("F",), "hook+", (ic, ia)))
                                cons.append((("F",), ("c", c), "hook-", (ic, ia)))
                        else:
                            for (c, ic), (d, idd) in itertools.permutations(rds, 2):
                                cons.append((("c", c), ("c", d), "free", (ic, idd)))   # wt = [t_d > t_c]
                    recs.append({"kind": kind, "cls": k, "t": t, "qubits": qs, "cons": cons})
    return recs, skipped


def bf(cons, rank):
    nodes, edges = {}, []
    for u, w, kd, (i1, i2) in cons:
        iu = nodes.setdefault(u, len(nodes)); iw = nodes.setdefault(w, len(nodes))
        if kd == "free":
            wt = 1 if rank[i2] > rank[i1] else 0
        elif kd == "hook+":
            wt = 1 if rank[i2] > rank[i1] else 0
        else:
            wt = -(1 if rank[i2] > rank[i1] else 0)
        edges.append((iu, iw, wt))
    d = [0] * len(nodes)
    for _ in range(len(nodes) + 1):
        ch = False
        for iu, iw, wt in edges:
            if d[iw] + wt < d[iu]:
                d[iu] = d[iw] + wt; ch = True
        if not ch:
            return {k: d[i] for k, i in nodes.items()}
    return None


class Model:
    def __init__(self, F: Family, bad_triples):
        self.F = F
        self.pool = IDPool()
        self.S = Cadical153()
        n = len(F.items)
        self.n = n
        for x, y, z in itertools.permutations(range(n), 3):
            self.S.add_clause([-self.lt(x, y), -self.lt(y, z), self.lt(x, z)])
        # determinism
        nd = 0
        seen = set()
        for a in range(N2):
            for c in range(N2):
                qa = set(int(q) for q in F.T["X"][a]); qc = set(int(q) for q in F.T["Z"][c])
                ov = sorted(qa & qc)
                if not ov:
                    continue
                assert len(ov) == 2
                u, v = ov
                l1 = (F.item("X", a, F.label_of("X", a, u)), F.item("Z", c, F.label_of("Z", c, u)))
                l2 = (F.item("X", a, F.label_of("X", a, v)), F.item("Z", c, F.label_of("Z", c, v)))
                key = tuple(sorted([l1, l2]))
                if key in seen:
                    continue
                seen.add(key)
                A, B = self.lt(*l1), self.lt(*l2)
                if A == B:
                    continue
                self.S.add_clause([-A, B]); self.S.add_clause([A, -B]); nd += 1
        self.ndet = nd
        # forbidden prefix (and suffix) triples, per class of each type
        for ty in "XZ":
            for k in range(F.nc):
                for T in bad_triples[ty]:
                    Tc = [y for y in range(6) if y not in T]
                    cl = [self.lt(F.idx[(ty, k, y)], F.idx[(ty, k, x)]) for x in T for y in Tc]
                    self.S.add_clause(cl)     # not (all of T before all of Tc)
        # fixed orders
        for (ty, k), o in F.fixed.items():
            for i in range(5):
                self.S.add_clause([self.lt(F.idx[(ty, k, o[i])], F.idx[(ty, k, o[i + 1])])])
        self.hook_lit = {}
        self.nnogood = 0

    def lt(self, x, y):
        """literal for t_x < t_y"""
        if x < y:
            return self.pool.id(("lt", x, y))
        return -self.pool.id(("lt", y, x))

    def present(self, ty, k, t, pos):
        """aux literal p -> pair t occupies the prefix (pos 0) / suffix (pos 1) of class (ty,k)."""
        key = (ty, k, t, pos)
        if key not in self.hook_lit:
            p = self.pool.id(("pres",) + key)
            ins = [self.F.idx[(ty, k, x)] for x in t]
            outs = [self.F.idx[(ty, k, y)] for y in range(6) if y not in t]
            lits = [self.lt(i, o) if pos == 0 else self.lt(o, i) for i in ins for o in outs]
            # p <-> AND lits
            for l in lits:
                self.S.add_clause([-p, l])
            self.S.add_clause([p] + [-l for l in lits])
            self.hook_lit[key] = p
        return self.hook_lit[key]

    def solve(self):
        if not self.S.solve():
            return None
        m = set(l for l in self.S.get_model() if l > 0)
        rank = [0] * self.n
        for x in range(self.n):
            rank[x] = sum(1 for y in range(self.n) if y != x and (self.lt(y, x) in m if self.lt(y, x) > 0
                                                                     else -self.lt(y, x) not in m))
        assert sorted(rank) == list(range(self.n))
        return rank

    def nogood(self, rec, pos, pi):
        lits = [-self.present(rec["kind"], rec["cls"], rec["t"], pos)]
        for u, w, kd, (i1, i2) in rec["cons"]:
            K = pi[u] - pi[w]
            if kd in ("free", "hook+") and K == 1:
                lits.append(-self.lt(i1, i2))       # weight [t_i2 > t_i1] must become 0
            elif kd == "hook-" and K == 0:
                lits.append(self.lt(i1, i2))        # weight -[t_i2 > t_i1] must become -1
        self.S.add_clause(sorted(set(lits)))
        self.nnogood += 1


def class_orders(F, rank):
    out = {}
    for ty in "XZ":
        for k in range(F.nc):
            labs = sorted(range(6), key=lambda lab: rank[F.idx[(ty, k, lab)]])
            out[(ty, k)] = tuple(labs)
    return out


def evaluate(F, recs, rank):
    """returns list of (rec, pos, pi) of lifting logicals whose hook is present."""
    co = class_orders(F, rank)
    lifting = []
    for r in recs:
        o = co[(r["kind"], r["cls"])]
        pos = 0 if tuple(sorted(o[:2])) == r["t"] else (1 if tuple(sorted(o[4:])) == r["t"] else None)
        if pos is None:
            continue
        pi = bf(r["cons"], rank)
        if pi is not None:
            lifting.append((r, pos, pi))
    return lifting


def bad_triples_all():
    out = {}
    for ty in "XZ":
        d = json.loads((OUT / f"pairs_{ty}_size3_W11.json").read_text())
        bad = set()
        for name, v in d.items():
            if v["n"] > 0:
                T = tuple(sorted(LAB.index(name[i:i + 2]) for i in range(0, 6, 2)))
                bad.add(T)
                bad.add(tuple(y for y in range(6) if y not in T))
        out[ty] = sorted(bad)
    return out


# ------------------------------------------------------------------ lazy d_ext >= 11 (both kinds) via DFS witnesses
def realisations(F: Family, kind):
    """key (bytes) -> list of (check, frozenset(labels)) over all label subsets of size 2..4 of every check of
    type `kind` (all possible hook residuals; |U| = 1, 5 are data-equivalent)."""
    H, L = C.HLk(kind)
    out = {}
    for a in range(N2):
        for size in (2, 3, 4):
            for U in itertools.combinations(range(6), size):
                qs = [int(F.T[kind][a][x]) for x in U]
                k = (H[:, qs].sum(1) % 2).astype("uint8").tobytes() + (L[:, qs].sum(1) % 2).astype("uint8").tobytes()
                out.setdefault(k, []).append((a, frozenset(U)))
    return out


class DextLazy:
    def __init__(self, F, M, workers):
        self.F, self.M, self.workers = F, M, workers
        self.real = {k: realisations(F, k) for k in "XZ"}
        self.suf, self.pres = {}, {}
        self.cache = {}
        self.ncl = 0

    def suffix_lit(self, ty, k, U):
        key = (ty, k, U)
        if key not in self.suf:
            s = self.M.pool.id(("suf",) + (ty, k, tuple(sorted(U))))
            lits = [self.M.lt(self.F.idx[(ty, k, y)], self.F.idx[(ty, k, x)]) for x in U for y in range(6) if y not in U]
            self.M.S.add_clause([s] + [-l for l in lits])          # AND -> s
            self.suf[key] = s
        return self.suf[key]

    def present_lit(self, kind, colkey):
        if (kind, colkey) not in self.pres:
            p = self.M.pool.id(("colpres", kind, colkey))
            for a, U in self.real[kind].get(colkey, []):
                self.M.S.add_clause([-self.suffix_lit(kind, self.F.cls[a], U), p])   # any realisation -> p
            self.pres[(kind, colkey)] = p
        return self.pres[(kind, colkey)]

    def check(self, orders):
        """orders: {(ty, class): label order}.  Returns list of (kind, witness info) for kinds with d_ext <= 10,
        adding a nogood for each; [] if d_ext >= 11 on both kinds (complete DFS)."""
        from search.experiments.e021.extgen import ext_dfs, ext_general
        bad = []
        for kind in "XZ":
            lab = [orders[(kind, self.F.cls[i])] for i in range(N2)]
            ck = (kind, tuple(lab))
            if ck in self.cache:
                res = self.cache[ck]
            else:
                E = ext_general(kind, lab)
                sols, nodes, complete = ext_dfs(kind, lab, 10, stopfirst=1, workers=self.workers, E=E)
                keys = []
                if sols:
                    for j in sols[0]:
                        sup = E["col_sups"][j]
                        if any(len(x) == 1 for x in sup):
                            continue
                        keys.append(E["He"][:, j].tobytes() + E["Le"][:, j].tobytes())
                res = (bool(sols), keys, nodes, complete, len(E["group"]))
                self.cache[ck] = res
            if res[0]:
                cl = [-self.present_lit(kind, k) for k in res[1]]
                self.M.S.add_clause(cl)
                self.ncl += 1
                bad.append((kind, len(res[1]), res[2]))
        return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", default="all", help="'all' = 72-element group (uniform), else generators 'a,b;a,b'")
    ap.add_argument("--kinds", default="XZ")
    ap.add_argument("--fixed", default="", help="json file with fixed class orders")
    ap.add_argument("--fig12", type=int, default=0, help="pin every class to its Fig. 12 order")
    ap.add_argument("--only", type=int, default=-1, help="positive control: keep only the first N logical reps")
    ap.add_argument("--no_triple", type=int, default=0, help="do not forbid d_ext<=10 triples (family = ALL orders)")
    ap.add_argument("--max_sec", type=float, default=7200)
    ap.add_argument("--fig12class", type=int, default=0,
                    help="restrict every class to orders with the SAME extended code as its Fig. 12 order "
                         "(within-pair swaps of positions 1-2 / 5-6 and reversal): d_ext = 11 and the E-018 "
                         "weight-11 list (4224 per kind) are then exact for the whole family")
    ap.add_argument("--dext", type=int, default=0, help="require d_ext >= 11 on both kinds (lazy DFS witnesses)")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    gens = [(1, 0), (0, 1)] if a.sub == "all" else parse_sub(a.sub)
    fixed = {}
    if a.fixed:
        fixed = {(k.split(",")[0], int(k.split(",")[1])): tuple(v) for k, v in json.loads(Path(a.fixed).read_text()).items()}
    t0 = time.time()
    F = Family(gens, fixed)
    if a.fig12:
        from search.experiments.e021.mono import fig12_labels
        f = fig12_labels()
        F.fixed = {(ty, k): f[ty][F.reps[k]] for ty in "XZ" for k in range(F.nc)}
        for ty in "XZ":
            for i in range(N2):
                assert f[ty][i] == f[ty][F.reps[F.cls[i]]], "Fig. 12 orders not Hs-invariant"
    if a.fig12class:
        from search.experiments.e021.mono import fig12_labels
        f12 = fig12_labels()
    recs, skipped = prepare(F, a.kinds)
    if a.only >= 0:
        recs = recs[:a.only]
    M = Model(F, {"X": [], "Z": []} if a.no_triple else bad_triples_all())
    if a.fig12class:
        for ty in "XZ":
            for k in range(F.nc):
                o = f12[ty][F.reps[k]]
                for i in range(N2):
                    assert F.cls[i] != k or f12[ty][i] == o, "Fig. 12 orders not Hs-invariant"
                rev = M.pool.id(("rev", ty, k))
                it_ = lambda lab: F.idx[(ty, k, lab)]  # noqa: E731

                def first(U, guard):
                    for x in U:
                        for y in range(6):
                            if y not in U:
                                M.S.add_clause(guard + [M.lt(it_(x), it_(y))])
                # not reversed: P1 = o[:2] first, T = o[:3] first, P3 = o[4:] last
                first(o[:2], [rev]); first(o[:3], [rev]); first(o[:4], [rev])
                # reversed: P3 first, T^c first, P1 last
                first(o[4:], [-rev]); first(o[3:], [-rev]); first(o[2:], [-rev])
    print(f"|Hs|={len(F.Hs)} classes={F.nc} items={len(F.items)} logical reps={len(recs)} skipped={skipped} "
          f"det={M.ndet} {time.time() - t0:.1f}s", flush=True)
    tag = a.tag or f"nw_H{len(F.Hs)}_{a.sub.replace(';', '_').replace(',', '')}_{a.kinds}"
    log = {"no_triple": a.no_triple, "sub": a.sub, "Hs": len(F.Hs), "classes": F.nc, "kinds": a.kinds, "reps": len(recs), "skipped": skipped,
           "iters": []}
    status, it = "UNKNOWN", 0
    DL = DextLazy(F, M, a.workers) if a.dext else None
    log["dext_rejects"] = []
    while time.time() - t0 < a.max_sec:
        it += 1
        rank = M.solve()
        if rank is None:
            status = "UNSAT"; break
        lif = evaluate(F, recs, rank)
        if not lif and DL is not None:
            co = class_orders(F, rank)
            bad = DL.check(co)
            if bad:
                log["dext_rejects"].append({"it": it, "orders": {f"{k[0]},{k[1]}": list(v) for k, v in co.items()},
                                            "bad": bad})
                print("d_ext<=10 reject", bad, {f"{k[0]}{k[1]}": "".join(LAB[x] for x in v) for k, v in co.items()},
                      f"{time.time() - t0:.0f}s", flush=True)
                continue
        if not lif:
            status = "CANDIDATE"
            log["candidate_rank"] = rank
            log["candidate_orders"] = {f"{k[0]},{k[1]}": list(v) for k, v in class_orders(F, rank).items()}
            break
        for r, pos, pi in lif:
            M.nogood(r, pos, pi)
        rec = {"it": it, "lifting": len(lif), "nogoods": M.nnogood, "sec": round(time.time() - t0, 1)}
        log["iters"].append(rec)
        if it % 20 == 0 or it < 4:
            print(rec, flush=True)
    log.update(status=status, iterations=it, sec=round(time.time() - t0, 1), nogoods=M.nnogood)
    print(f"STATUS {status} it={it} nogoods={M.nnogood} {log['sec']}s", flush=True)
    (OUT / f"{tag}.json").write_text(json.dumps(log))


if __name__ == "__main__":
    main()
