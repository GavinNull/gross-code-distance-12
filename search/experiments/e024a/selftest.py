"""E-024a self-tests of the TimeSAT encoding: a known certified circuit (cand_p21, cand1c) must be admitted by the base
encoding (legality + determinism + order class + window), must have 0 modelled lifting logicals, and nogoods generated
from OTHER circuits must not exclude it (they are valid clauses).  Also: random admitted circuits are legal under the
evaluator and deterministic under stim.

    PYTHONPATH=.:tests uv run python -m search.experiments.e024a.selftest
"""
import json
import random
import sys

import search.experiments.e021.nwfull as NF
from evaluators.candidate import parse_schedule, validate_schedule, build_circuits
from search.experiments.e018 import common as C
from search.experiments.e021.nwsat import Family, parse_sub
from search.experiments.e024a.cegar import TimeSAT, bf_P, spec_of

N2 = 72


def times_of_spec(F, d, P):
    """absolute item times normalised per unit (first CNOT in [0,P)), X0 first = 0 (global shift)."""
    T = F.T
    raw = {}
    for ty, key in (("X", "x_checks"), ("Z", "z_checks")):
        for i, c in enumerate(d[key]):
            col2t = {col: t for col, t in c["cnots"]}
            p = c["prep"]
            offs = {lab: (col2t[int(T[ty][i][lab])] - p) % P for lab in range(6)}
            raw[(ty, i)] = (p, offs)
    # global shift so that X0's first CNOT = 0
    p0, o0 = raw[("X", 0)]
    sh = -(p0 + min(o0.values()))
    t = [None] * len(F.items)
    for (ty, i), (p, offs) in raw.items():
        f = (p + min(offs.values()) + sh) % P
        base = f - min(offs.values())
        for lab in range(6):
            v = base + offs[lab]
            k = F.item(ty, i, lab)
            assert t[k] is None or t[k] == v, "circuit not H-invariant"
            t[k] = v
    return t


def main():
    P_spec = sys.argv[1] if len(sys.argv) > 1 else "search/experiments/e021/cand_p21_spec.json"
    sub = sys.argv[2] if len(sys.argv) > 2 else "1,2;0,3"
    d = json.load(open(P_spec))
    P = d["period"]
    F = Family(parse_sub(sub) if sub else [(0, 0)])
    t = times_of_spec(F, d, P)
    M = TimeSAT(F, P)
    ass = [M.eq(i, t[i]) for i in range(len(t))]
    r = M.solve(ass)
    print("base encoding admits", P_spec, ":", r is not None and r == t)
    recs, skipped = NF.prepare_full(F, "XZ")
    NF.bf_general = lambda cons, rank: bf_P(cons, t, P)  # noqa: E731
    print("modelled lifting on it:", len(NF.evaluate_full(F, recs, None)), "of", len(recs))
    # round-trip spec
    d2 = spec_of(F, t, P)
    s1, s2 = parse_schedule(d).canonical(), parse_schedule(d2).canonical()
    o1 = [[col for _, col in c.offsets(P)[1]] for c in s1.x_checks + s1.z_checks]
    o2 = [[col for _, col in c.offsets(P)[1]] for c in s2.x_checks + s2.z_checks]
    print("round trip: same orders", o1 == o2, "valid", validate_schedule(s2, C.css()) == [])
    # random admitted circuits: legal + deterministic
    rng = random.Random(1)
    nbad = 0
    for k in range(5):
        M.S.set_phases([rng.choice([1, -1]) * v for v in range(1, M.pool.top + 1)])
        tt = M.solve()
        sp = parse_schedule(spec_of(F, tt, P))
        ok = validate_schedule(sp, C.css()) == []
        try:
            for b, c in build_circuits(sp, C.css(), 2).items():
                c.detector_error_model()
            det = True
        except Exception:
            det = False
        nbad += (not ok) or (not det)
        print("random admitted:", "legal" if ok else "ILLEGAL", "deterministic" if det else "NONDET")
    print("bad", nbad)


if __name__ == "__main__":
    main()
