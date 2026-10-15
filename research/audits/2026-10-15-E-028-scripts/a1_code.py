"""A1: code identity, n, k, d (exact, SAT), compare with evaluator matrices."""
import sys, json, itertools
sys.path.insert(0, "research/audits/2026-10-15-E-028-scripts")
import numpy as np
from alib import *
from pysat.formula import CNF
from pysat.card import CardEnc, EncType
from pysat.solvers import Solver

HX, HZ, LX, LZ = code_with_logicals()
k = N - rank(HX) - rank(HZ)
print("n", N, "k", k, "rankHX", rank(HX), "rankHZ", rank(HZ), "LX", LX.shape, "LZ", LZ.shape)
# evaluator comparison
from evaluators.tasks import build_code, get_task
c, _ = build_code(get_task("bb90-dcirc"), None)
print("evaluator HX==mine", np.array_equal(np.asarray(c.HX) % 2, HX), "HZ==mine", np.array_equal(np.asarray(c.HZ) % 2, HZ))
# logical spans equal mod stabilisers
for nm, Lm, Le, S in (("LX", LX, np.asarray(c.LX) % 2, HX), ("LZ", LZ, np.asarray(c.LZ) % 2, HZ)):
    print(nm, "same span mod stab:", rank(np.vstack([S, Lm])) == rank(np.vstack([S, Lm, Le])) == rank(np.vstack([S, Le])))

def xor_clauses(vs, rhs, top):
    """Tseitin chain: xor(vs) == rhs. returns clauses, new top."""
    cls = []
    cur = vs[0]
    for v in vs[1:]:
        top += 1; y = top
        cls += [[-cur, -v, -y], [cur, v, -y], [cur, -v, y], [-cur, v, y]]
        cur = y
    cls.append([cur] if rhs else [-cur])
    return cls, top, cur

def xor_def(vs, top):
    cls = []
    cur = vs[0]
    for v in vs[1:]:
        top += 1; y = top
        cls += [[-cur, -v, -y], [cur, v, -y], [cur, -v, y], [-cur, v, y]]
        cur = y
    return cls, top, cur

def min_weight(H, Lg, W):
    """exists x != logical-trivial, H x = 0, some Lg row odd, |x| <= W ?"""
    n = H.shape[1]
    top = n
    cls = []
    for row in H:
        c, top, _ = xor_clauses([int(j) + 1 for j in np.nonzero(row)[0]], 0, top); cls += c
    outs = []
    for row in Lg:
        c, top, o = xor_def([int(j) + 1 for j in np.nonzero(row)[0]], top); cls += c; outs.append(o)
    cls.append(outs)
    card = CardEnc.atmost(list(range(1, n + 1)), bound=W, top_id=top, encoding=EncType.seqcounter)
    cls += card.clauses
    with Solver(name="cd15", bootstrap_with=cls) as s:
        r = s.solve()
        if r:
            m = s.get_model()
            return [j for j in range(n) if m[j] > 0]
        return None

for nm, H, Lg in (("X-type logical (ker HZ, odd vs LZ)", HZ, LZ), ("Z-type logical (ker HX, odd vs LX)", HX, LX)):
    w9 = min_weight(H, Lg, 9)
    w10 = min_weight(H, Lg, 10)
    print(nm, "weight<=9:", w9, " weight<=10 witness size:", None if w10 is None else len(w10))
