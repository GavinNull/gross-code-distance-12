"""E-024a: simulated annealing over pipelined circuits of a family F(H) (or a mixed family) at fixed period P in the
Fig. 12 extended-code class, minimising the number of weight-11 logicals that LIFT in the bulk frame model
(e021.nwfull realisations, wrap weights floor((t2-t1)/P)+1 -- the same model as the CEGAR).  Hard constraints kept at
every step (same as cegar.TimeSAT): per unit distinct times, window <= P-3, first CNOT in [0, P-1], order in the
8-element class; legality (6 times distinct mod P on every data qubit); determinism criterion.
A state with 0 modelled lifting logicals goes to the exact lift (e021.liftscreen R = 1..rmax both bases).
This is the SAT-side heuristic for families where the CEGAR does not converge (it proves nothing when it fails).

    PYTHONPATH=.:tests uv run python -m search.experiments.e024a.sa --P 17 --sub "1,2" --seed 1 --max_sec 3600
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import search.experiments.e021.nwfull as NF
from search.experiments.e021.liftscreen import screen
from search.experiments.e021.mono import fig12_labels
from search.experiments.e021.nwsat import Family, parse_sub
from search.experiments.e024a.cegar import TimeSAT, adapt, bf_P, spec_of

OUT = Path("results/E-024a-gross12-period")
N2 = 72


def allowed_orders(o):
    """the 8 label orders of the class of Fig. 12 order o."""
    out = set()
    for a in (o[:2], o[1::-1]):
        for b in (o[4:], o[:3:-1]):
            f = tuple(a) + (o[2], o[3]) + tuple(b)
            out.add(f)
            out.add(f[::-1])
    assert len(out) == 8
    return out


class State:
    def __init__(self, F, P, t, recs):
        self.F, self.P, self.t = F, P, list(t)
        adapt(F)
        f12 = fig12_labels()
        self.uitems = {u: [F.idx[(u[0], u[1], l)] for l in range(6)] for u in F.units}
        self.uallowed = {u: allowed_orders(f12[u[0]][F.unit_rep[u]]) for u in F.units}
        self.unit_of = {}
        for u, its in self.uitems.items():
            for i in its:
                self.unit_of[i] = u
        self.qitems = []
        self.item_q = {}
        for q in range(144):
            its = sorted({F.item(ty, c, lab) for ty, c, lab in F.touch[q]})
            self.qitems.append(its)
            for i in its:
                self.item_q.setdefault(i, set()).add(q)
        T = F.T
        self.det = []
        seen = set()
        for a in range(N2):
            qa = set(int(x) for x in T["X"][a])
            for c in range(N2):
                ov = sorted(qa & set(int(x) for x in T["Z"][c]))
                if not ov:
                    continue
                pr = tuple((F.item("X", a, F.label_of("X", a, q)), F.item("Z", c, F.label_of("Z", c, q))) for q in ov)
                if pr not in seen:
                    seen.add(pr)
                    self.det.append(pr)
        self.item_det = {}
        for k, pr in enumerate(self.det):
            for x, z in pr:
                self.item_det.setdefault(x, set()).add(k); self.item_det.setdefault(z, set()).add(k)
        # recs and the items they involve
        self.recs = recs
        rd_items = {}
        self.rec_items = []
        for r in recs:
            its = set()
            for e in r["evs"]:
                qs = [e[1]] if e[0] == "d" else list(e[2])
                for q in qs:
                    for ty, c, lab in F.touch[q]:
                        if ty == r["rd"]:
                            its.add(F.item(ty, c, lab))
                    if e[0] == "h":
                        its.add(F.item(r["kind"], e[1], F.label_of(r["kind"], e[1], q)))
            self.rec_items.append(its)
        self.item_recs = {}
        for k, its in enumerate(self.rec_items):
            for i in its:
                self.item_recs.setdefault(i, []).append(k)
        self.lift = [self.eval_rec(k) for k in range(len(recs))]
        self.count = sum(self.lift)

    def eval_rec(self, k):
        t, P = self.t, self.P
        NF.bf_general = lambda cons, rank: bf_P(cons, t, P)  # noqa: E731
        return 1 if NF.evaluate_full(self.F, [self.recs[k]], None) else 0

    def unit_ok(self, u):
        ts = [self.t[i] for i in self.uitems[u]]
        if len(set(ts)) < 6 or max(ts) - min(ts) > self.P - 3 or not (0 <= min(ts) <= self.P - 1):
            return False
        order = tuple(sorted(range(6), key=lambda l: ts[l]))
        return order in self.uallowed[u]

    def local_ok(self, items):
        P, t = self.P, self.t
        qs = set()
        for i in items:
            qs |= self.item_q[i]
        for q in qs:
            r = [t[i] % P for i in self.qitems[q]]
            if len(set(r)) < 6:
                return False
        ds = set()
        for i in items:
            ds |= self.item_det.get(i, set())
        for k in ds:
            (x1, z1), (x2, z2) = self.det[k]
            if (t[x1] - t[z1]) // P != (t[x2] - t[z2]) // P:
                return False
        return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--sub", default="1,2")
    ap.add_argument("--split_units", default="")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max_sec", type=float, default=3600)
    ap.add_argument("--T0", type=float, default=2.0)
    ap.add_argument("--T1", type=float, default=0.2)
    ap.add_argument("--rmax", type=int, default=6)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    P = a.P
    rng = random.Random(a.seed)
    gens = parse_sub(a.sub) if a.sub else [(0, 0)]
    if a.split_units:
        from search.experiments.e024a.mixed import MixedFamily
        F = MixedFamily(gens, {(x[0], int(x[1:])) for x in a.split_units.split(",")})
    else:
        F = Family(gens)
    tag = a.tag or f"sa_P{P}_s{a.sub.replace(',', '').replace(';', '_') or 'triv'}_seed{a.seed}"
    recs, skipped = NF.prepare_full(F, "XZ")
    M = TimeSAT(F, P)
    M.S.set_phases([rng.choice([1, -1]) * v for v in range(1, M.pool.top + 1)])
    t0 = time.time()
    t = M.solve()
    S = State(F, P, t, recs)
    print(f"{tag}: units {len(F.units)} recs {len(recs)} initial lifting {S.count} ({time.time() - t0:.0f}s)", flush=True)
    best = S.count
    log = {"P": P, "sub": a.sub, "split": a.split_units, "seed": a.seed, "trace": [], "lift": []}
    steps = acc = 0
    units = list(F.units)
    status = "NONE"
    while time.time() - t0 < a.max_sec:
        frac = (time.time() - t0) / a.max_sec
        T = a.T0 * (a.T1 / a.T0) ** frac
        u = rng.choice(units)
        its = S.uitems[u]
        old = {i: S.t[i] for i in its}
        mv = rng.random()
        if mv < 0.3:                       # shift whole unit
            d = rng.choice([-2, -1, 1, 2])
            for i in its:
                S.t[i] += d
            mn = min(S.t[i] for i in its)
            if mn < 0 or mn > P - 1:
                sh = P if mn < 0 else -P
                for i in its:
                    S.t[i] += sh
            changed = its
        elif mv < 0.75:                    # move one CNOT
            i = rng.choice(its)
            S.t[i] += rng.choice([-2, -1, 1, 2])
            changed = [i]
            mn = min(S.t[j] for j in its)
            if mn < 0 or mn > P - 1:
                sh = P if mn < 0 else -P
                for j in its:
                    S.t[j] += sh
                changed = its
        else:                              # swap two CNOT times within the unit
            i, j = rng.sample(its, 2)
            S.t[i], S.t[j] = S.t[j], S.t[i]
            changed = [i, j]
        steps += 1
        if not S.unit_ok(u) or not S.local_ok(changed):
            for i, v in old.items():
                S.t[i] = v
            continue
        aff = set()
        for i in changed:
            aff.update(S.item_recs.get(i, []))
        newv = {k: S.eval_rec(k) for k in aff}
        delta = sum(newv[k] - S.lift[k] for k in aff)
        if delta <= 0 or rng.random() < math.exp(-delta / T):
            for k, v in newv.items():
                S.lift[k] = v
            S.count += delta
            acc += 1
            if S.count < best:
                best = S.count
                log["trace"].append({"sec": round(time.time() - t0, 1), "best": best, "steps": steps})
                print({"sec": round(time.time() - t0, 1), "best": best, "steps": steps, "T": round(T, 3)}, flush=True)
            if S.count == 0:
                sp = OUT / f"{tag}_zero{len(log['lift']) + 1}.json"
                sp.write_text(json.dumps(spec_of(F, S.t, P)))
                r = screen(str(sp), a.rmax)
                r["sec"] = round(time.time() - t0, 1)
                log["lift"].append(r)
                print("exact:", r, flush=True)
                if r["status"] == "CERTIFIED":
                    status = "CERTIFIED"; log["spec"] = str(sp); break
        else:
            for i, v in old.items():
                S.t[i] = v
    log.update(status=status, best=best, steps=steps, accepted=acc, sec=round(time.time() - t0, 1))
    print(f"STATUS SA P={P} sub={a.sub} split={a.split_units} seed={a.seed} {status} best={best} steps={steps} "
          f"acc={acc} {log['sec']}s", flush=True)
    (OUT / f"{tag}.json").write_text(json.dumps(log))


if __name__ == "__main__":
    main()
