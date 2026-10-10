"""E-021 follow-up (2a): compress a non-wrapping frame candidate without changing its gate DAG.

Two class-label items are "related" if some data qubit is touched by both (or they belong to the same check class,
i.e. the same ancilla).  Only the relative order of related items enters the circuit's gate DAG, the determinism
criterion and the frame model.  Longest-path layering of the related-pairs DAG gives the minimal depth D for the
same relative order; period = D + 2 (prep before, measurement after).

    PYTHONPATH=.:tests uv run python -m search.experiments.e021.compress search/experiments/e021/cand1_spec.json out.json
"""
import json
import sys

from evaluators.candidate import parse_schedule
from search.experiments.e021.mono import table

N2 = 72


def compress(sd):
    spec = parse_schedule(sd).canonical()
    D = spec.period
    T = table()
    # items: (type, check, col) with time; relation graph over individual CNOTs
    ev = []
    for ty, chk in (("X", spec.x_checks), ("Z", spec.z_checks)):
        for i, c in enumerate(chk):
            for q, t in c.cnots:
                off = (t - c.prep) % D
                ev.append((off, ty, i, q))
    # level per CNOT: longest chain over CNOTs sharing data qubit or ancilla (non-wrapping frame: off is the time)
    ev.sort()
    level = {}
    last_q, last_a = {}, {}
    for off, ty, i, q in ev:
        lv = 1 + max(last_q.get(q, 0), last_a.get((ty, i), 0))
        level[(ty, i, q)] = lv
        last_q[q] = lv; last_a[(ty, i)] = lv
    Dn = max(level.values())
    P = Dn + 2
    out = {"format": "qec-schedule/v1", "period": P, "x_checks": [], "z_checks": []}
    for ty, key, chk in (("X", "x_checks", spec.x_checks), ("Z", "z_checks", spec.z_checks)):
        for i, c in enumerate(chk):
            out[key].append({"prep": 0, "meas": P - 1, "cnots": [[q, level[(ty, i, q)]] for q, _ in c.cnots]})
    return out, D, P


if __name__ == "__main__":
    sd = json.load(open(sys.argv[1]))
    out, D, P = compress(sd)
    print("period", D, "->", P)
    json.dump(out, open(sys.argv[2], "w"))
