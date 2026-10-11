"""E-024a property test of the nogood clauses as ENCODED (audit 2026-10-09 C3 style, but through TimeSAT's literals):
for random admitted circuits A, B of the same family/period: every nogood generated from a lifting logical of A
(and its 24 images), evaluated on B by solving B with assumptions, must satisfy  "all literals false on B => the
(image) logical lifts on B in the model".  Also literal semantics: a literal can be true on B only if its difference
condition holds on B.

    PYTHONPATH=.:tests uv run python -m search.experiments.e024a.nogood_test P "sub" npairs
"""
import random
import sys

import search.experiments.e021.nwfull as NF
from search.experiments.e021.nwsat import Family, parse_sub
from search.experiments.e024a.cegar import TimeSAT, bf_P, item_perms


def main():
    P = int(sys.argv[1]); sub = sys.argv[2]; npairs = int(sys.argv[3])
    F = Family(parse_sub(sub) if sub else [(0, 0)])
    recs, _ = NF.prepare_full(F, "XZ")
    M = TimeSAT(F, P)
    perms = item_perms(F)
    rng = random.Random(7)
    circuits = []
    for _ in range(2 * npairs):
        M.S.set_phases([rng.choice([1, -1]) * v for v in range(1, M.pool.top + 1)])
        circuits.append(M.solve())
    viol = checked = sem_bad = lifted_ok = 0
    for k in range(npairs):
        A, B = circuits[2 * k], circuits[2 * k + 1]
        NF.bf_general = lambda cons, rank: bf_P(cons, A, P)  # noqa: E731
        lif = NF.evaluate_full(F, recs, None)
        for r_, cons, pi in lif[:40]:
            for pm in perms[:6]:
                conds = []
                for u_, w_, kd, (i1, i2) in cons:
                    K = pi[u_] - pi[w_]
                    j1, j2 = pm[i1], pm[i2]
                    if kd in ("free", "hook+"):
                        conds.append(B[j2] - B[j1] <= (K - 1) * P - 1)
                    else:
                        conds.append(B[j1] - B[j2] <= K * P)
                checked += 1
                if not any(conds):
                    # mapped constraints on B must still be satisfied by pi (same pi, images of nodes)
                    def mp(x):
                        return x
                    cons_img = [(u_, w_, kd, (pm[i1], pm[i2])) for u_, w_, kd, (i1, i2) in cons]
                    feas = all(pi[u_] - pi[w_] <= ((B[i2] - B[i1]) // P + 1 if kd != "hook-" else -((B[i2] - B[i1]) // P + 1))
                               for u_, w_, kd, (i1, i2) in cons_img)
                    if not feas:
                        viol += 1
                    else:
                        lifted_ok += 1
            # literal semantics via the SAT encoding: force B, check literal values agree with conditions when forced
        ass = [M.eq(i, B[i]) for i in range(len(B))]
        for (key, lit) in list(M.dcache.items())[:3000]:
            if key[0] != "le":
                continue
            _, a, b, Mv = key
            ok = M.S.solve(assumptions=ass + [lit])
            if ok and not (B[a] - B[b] <= Mv):
                sem_bad += 1
    print(f"P={P} sub={sub!r}: nogood instances checked {checked}, all-false-on-B {lifted_ok + viol}, "
          f"of which pi NOT feasible on B (violation) {viol}; literal semantics violations {sem_bad}")


if __name__ == "__main__":
    main()
