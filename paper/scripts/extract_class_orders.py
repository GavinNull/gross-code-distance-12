"""Print the per-colour-class CNOT order and time steps of a gross-code schedule spec.

Used for Table I of paper/draft.tex (cand_p21) and Fig. 1 of paper/figures_plan.md.
Usage: uv run python paper/scripts/extract_class_orders.py search/experiments/e021/cand_p21_spec.json
Conventions: check index i = 6x + y on the 12 x 6 torus; colour = (x + y) mod 3;
A = x^3 + y + y^2 -> labels A1, A2, A3; B = y^3 + x + x^2 -> labels B1, B2, B3.
X check (x,y) acts on L qubit (x,y)+shift(A_k) and R qubit (x,y)+shift(B_k);
Z check (x,y) acts on L qubit (x,y)-shift(B_k) and R qubit (x,y)-shift(A_k).
The script asserts that this labelling reproduces every check's support and that
each (type, colour) class has a single (order, times) pattern. Order is cyclic from prep.
"""
import json
import sys
from collections import defaultdict

L, M = 12, 6
A = [("A1", (3, 0)), ("A2", (0, 1)), ("A3", (0, 2))]
B = [("B1", (0, 3)), ("B2", (1, 0)), ("B3", (2, 0))]


def idx(a, b):
    return 6 * (a % L) + (b % M)


def labels(i, typ):
    x, y = divmod(i, 6)
    out = {}
    if typ == "X":
        for n, (dx, dy) in A:
            out[idx(x + dx, y + dy)] = n
        for n, (dx, dy) in B:
            out[72 + idx(x + dx, y + dy)] = n
    else:
        for n, (dx, dy) in B:
            out[idx(x - dx, y - dy)] = n
        for n, (dx, dy) in A:
            out[72 + idx(x - dx, y - dy)] = n
    return out


def main(path):
    d = json.load(open(path))
    P = d["period"]
    cls = defaultdict(set)
    for typ, key in (("X", "x_checks"), ("Z", "z_checks")):
        for i, c in enumerate(d[key]):
            lab = labels(i, typ)
            assert {q for q, _ in c["cnots"]} == set(lab), (typ, i)
            x, y = divmod(i, 6)
            prep = c["prep"]
            seq = tuple(
                (lab[q], t)
                for q, t in sorted(c["cnots"], key=lambda e: (e[1] - prep) % P)
            )
            cls[(typ, (x + y) % 3)].add((seq, prep, c["meas"]))
    print(f"period {P}")
    for k in sorted(cls):
        assert len(cls[k]) == 1, k
        seq, prep, meas = next(iter(cls[k]))
        print(f"{k[0]}{k[1]}  prep {prep:2d}  meas {meas:2d}  order "
              + " ".join(n for n, _ in seq) + "  times " + " ".join(str(t) for _, t in seq))


if __name__ == "__main__":
    main(sys.argv[1])
