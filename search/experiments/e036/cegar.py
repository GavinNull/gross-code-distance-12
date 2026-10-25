"""E-036 step 5c: exact CEGAR over ALL per-check-free non-wrapping single-ancilla schedules with S CNOT layers.

Template: every measured check prepared at layer 0, its 6 CNOTs in layers 1..S, measured at S+1 (period S+2).
Variables (CP-SAT): t(k, a) in 1..S for check k and term a; all-different per check and per data qubit; determinism
(even number of shared qubits with t_X < t_Z for every overlapping X/Z pair).

Counter-example step: build the SD6 circuit for R = 1..3 (then 4..6), both memory bases; exact meet-in-the-middle
search for an undetectable logical of weight <= d-1 on the full DEM.  For each witness, stim explains every mechanism
by one representative circuit fault; from the fault we read the ORDER LITERALS (relative order of two CNOT events
that share a data qubit or a check) that its detector / observable effect depends on:
  * data qubit q, relevant Pauli component (X in Z memory, Z in X memory) after tick tau: the reader CNOTs
    (checks of the memory basis) on q in that round split into B (at or before tau) and A (after); if the fault sits
    on a CNOT e touching q: lt(b, e), lt(e, a); otherwise lt(b, a) for all b in B, a in A;
  * reader ancilla: flips only its own outcome -> no literal;
  * spreader ancilla (other basis) after tau: its CNOTs in that round split into prefix / suffix (lt(f, g), or via
    the faulty CNOT e), and for every suffix CNOT g on qubit q_g: lt(b, g), lt(g, a) w.r.t. the reader CNOTs on q_g.
If every literal holds in another schedule of the same template, the same faults (or, for idle-type data faults, a
fault at the corresponding gap, which always exists in the template: a CNOT fault, or the data idle in the
prep / meas layer) produce the same detector and observable flips, so that schedule has the same weight-w
undetectable logical.  The nogood is OR(not literal).  UNSAT  =>  no schedule of the family reaches d_circ >= d.
"""
import argparse
import json
import random
import time

import stim  # noqa: F401  (import stim BEFORE ortools: the reverse order makes stim ~10x slower here)
from search.experiments.e036 import common as _c  # noqa: F401
from ortools.sat.python import cp_model
from evaluators import candidate as cand
from search.experiments.e036.common import (OUT, checks, code, dem_mechs, min_weight, noiseless, sd6, spec_from_terms,
                                            term_col)
from evaluators.noise import add_noise
import stim


