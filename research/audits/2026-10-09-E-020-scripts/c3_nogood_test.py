"""Audit E-020 c3: property tests of cegar.py's nogood machinery at period P (default 11).

A. model: cegar.bellman_ford(cons) vs the E-018 audit's independent a3_model.lifts (kind X logicals), random option
   schedules (legality irrelevant for the model).
B. nogood validity: pi from schedule A; on schedule B: if no constraint has wt_B < pi_u - pi_w then S lifts in B
   (a3 model); and the literal's difference condition (as encoded) <=> wt_B < K.
C. CNF encoding of Lits.diff/tlit: fresh solver with only exactly-one per check; fix schedule B by assumptions;
   assumption l satisfiable  <=>  the condition holds on B.
D. translation images: for g in the 24-group, cons(g S) == g(cons(S)) as multisets of (node, node, kind, positions),
   and lifting set of g.A == g(lifting set of A).
"""
import random, sys, collections
sys.path.insert(0, "research/audits/2026-10-08-E-018-scripts")
from pysat.solvers import Cadical153
from pysat.card import CardEnc, EncType
from pysat.formula import IDPool
from search.experiments.e020.cegar import prep_logicals, bellman_ford, Lits, weight
from search.experiments.e020.plegal import options, checks
from search.experiments.e018.common import ext, tr
import a3_model

P = int(sys.argv[1]) if len(sys.argv) > 1 else 11
NS = int(sys.argv[2]) if len(sys.argv) > 2 else 30
rng = random.Random(7)
O = options(P)
C = checks()
L, skipped = prep_logicals("XZ", "single")
print("modelled", len(L), "skipped", skipped)
xo = [c[2] for c in C[:72]]; zo = [c[2] for c in C[72:]]


def times(sv):
    return {(ci, p): t for ci, k in enumerate(sv) for p, t in enumerate(O[k])}


def a3sched(sv):
    sch = {}
    for ci, k in enumerate(sv):
        o = O[k]; s = o[0] - 1
        sch[("X", ci) if ci < 72 else ("Z", ci - 72)] = (s, [t - s for t in o])
    return sch


# map cegar kind-X logicals to a3 tuples
A3 = {}
for f, h, r in a3_model.single_hook_logicals("X"):
    A3[(frozenset(f), frozenset(r))] = (f, h, r)
def key_of(cons):
    free, res = set(), set()
    for u, w, kd, ((c1, p1), (c2, p2)) in cons:
        if kd == "free":
            free.add(zo[c1 - 72][p1])
        else:
            res.add(zo[c2 - 72][p2])
    return frozenset(free), frozenset(res)
LX = [(l, A3[key_of(l[3])]) for l in L if l[0] == "X" and l[2] == "d10 r21"]
print("kind-X modelled single hooks matched to a3:", len(LX))

# schedules: random, and 'near-Fig12-like' (shifted copies) to get blocked cases
def rand_sched():
    return [rng.randrange(len(O)) for _ in range(144)]
cnt = collections.Counter()
scheds = [rand_sched() for _ in range(NS)]
for sv in scheds:
    T = times(sv); sch = a3sched(sv)
    for l, a in LX:
        m1 = bellman_ford(l[3], T, P) is not None
        m2 = a3_model.lifts(sch, P, a)
        cnt["A_agree" if m1 == m2 else "A_DISAGREE"] += 1
        cnt["A_lift" if m1 else "A_block"] += 1
print(dict(cnt))

# B
for it in range(NS):
    A, B = scheds[it], scheds[(it + 1) % NS]
    TA, TB, schB = times(A), times(B), a3sched(B)
    for l, a in LX[:200]:
        pi = bellman_ford(l[3], TA, P)
        if pi is None:
            continue
        anylit = False
        for u, w, kd, (p1, p2) in l[3]:
            K = pi[u] - pi[w]
            wt = weight(kd, (p1, p2), TB, P)
            d = TB[p1] - TB[p2]
            cond = d <= (K - 1) * P - 1 if kd in ("free", "hook+") else d >= -K * P
            cnt["B_litcond_ok" if cond == (wt < K) else "B_LITCOND_BAD"] += 1
            anylit |= wt < K
        if not anylit:
            cnt["B_allfalse_lifts" if a3_model.lifts(schB, P, a) else "B_ALLFALSE_BLOCKED(!)"] += 1
        else:
            cnt["B_some_true"] += 1
print(dict(cnt))

# C
pool = IDPool()
x = [[pool.id(("x", ci, k)) for k in range(len(O))] for ci in range(144)]
S = Cadical153()
for ci in range(144):
    for cl in CardEnc.equals(lits=x[ci], bound=1, vpool=pool, encoding=EncType.seqcounter).clauses:
        S.add_clause(cl)
lits = Lits(P, C, O, x, pool, S)
tests = []
for _ in range(300):
    p1 = (rng.randrange(144), rng.randrange(6)); p2 = (rng.randrange(144), rng.randrange(6))
    if p1[0] == p2[0]:
        continue
    op = rng.choice(["le", "ge"]); M = rng.randrange(-3 * P, 3 * P)
    tests.append((p1, p2, op, M, lits.diff(p1, p2, op, M)))
for sv in scheds[:5]:
    T = times(sv)
    asm = [x[ci][k] for ci, k in enumerate(sv)]
    for p1, p2, op, M, l in tests:
        d = T[p1] - T[p2]
        cond = d <= M if op == "le" else d >= M
        sat = S.solve(assumptions=asm + [l])
        cnt["C_ok" if sat == cond else "C_BAD"] += 1
print(dict(cnt))

# D
E = ext("X")
group = E["group"]
byS = {tuple(sorted(l[1])): l for l in L if l[0] == "X"}
def canon(cons):
    return collections.Counter((u, w, kd, dt) for u, w, kd, dt in cons)
for g, perm in zip(group, E["perms"]):
    pm, _ = tr(*g)
    gm = [int(pm[i]) for i in range(72)] + [72 + int(pm[j]) for j in range(72)]
    for Sx, l in list(byS.items())[:60]:
        gS = tuple(sorted(int(perm[j]) for j in Sx))
        if gS not in byS:
            cnt["D_IMAGE_MISSING"] += 1; continue
        mapped = canon([((u[0], gm[u[1]]), (w[0], gm[w[1]]), kd, ((gm[a[0]], a[1]), (gm[b[0]], b[1])))
                        for u, w, kd, (a, b) in l[3]])
        cnt["D_cons_eq" if mapped == canon(byS[gS][3]) else "D_CONS_NEQ"] += 1
    A = scheds[0]
    gA = [None] * 144
    for ci in range(144):
        gA[gm[ci]] = A[ci]
    TA, TgA = times(A), times(gA)
    for Sx, l in list(byS.items())[:60]:
        gS = tuple(sorted(int(perm[j]) for j in Sx))
        a1 = bellman_ford(l[3], TA, P) is not None
        a2 = bellman_ford(byS[gS][3], TgA, P) is not None
        cnt["D_lift_eq" if a1 == a2 else "D_LIFT_NEQ"] += 1
print(dict(cnt))
