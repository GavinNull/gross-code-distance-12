"""E-041 encoder for a W(P) / Mg(P) subclass with per-check OFFSET RANGES: pi_k in [lo_k, hi_k] (absolute layer of the
reset; X0's range is {0} by the global time shift), tau in [lo_k + 1, hi_k + 7], mu in [lo_k + 2, hi_k + 8],
pi < tau < mu, mu - pi <= P - 1 (W) or <= P (Mg).  For P = 9 (W) and P = 8 (Mg) this is exactly "6 CNOTs inside the
7-layer window starting at pi_k + 1" with the window start restricted to [lo_k, hi_k] (theory C lemma 2).
Everything else (distinctness, mod-P data distinctness, determinism parity over instance shifts -2..2, LT literals)
is e038.enc.Enc unchanged (audited); the parity shifts -2..2 cover every overlap because all times lie in an
interval of length < 2P when ranges are narrower than P - 7 ... (asserted below: hi - lo + 7 + spread <= 2P - 3).

build: uv run python -m search.experiments.e041.rng_enc --cls W --P 9 --lo -1 --hi 1 --types HH,HHM,DDH,DHH \
       --out results/E-041-bb18-p9/W9_r1.cnf"""
from __future__ import annotations

import argparse
import itertools
import json
import time

from search.experiments.e036_audit.core import checks, support
from search.experiments.e038.enc import Enc, IntVar, neg


class EncRange(Enc):
    def __init__(self, P, lo, hi, merged=False, variant="bb18"):
        self.variant, self.cls = variant, "Range"
        self.nv = 0
        self.cl = []
        self.ks = checks(variant)
        self.ev = [(k, a) for k in self.ks for a in range(6)]
        self.P = P
        assert lo[0] == hi[0] == 0
        tmin = min(lo) + 1
        tmax = max(hi) + 7
        assert tmax - tmin <= 2 * P - 3, "time range too wide for parity shifts -2..2"
        self.pi = {k: IntVar(self, l, h) for k, l, h in zip(self.ks, lo, hi)}
        self.mu = {k: IntVar(self, l + 2, h + 8) for k, l, h in zip(self.ks, lo, hi)}
        self.tau = {(k, a): IntVar(self, l + 1, h + 7) for k, l, h in zip(self.ks, lo, hi) for a in range(6)}
        self.ltc, self.andc, self.xorc = {}, {}, {}
        gap = P if merged else P - 1
        for k in self.ks:
            for a in range(6):
                self.hard_le(self.pi[k], self.tau[(k, a)], 1)
                self.hard_le(self.tau[(k, a)], self.mu[k], 1)
            self.hard_le(self.mu[k], self.pi[k], -gap)
            for e1, e2 in itertools.combinations([(k, a) for a in range(6)], 2):
                self.distinct(e1, e2, mod=False)
        self.onq = {}
        for k in self.ks:
            for a, q in enumerate(support(k)):
                self.onq.setdefault(q, []).append((k, a))
        for q, evs in self.onq.items():
            for e1, e2 in itertools.combinations(evs, 2):
                self.distinct(e1, e2, mod=True)
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
                for i in (-2, -1, 0, 1, 2):
                    lits = [self.LT((kx, sx.index(q)), (kz, sz.index(q)), i) for q in sh]
                    self.xor_const(lits, 0)


def enc_n8s6():
    """E-038 non-wrapping class N(8) (CNOT layers 1..8) restricted to span <= 6 per check (not both layer 1 and 8).
    Deleting the CNOT-free layer of N(8)'s period 10 (theory C lemma 3) puts every such schedule in W9 (window starts
    1 or 2, period 9) with the same bulk mechanisms."""
    E = Enc("bb18", "N", 8)
    for k in E.ks:
        for a in range(6):
            for b in range(6):
                if a != b:
                    E.add([neg(E.tau[(k, a)].eq(1)), neg(E.tau[(k, b)].eq(8))])
    return E


def build(cls, P, lo, hi, types, out=None):
    from search.experiments.e038.cegar import PatternEncoder
    from search.experiments.e039.static import multisets, patterns_of
    E = enc_n8s6() if cls == "N8s6" else EncRange(P, lo, hi, merged=(cls == "Mg"))
    PE = PatternEncoder(E)
    npat = 0
    t0 = time.time()
    for b in ("Z", "X"):
        for m in multisets("bb18", b, set(types)):
            for pat in patterns_of(b, m):
                for c in PE.clauses(pat):
                    E.add(c)
                npat += 1
    pil = {f"{k[0]}{k[1]}": {v: E.pi[k].eq(v) for v in range(E.pi[k].lo, E.pi[k].hi + 1)} for k in E.ks}
    if out:
        with open(out, "w") as f:
            f.write(f"p cnf {E.nv} {len(E.cl)}\n")
            for c in E.cl:
                f.write(" ".join(map(str, c)) + " 0\n")
        json.dump({"pi_eq": pil, "nv": E.nv, "ncl": len(E.cl), "patterns": npat, "cls": cls, "P": P, "lo": lo,
                   "hi": hi, "types": sorted(types), "build_sec": round(time.time() - t0, 1)},
                  open(out.replace(".cnf", "_map.json"), "w"))
    return E, PE


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cls", default="W")
    ap.add_argument("--P", type=int, default=9)
    ap.add_argument("--lo", type=int, default=-1)
    ap.add_argument("--hi", type=int, default=1)
    ap.add_argument("--types", default="HH,HHM,DDH,DHH")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    lo = [0] + [a.lo] * 13
    hi = [0] + [a.hi] * 13
    E, _ = build(a.cls, a.P, lo, hi, a.types.split(","), a.out)
    print(E.nv, len(E.cl), flush=True)
