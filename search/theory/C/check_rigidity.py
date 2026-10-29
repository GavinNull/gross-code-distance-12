"""Question C: numerical check of Lemma 5 (W8 hook rigidity) and Proposition 6 (simultaneous-logical criterion).
For random legal W8 schedules (legality + static HH clauses, i.e. no weight-2 bulk witness) and every spreader k
(both memory bases):
  back hook  H(k, last two)        vs located errors (a, beta), (b, beta), beta = pi_k + 6.5  (a = 5th, b = 6th qubit)
  front hook H(k, last four)       vs located errors (q1, beta'), (q2, beta'), beta' = pi_k + 0.5
detector masks must coincide iff no reader acts on a at layer pi_k+6 (resp. on q2 at layer pi_k+1).
Prop 6: if they coincide and L (weight-4 logical containing the pair) is not split at beta by any reader, then
H + (c, beta) + (d, beta) is an undetectable logical of weight 3 -> checked: zero detector mask and observable != 0.
usage: uv run python -m search.theory.C.check_rigidity results/theory-C/W8.pkl n seed"""
import itertools, random, sys
import numpy as np
from pysat.solvers import Cadical153
from search.theory.C.project import load
from search.experiments.e038.enc import Enc
from search.experiments.e038.model import Bulk, legal
from search.experiments.e036_audit.core import support, observables, checks

D = load(sys.argv[1]); n, seed = int(sys.argv[2]), int(sys.argv[3]); rng = random.Random(seed)
E = Enc("bb18", "W", 8)
S = Cadical153(bootstrap_with=D["base"] + [c for tag, t, c in D["tagged"] if t == "HH"])
ks = checks("bb18")

def L4(b):
    rd = [k for k in ks if k[0] == b]; obs = observables("bb18", b); out = []
    for T in itertools.combinations(range(18), 4):
        if all(len(set(T) & set(support(k))) % 2 == 0 for k in rd):
            v = np.zeros(18, int); v[list(T)] = 1
            if (obs @ v % 2).any(): out.append(frozenset(T))
    return out
LOG = {b: L4(b) for b in ("Z", "X")}
stats = dict(eq_pred_ok=0, eq_pred_bad=0, prop6_applied=0, prop6_ok=0, prop6_bad=0)

def located(bk, q, t2, r=1):
    """detector mask of an error on q at doubled time t2 (instance r frame)."""
    d = 0
    for f in bk.rev[q]:
        d ^= bk.bit(f[0], bk.j0(f, t2 + 2 * r * bk.s.P))
    return d

for it in range(n):
    ass = [l for k in E.ks[1:] for l in [E.pi[k].eq(rng.randrange(8))] if l not in (True, False)]
    rng.shuffle(ass); m = len(ass)
    while m and not S.solve(assumptions=ass[:m]): m -= 1
    if not m: S.solve()
    s = E.decode(S.get_model()); assert legal(s)[0]
    for b in ("Z", "X"):
        bk = Bulk(s, b, 6)
        mech = {(t[1], t[2], t[3]): (d, o) for d, o, t in bk.mechs() if t[0] == "H"}
        for k in bk.spreaders:
            order = sorted(range(6), key=lambda a: s.tau[(k, a)]); sp = support(k); pk = s.pi[k]
            reads = {(q, s.tau[f] % 8) for q in range(18) for f in bk.rev[q]}
            for kind in ("back", "front"):
                if kind == "back":
                    U = frozenset(order[4:]); pair = (sp[order[4]], sp[order[5]]); beta2 = 2 * (pk + 6) + 1
                    pred = (pair[0], (pk + 6) % 8) not in reads
                else:
                    U = frozenset(order[2:]); pair = (sp[order[0]], sp[order[1]]); beta2 = 2 * pk + 1
                    pred = (pair[1], (pk + 1) % 8) not in reads
                dH, oH = mech[(k, U, 1)]
                dP = located(bk, pair[0], beta2) ^ located(bk, pair[1], beta2)
                same = dH == dP
                stats["eq_pred_ok" if same == pred else "eq_pred_bad"] += 1
                if not same:
                    continue
                for Lg in LOG[b]:
                    if not set(pair) <= Lg: continue
                    c, dd = sorted(Lg - set(pair))
                    tot = dH ^ located(bk, c, beta2) ^ located(bk, dd, beta2)
                    split = False
                    for g in bk.readers:
                        I = [q for q in support(g) if q in Lg]
                        if len(I) == 2:
                            js = {bk.j0((g, support(g).index(q)), beta2 + 16) for q in I}
                            split |= len(js) > 1
                    if not split:
                        stats["prop6_applied"] += 1
                        obs = oH ^ bk.obsq[c] ^ bk.obsq[dd]
                        stats["prop6_ok" if (tot == 0 and obs) else "prop6_bad"] += 1
    print(it, stats, flush=True)
