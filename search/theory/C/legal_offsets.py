"""Question C: enumerate prep-offset vectors (pi_k)_k admitting a LEGAL W(P) schedule (no distance clauses).
usage: uv run python -m search.theory.C.legal_offsets 8 [maxcount] [timeout_s]"""
import sys, time
from pysat.solvers import Cadical153
from search.experiments.e038.enc import Enc

P = int(sys.argv[1]); cap = int(sys.argv[2]) if len(sys.argv) > 2 else 10**6
tmax = float(sys.argv[3]) if len(sys.argv) > 3 else 300
E = Enc("bb18", "W", P)
lits = {k: {v: E.pi[k].eq(v) for v in range(E.pi[k].lo, E.pi[k].hi + 1)} for k in E.ks}
S = Cadical153(bootstrap_with=E.cl)
t0 = time.time(); n = 0; out = []
while n < cap and time.time() - t0 < tmax and S.solve():
    m = S.get_model(); pos = set(l for l in m if l > 0)
    vec = tuple(E.value(E.pi[k], pos) for k in E.ks)
    out.append(vec); n += 1
    blk = [-lits[k][v] for k, v in zip(E.ks, vec) if lits[k][v] not in (True, False)]
    S.add_clause(blk)
done = time.time() - t0 < tmax and n < cap
print("count", n, "complete" if done else "INCOMPLETE", round(time.time() - t0, 1), "s")
for v in out[:20]:
    print(v)
