"""Audit E-020 b4: control for p8search: count solutions of weakened P=8 instances (all-different of the listed data
qubits dropped) with my own pysat encoding (direct pairwise clauses on start literals), check 0 fixed to 4.
    uv run python b4_satcount.py "0,1,2" """
import sys
from pysat.solvers import Cadical153
skip = {int(v) for v in sys.argv[1].split(",")} if len(sys.argv) > 1 and sys.argv[1] else set()
inst = [list(map(int, l.split())) for l in open("results/E-020-audit/p8_inst.txt")]
v = lambda c, s: 8 * c + s + 1
cl = []
for c in range(144):
    cl.append([v(c, s) for s in range(8)])
    for a in range(8):
        for b in range(a + 1, 8):
            cl.append([-v(c, a), -v(c, b)])
touch = {}
for row in inst:
    c = row[0]
    for j in range(6):
        touch.setdefault(row[2 + 2 * j], []).append((c, row[3 + 2 * j]))
for q, lst in touch.items():
    if q in skip:
        continue
    for i in range(6):
        for j in range(i + 1, 6):
            (c, k), (d, l) = lst[i], lst[j]
            for sc in range(8):
                sd = (sc + k - l) % 8          # s_c + k == s_d + l
                cl.append([-v(c, sc), -v(d, sd)])
cl.append([v(0, 4)])
n = 0
with Cadical153(bootstrap_with=cl) as S:
    while S.solve():
        m = S.get_model(); n += 1
        S.add_clause([-l for l in m[:144 * 8] if l > 0])
print("SKIP", sorted(skip), "solutions", n)
