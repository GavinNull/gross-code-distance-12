"""Print a circuit specification in the form of Table I / Tables S1-S2 of the paper.

Checks are grouped by type and colour (x + y) mod 3 of their position (x, y) (check index 6x + y); the script asserts
that all 24 checks of a class share reset step, CNOT order (term labels A1 A2 A3 B1 B2 B3, A = x^3 + y + y^2,
B = y^3 + x + x^2), CNOT steps and measurement step, and prints one line per class.

    python code/class_table.py A      (B, C, fig12, fig12_retiming_k)
"""
import sys

from common_cli import circuit

TERMS = {"A1": (3, 0), "A2": (0, 1), "A3": (0, 2), "B1": (0, 3), "B2": (1, 0), "B3": (2, 0)}


def label(typ, i, q):
    x, y = divmod(i, 6)
    for lab, (a, b) in TERMS.items():
        left = lab[0] == "A" if typ == "X" else lab[0] == "B"
        s = 1 if typ == "X" else -1
        qq = ((x + s * a) % 12) * 6 + (y + s * b) % 6 + (0 if left else 72)
        if qq == q:
            return lab
    raise ValueError((typ, i, q))


name = sys.argv[1] if len(sys.argv) > 1 else "A"
spec = circuit(name)
P = spec.period
print(f"circuit {name}, period {P}")
print("class  reset  CNOT order        CNOT steps              meas.")
for typ, checks in (("X", spec.x_checks), ("Z", spec.z_checks)):
    for col in range(3):
        rows = set()
        for i, c in enumerate(checks):
            if (i // 6 + i % 6) % 3 != col:
                continue
            dm, offs = c.offsets(P)
            order = "".join(label(typ, i, q) for _, q in offs)
            steps = tuple((c.prep + o) % P for o, _ in offs)
            rows.add((c.prep, order, steps, c.meas))
        assert len(rows) == 1, f"class {typ}{col} is not uniform"
        prep, order, steps, meas = rows.pop()
        print(f"{typ}{col:<5d} {prep:<6d} {order:<17s} {', '.join(map(str, steps)):<23s} {meas}")
