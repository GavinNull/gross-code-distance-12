"""c3: upper bound d_circ <= 4 for every R: a weight-4 code logical injected on the data right after the data reset
is undetectable and flips an observable (my circuit, reset and no-reset, both bases, several R).  Also: c2c, the
period-10 picture with ALL checks prep 0 / meas 9 (the E-038 N8 template) has the same mechanism set as period 9.
usage: uv run python -m search.experiments.e041_audit.c3_upper"""
import itertools
import json

import numpy as np

from search.experiments.e039_audit import fcore as F
from search.experiments.e041_audit import core as C

SPEC = "search/experiments/e041/bb18_w9_d4_spec.json"


def w4_logicals(basis):
    out = []
    for qs in itertools.combinations(range(C.ND), 4):
        e = np.zeros(C.ND, np.uint8)
        e[list(qs)] = 1
        if F.is_logical_residual(e, basis):
            out.append(qs)
    return out


def main():
    S = C.load(SPEC)
    res = {}
    for basis in "ZX":
        L = w4_logicals(basis)
        L3 = [qs for qs in itertools.combinations(range(C.ND), 3)
              if F.is_logical_residual(np.bincount(qs, minlength=C.ND).astype(np.uint8), basis)]
        err = "X" if basis == "Z" else "Z"
        ok = tot = 0
        for qs in L[:20]:
            for reset in (True, False):
                for R in (1, 2, 3, 5, 10):
                    c, _ = C.circuit(S, basis, R, reset=reset, inject=[(0, "post", q, err) for q in qs])
                    fired, obs = F.fires(c)
                    tot += 1
                    ok += (not fired) and obs != 0
        res[basis] = dict(n_w4_logicals=len(L), n_w3_logicals=len(L3), injected=tot, undetectable_and_flip=ok)
    # c2c: N8 template picture (all prep 0, meas 9, period 10, same absolute CNOT layers)
    T10 = dict(P=10, sched={k: (0, 9, T) for k, (pi, mu, T) in S["sched"].items()})
    assert not C.legal(T10), C.legal(T10)
    eq = {}
    for basis in "ZX":
        for reset in (True, False):
            for R in range(1, 7):
                eq[f"{basis}{R}{'r' if reset else 'n'}"] = set(C.mechs(S, basis, R, reset)) == set(C.mechs(T10, basis, R, reset))
    res["n8template_equal"] = dict(n=len(eq), all_equal=all(eq.values()), bad=[k for k, v in eq.items() if not v])
    print(json.dumps(res, indent=1))
    json.dump(res, open("results/E-041-audit/c3_upper.json", "w"), indent=1)


if __name__ == "__main__":
    main()
