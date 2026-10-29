"""Theory A, Lemma F'' (flat hook + data cuts + readout flips): exact bulk lift of the configuration
"one hook (suffix S of check 0, round r) + data qubits L \\ T" for witness logicals L containing T (T = S or its
complement), with data errors at any cut slot and any round, and readout flips; minimises the number of flips.
Built from the signature's absolute CNOT times (own model; reads only the definitions).

    uv run python search/theory/A/lift.py --code bb90 --P 9 --K 20
"""
from __future__ import annotations

import argparse
import itertools
import json
import pickle
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
from ortools.sat.python import cp_model

sys.path.insert(0, "search/theory/A")
from common import Code  # noqa: E402
from pairs import add_logical  # noqa: E402
from sigs import LAB, required  # noqa: E402

OUT = Path("results/theoryA")
RR = range(-2, 3)


def witnesses(C, kind, T, w, K, tl=120.0):
    """up to K logicals of weight <= w containing qubits Hook[0][T] (CP-SAT with no-good cuts)."""
    Hk, Rd, H, L = C.side(kind)
    m = cp_model.CpModel()
    x = [m.NewBoolVar("") for _ in range(C.n)]
    for s in T:
        m.Add(x[int(Hk[0][s])] == 1)
    add_logical(m, [[x[q] for q in np.nonzero(H[i])[0]] for i in range(H.shape[0])],
                [[x[q] for q in np.nonzero(L[i])[0]] for i in range(L.shape[0])])
    m.Add(sum(x) <= w)
    out = []
    t0 = time.time()
    while len(out) < K and time.time() - t0 < tl:
        sv = cp_model.CpSolver()
        sv.parameters.max_time_in_seconds = 30
        sv.parameters.num_workers = 1
        sv.parameters.random_seed = len(out)
        st = sv.Solve(m)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break
        e = [q for q in range(C.n) if sv.Value(x[q])]
        assert not (H[:, e].sum(axis=1) % 2).any() and (L[:, e].sum(axis=1) % 2).any()
        out.append(e)
        m.AddBoolOr([x[q].Not() for q in e])
    return out


class Bulk:
    def __init__(self, C, kind, tH, tR, P):
        self.C, self.P = C, P
        self.Hk, self.Rd, _, _ = C.side(kind)
        self.tH, self.tR = tH, tR
        self.readers = [[] for _ in range(C.n)]
        for c in range(C.N2):
            for b in range(6):
                self.readers[int(self.Rd[c][b])].append((c, b))

    def idx(self, q, t2):
        """detector index on each reader of q for an error at time t2/2."""
        P = self.P
        return [(c, (t2 - 2 * self.tR[b]) // (2 * P) + 1) for c, b in self.readers[q]]

    def solve(self, S, data, budget, want=False):
        """min #readout flips to make hook S (check 0) + data undetected, or None if > budget."""
        P = self.P
        m = cp_model.CpModel()
        contrib = {}  # (c, v) -> list of literals

        def add(c, v, lit):
            contrib.setdefault((c, v), []).append(lit)
        rr = {r: m.NewBoolVar("") for r in RR}
        dopt = []
        fl_of = []
        m.AddExactlyOne(rr.values())
        for r, lit in rr.items():
            for a in S:
                q = int(self.Hk[0][a])
                for c, v in self.idx(q, 2 * (self.tH[a] + r * P)):
                    add(c, v, lit)
        for q in data:
            opts = []
            for (c0, b0) in self.readers[q]:
                for n in RR:
                    lit = m.NewBoolVar("")
                    opts.append(lit)
                    dopt.append((q, b0, n, lit))
                    for c, v in self.idx(q, 2 * (self.tR[b0] + n * P) + 1):
                        add(c, v, lit)
            m.AddExactlyOne(opts)
        checks = sorted({c for c, v in contrib})
        vs = [v for c, v in contrib]
        lo, hi = min(vs) - 1, max(vs) + 1
        flips = []
        for c in checks:
            f = {v: m.NewBoolVar("") for v in range(lo, hi + 1)}
            flips += list(f.values())
            fl_of += [(c, v, f[v]) for v in f]
            for v in range(lo, hi + 2):
                lits = contrib.get((c, v), []) + [f[u] for u in (v, v - 1) if u in f]
                if lits:
                    k = m.NewIntVar(0, len(lits) // 2, "")
                    m.Add(sum(lits) == 2 * k)
        m.Add(sum(flips) <= budget)
        m.Minimize(sum(flips))
        sv = cp_model.CpSolver()
        sv.parameters.num_workers = 1
        sv.parameters.max_time_in_seconds = 20
        st = sv.Solve(m)
        if st == cp_model.OPTIMAL or st == cp_model.FEASIBLE:
            if not want:
                return int(sv.ObjectiveValue())
            r = [r for r, lit in rr.items() if sv.Value(lit)][0]
            faults = [("h", 0, sorted(S), r)] + [("d", q, b, n) for q, b, n, lit in dopt if sv.Value(lit)]
            faults += [("m", c, v) for c, v, lit in fl_of if sv.Value(lit)]
            return int(sv.ObjectiveValue()), faults
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--src", default="")
    ap.add_argument("--K", type=int, default=20)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=0)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    C = Code(a.code)
    d = C.d
    sv = pickle.load(open(OUT / (a.src or f"surv_{a.code}_P{a.P}.pkl"), "rb"))
    surv, times = sv["surv"], sv["times"]
    if a.limit:
        surv, times = surv[:a.limit], times[:a.limit]
    if a.end:
        surv, times = surv[a.start:a.end], times[a.start:a.end]
    req = {k: required(OUT / f"pairs_{a.code}_{k}.json", d) for k in ("X", "Z")}
    wcache = {}

    def wits(kind, T):
        key = (kind, T)
        if key not in wcache:
            wcache[key] = witnesses(C, kind, sorted(T), req[kind][T], a.K)
        return wcache[key]
    res = []
    t0 = time.time()
    for i, (sig, (tx, tz)) in enumerate(zip(surv, times)):
        best = None
        for kind, order, tH, tR in (("X", sig[0], tx, tz), ("Z", sig[1], tz, tx)):
            bk = Bulk(C, kind, list(tH), list(tR), a.P)
            for S in (frozenset(order[4:]), frozenset(order[2:]), frozenset(order[3:])):
                for T in (S, frozenset(range(6)) - S):
                    if T not in req[kind]:
                        continue
                    w = 1 + req[kind][T] - len(T)
                    for Lw in wits(kind, T):
                        data = [q for q in Lw if q not in {int(bk.Hk[0][s]) for s in T}]
                        assert len(data) + 1 <= w
                        fl = bk.solve(sorted(S), data, d - 1 - (len(data) + 1))
                        if fl is not None:
                            tot = len(data) + 1 + fl
                            if best is None or tot < best[0]:
                                best = (tot, kind, "".join(LAB[s] for s in sorted(S)), Lw)
                            break
                    if best and best[0] <= d - 1:
                        break
                if best and best[0] <= d - 1:
                    break
            if best and best[0] <= d - 1:
                break
        res.append(best)
        if i % 50 == 0:
            print(i, best[:3] if best else None, round(time.time() - t0), flush=True)
    killed = sum(1 for b in res if b and b[0] <= d - 1)
    print(json.dumps({"code": a.code, "P": a.P, "n": len(res), "killed": killed,
                      "hist": dict(Counter(b[0] if b else None for b in res))}))
    pickle.dump({"surv": surv, "times": times, "res": res}, open(OUT / f"lift_{a.code}_P{a.P}{a.tag}.pkl", "wb"))


if __name__ == "__main__":
    main()
