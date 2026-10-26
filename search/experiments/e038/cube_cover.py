"""E-038: check that the per-cube DRAT certificates cover N(S): the cube literal pairs are exactly
{(tau(X0,A1) = v0, tau(X0,A2) = v1) : v0 != v1 in 1..S} (as eq-literals of the same Enc numbering as final CNF), and
in the CNF tau(X0,A1), tau(X0,A2) take exactly one value each and differ (so every model satisfies one cube).
usage: uv run python -m search.experiments.e038.cube_cover N 7 results/E-038-bb18-d4/final_N7"""
import glob
import json
import sys

from search.experiments.e038.enc import Enc

cls, S, prefix = sys.argv[1], int(sys.argv[2]), sys.argv[3]
E = Enc("bb18", cls, S)
k0 = E.ks[0]
want = set()
for v0 in range(1, S + 1):
    for v1 in range(1, S + 1):
        if v0 != v1:
            want.add((E.tau[(k0, 0)].eq(v0), E.tau[(k0, 1)].eq(v1)))
got = set()
for f in glob.glob(prefix + "_cube_drat_d2_*.jsonl"):
    for l in open(f):
        r = json.loads(l)
        assert r["verified"] and r["cadical"] == "s UNSATISFIABLE"
        got.add(tuple(r["lits"]))
# the encoding prefix of the final CNF must be identical to this Enc (same variable numbering)
head = open(prefix + ".cnf").read().split("\n")[1:1 + len(E.cl)]
same = all(h == " ".join(map(str, c)) + " 0" for h, c in zip(head, E.cl))
print(json.dumps({"cubes_needed": len(want), "cubes_verified": len(got), "covered": want <= got,
                  "legality_prefix_identical": same}))
