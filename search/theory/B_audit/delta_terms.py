"""delta as a function of the term pair (i, j) for translation-invariant BB schedules (left shared qubit is
X's A_i term and Z's B_j term).  Uses the evaluator's bb convention: HX = [A | B], HZ = [B^T | A^T].
  uv run python -m search.theory.B_audit.delta_terms gross search/experiments/e032/u11_spec.json
"""
import json
import sys
from collections import defaultdict

import numpy as np

from search.theory.B_audit.common import Bulk, get_code, load_spec_dict, TASK


def terms(name):
    from evaluators.tasks import get_task, _mono_exponents
    fx = get_task(TASK[name]).code_family["fixed"]
    l, m = fx["l"], fx["m"]
    return l, m, [_mono_exponents(t, l, m) for t in fx["A"]], [_mono_exponents(t, l, m) for t in fx["B"]]


def main():
    name, sp = sys.argv[1], sys.argv[2]
    code = get_code(name)
    l, m, A, Bt = terms(name)
    N2 = l * m
    idx = lambda a, b: (a % l) * m + (b % m)
    B = Bulk(load_spec_dict(sp), code, "Z")
    # label: for X check g, left qubit g+A_i -> 'A i'; Z check h, left qubit h - B_j -> 'B j'
    tab = defaultdict(set)
    for c, (order, tm) in enumerate(B.wr):
        a, b = divmod(c, m)
        Xlab = {idx(a + A[i][0], b + A[i][1]): i for i in range(3)}
        assert set(Xlab) <= set(order)
        for z, (ro, rt) in enumerate(B.rd):
            ha, hb = divmod(z, m)
            Zlab = {idx(ha - Bt[j][0], hb - Bt[j][1]): j for j in range(3)}
            sh = set(Xlab) & set(Zlab)
            if not sh:
                continue
            assert len(sh) == 1
            q = sh.pop()
            tab[(Xlab[q] + 1, Zlab[q] + 1)].add(B.sig(z, q, tm[q]))
    M = [[sorted(tab[(i, j)]) for j in (1, 2, 3)] for i in (1, 2, 3)]
    print(json.dumps({"spec": sp, "rows=A_i(X left), cols=B_j(Z left)": M}))


if __name__ == "__main__":
    main()