class Fam:
    def __init__(self, variant, S):
        self.variant, self.S, self.P = variant, S, S + 2
        xs, zs = checks(variant)
        self.cks = [("X", c) for c in xs] + [("Z", c) for c in zs]
        self.cols = {k: [term_col(k[0], k[1], t) for t in range(6)] for k in self.cks}
        self.ev_on_q = {}
        for k in self.cks:
            for a in range(6):
                self.ev_on_q.setdefault(self.cols[k][a], []).append((k, a))
        self.pairs = []
        for kx in self.cks:
            if kx[0] != "X":
                continue
            for kz in self.cks:
                if kz[0] != "Z":
                    continue
                sh = [(a, self.cols[kz].index(q)) for a, q in enumerate(self.cols[kx]) if q in self.cols[kz]]
                if sh:
                    self.pairs.append((kx, kz, sh))
        lay = cand.layout_for(code(variant))
        self.anc = {}
        for i, c in enumerate(xs):
            self.anc[lay.x_anc[i]] = ("X", c)
        for i, c in enumerate(zs):
            self.anc[lay.z_anc[i]] = ("Z", c)
        self.ndata = lay.n

    def spec(self, T):
        xt = {k[1]: T[k] for k in self.cks if k[0] == "X"}
        zt = {k[1]: T[k] for k in self.cks if k[0] == "Z"}
        return spec_from_terms(self.variant, xt, zt, self.P, 0, self.P - 1, 0, self.P - 1)

    def solve(self, nogoods, seed, timeout):
        m = cp_model.CpModel()
        S = self.S
        T = {k: [m.NewIntVar(1, S, "") for _ in range(6)] for k in self.cks}
        for k in self.cks:
            m.AddAllDifferent(T[k])
        for q, evs in self.ev_on_q.items():
            m.AddAllDifferent([T[k][a] for k, a in evs])
        for kx, kz, sh in self.pairs:
            bs = []
            for a, b in sh:
                v = m.NewBoolVar("")
                m.Add(T[kx][a] < T[kz][b]).OnlyEnforceIf(v)
                m.Add(T[kx][a] > T[kz][b]).OnlyEnforceIf(v.Not())
                bs.append(v)
            z = m.NewIntVar(0, len(bs), "")
            m.Add(sum(bs) == 2 * z)
        cache = {}

        def lt(e1, e2):
            key = (e1, e2)
            if key not in cache:
                v = m.NewBoolVar("")
                (k1, a1), (k2, a2) = e1, e2
                m.Add(T[k1][a1] < T[k2][a2]).OnlyEnforceIf(v)
                m.Add(T[k1][a1] > T[k2][a2]).OnlyEnforceIf(v.Not())
                cache[key] = v
            return cache[key]
        for ng in nogoods:
            m.AddBoolOr([lt(e1, e2).Not() for e1, e2 in ng])
        rng = random.Random(seed)
        for k in self.cks:
            for a in range(6):
                m.AddHint(T[k][a], rng.randint(1, S))
        s = cp_model.CpSolver()
        s.parameters.max_time_in_seconds = timeout
        s.parameters.num_workers = 1
        s.parameters.random_seed = seed
        s.parameters.randomize_search = True
        st = s.Solve(m)
        if st == cp_model.INFEASIBLE:
            return "UNSAT"
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return "TIMEOUT"
        return {k: [s.Value(T[k][a]) for a in range(6)] for k in self.cks}

    # ------------------------------------------------------------------ literal extraction
    def nogood_from(self, T, circ, U, basis, mechs, wit):
        reader = basis
        rel = "XY" if basis == "Z" else "ZY"
        # layer of event (k, a) in round j
        base = {}
        for q, s0 in U.start.items():
            base[self.anc[q]] = s0
        P = self.P

        def layer(e, j):
            k, a = e
            return base[k] + P * j + T[k][a]

        def round_of(tau):
            b0 = min(base.values())
            return max(0, (tau - b0) // P)
        lits = set()
        sub = stim.DetectorErrorModel()
        keys = []
        for i in wit:
            d, o = mechs[i]
            targets = [stim.target_relative_detector_id(x) for x in range(d.bit_length()) if d >> x & 1]
            targets += [stim.target_logical_observable_id(x) for x in range(o.bit_length()) if o >> x & 1]
            sub.append("error", 0.001, targets)
        ex = circ.explain_detector_error_model_errors(dem_filter=sub, reduce_to_one_representative_error=True)
        assert len(ex) == len(wit), (len(ex), len(wit))
        for exi in ex:
            loc = exi.circuit_error_locations[0]
            tau = loc.tick_offset
            j = round_of(tau)
            gate_qs = [t.gate_target.value for t in loc.instruction_targets.targets_in_range]
            for fp in loc.flipped_pauli_product:
                Q = fp.gate_target.value
                pa = fp.gate_target.pauli_type
                if pa not in rel:
                    continue
                if Q < self.ndata:
                    reads = [e for e in self.ev_on_q[Q] if e[0][0] == reader]
                    e_here = [e for e in self.ev_on_q[Q] if layer(e, j) == tau]
                    B = [e for e in reads if layer(e, j) <= tau]
                    A = [e for e in reads if layer(e, j) > tau]
                    if e_here and len(gate_qs) == 2:
                        e = e_here[0]
                        lits |= {(b, e) for b in B if b != e} | {(e, a) for a in A}
                    else:
                        lits |= {(b, a) for b in B for a in A}
                else:
                    k = self.anc[Q]
                    if k[0] == reader:
                        continue
                    evs = [(k, a) for a in range(6)]
                    pre = [e for e in evs if layer(e, j) <= tau]
                    suf = [e for e in evs if layer(e, j) > tau]
                    e_here = [e for e in evs if layer(e, j) == tau]
                    if e_here and len(gate_qs) == 2:
                        e = e_here[0]
                        lits |= {(f, e) for f in pre if f != e} | {(e, g) for g in suf}
                    else:
                        lits |= {(f, g) for f in pre for g in suf}
                    for g in suf:
                        qg = self.cols[k][g[1]]
                        reads = [e for e in self.ev_on_q[qg] if e[0][0] == reader]
                        lits |= {(b, g) for b in reads if layer(b, j) < layer(g, j)}
                        lits |= {(g, a) for a in reads if layer(a, j) > layer(g, j)}
        return sorted(lits)

    def check(self, T, Rs, d, max_wit=6):
        spec = self.spec(T)
        out = []
        for R in Rs:
            U = cand.unroll(spec, code(self.variant), R)
            for b in ("Z", "X"):
                circ = sd6(spec, self.variant, b, R)
                mechs, _ = dem_mechs(circ)
                w, wit = min_weight(mechs, d - 1)
                if w is not None:
                    out.append((R, b, w, self.nogood_from(T, circ, U, b, mechs, wit)))
                    if len(out) >= max_wit:
                        return out
        return out


def run(variant, S, d, seed, max_iter, timeout):
    F = Fam(variant, S)
    nogoods = []
    t0 = time.time()
    log = []
    for it in range(max_iter):
        T = F.solve(nogoods, seed + it, timeout)
        if T in ("UNSAT", "TIMEOUT"):
            return {"variant": variant, "S": S, "period": S + 2, "result": T, "iters": it, "nogoods": len(nogoods),
                    "sec": round(time.time() - t0, 1), "log": log[-5:]}
        cex = F.check(T, (1, 2, 3), d)
        if not cex:
            cex = F.check(T, (4, 5, 6), d)
        if not cex:
            spec = F.spec(T)
            path = OUT / f"cegar_{variant}_S{S}.json"
            path.write_text(json.dumps(spec.to_dict()))
            return {"variant": variant, "S": S, "period": S + 2, "result": "FOUND", "iters": it,
                    "nogoods": len(nogoods), "spec": str(path), "sec": round(time.time() - t0, 1)}
        for R, b, w, ng in cex:
            if not ng:
                return {"variant": variant, "S": S, "period": S + 2, "result": "UNSAT(schedule-independent witness)",
                        "R": R, "basis": b, "w": w, "iters": it, "sec": round(time.time() - t0, 1)}
            nogoods.append(ng)
        if it % 20 == 0:
            rec = [it, len(nogoods), round(time.time() - t0, 1), [(R, b, w, len(ng)) for R, b, w, ng in cex][:3]]
            log.append(rec)
            print(json.dumps(rec), flush=True)
    return {"variant": variant, "S": S, "result": "MAXITER", "iters": max_iter, "nogoods": len(nogoods)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("variant")
    ap.add_argument("S", type=int)
    ap.add_argument("--d", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20261025)
    ap.add_argument("--max-iter", type=int, default=20000)
    ap.add_argument("--timeout", type=float, default=600)
    a = ap.parse_args()
    r = run(a.variant, a.S, a.d, a.seed, a.max_iter, a.timeout)
    print(json.dumps(r), flush=True)
    with open(OUT / "cegar.jsonl", "a") as f:
        f.write(json.dumps(r) + "\n")
