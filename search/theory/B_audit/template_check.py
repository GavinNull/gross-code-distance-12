"""Item 7: does the u11 term template reproduce u11 (gross) and c11 ([[90]]) verbatim?  Own template builder
(evaluator bb convention HX=[A|B], HZ=[B^T|A^T]: X check c -> left c+A_p, right c+B_p; Z check z -> left z-B_p,
right z-A_p).  Also extracts the per-term timing of a given spec and tests translation invariance.

  uv run python -m search.theory.B_audit.template_check
"""
import itertools
import json

from search.theory.B_audit.common import get_code, load_spec_dict
from search.theory.B_audit.delta_terms import terms

U11 = dict(P=11, X=(0, 10, {"A2": 1, "A1": 2, "A3": 3, "B3": 4, "B2": 5, "B1": 9}),
           Z=(10, 9, {"B1": 0, "B2": 4, "B3": 5, "A3": 6, "A1": 7, "A2": 8}))
LAB = ["A1", "A2", "A3", "B1", "B2", "B3"]


def build(name, T, rl=None):
    l, m, A, Bt = terms(name)
    N2 = l * m
    idx = lambda a, b: (a % l) * m + (b % m)
    rl = rl or {x: x for x in LAB}
    xs, zs = [], []
    for c in range(N2):
        a, b = divmod(c, m)
        cx = {f"A{p+1}": idx(a + A[p][0], b + A[p][1]) for p in range(3)}
        cx.update({f"B{p+1}": N2 + idx(a + Bt[p][0], b + Bt[p][1]) for p in range(3)})
        cz = {f"B{p+1}": idx(a - Bt[p][0], b - Bt[p][1]) for p in range(3)}
        cz.update({f"A{p+1}": N2 + idx(a - A[p][0], b - A[p][1]) for p in range(3)})
        px, mx, tx = T["X"]
        pz, mz, tz = T["Z"]
        xs.append((px, mx, frozenset((cx[rl[k]], s) for k, s in tx.items())))
        zs.append((pz, mz, frozenset((cz[rl[k]], s) for k, s in tz.items())))
    return T["P"], xs, zs


def norm(spec):
    f = lambda c: (c["prep"], c["meas"], frozenset((a, t) for a, t in c["cnots"]))
    return spec["period"], [f(c) for c in spec["x_checks"]], [f(c) for c in spec["z_checks"]]


def main():
    out = {}
    for name, sp in (("gross", "search/experiments/e032/u11_spec.json"), ("bb90", "search/experiments/e030/c11_spec.json")):
        target = norm(load_spec_dict(sp))
        hits = []
        for perm in itertools.permutations(LAB):
            rl = dict(zip(LAB, perm))
            # a relabelling must map A-labels to one block and B-labels to the other (else not a template)
            if len({rl[x][0] for x in ("A1", "A2", "A3")}) != 1:
                continue
            if build(name, U11, rl) == target:
                hits.append("".join(f"{k}->{v} " for k, v in rl.items() if k != v) or "identity")
        out[sp] = {"verbatim_relabelings_of_u11_template": hits}
        # also: is the evaluator-generated circuit identical under the canonical form (time-shift invariant)?
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
