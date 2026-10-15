"""A6: independent re-derivation of "every per-check CNOT order assignment has d_ext <= 8" (kind X = X-check hooks,
Z-basis memory), different generator and encoding from search/experiments/e028/eager*.py.

1. single-check types: for each of the 90 types (orbit of 720 orders under s12, s56, reversal) compute by SAT whether
   the extended code with data columns + the 3 hook columns of check 0 has a logical of weight <= 8 ("bad" types).
2. all weight-10 X-type logicals by SAT model enumeration.
3. clauses: for each weight-10 logical l and each realisable hook support U inside l (pair, triple, 4-set;
   column = U mod complement), or two disjoint pairs inside l, the hooks + remaining data qubits are an extended
   logical of weight <= 8, so these columns cannot all be realised.  Every clause is re-verified by building the
   extended logical explicitly (distinct column keys, zero syndrome, odd logical, weight <= 8).
4. CNF: y[a,t] (check a uses type t; only "good" types; at-least-one per check, no at-most-one = stronger),
   r[a,U] (column (a,U) realised): y[a,t] -> r[a,U] for U realised by t; clause (not r1 or not r2).
   Writes DIMACS for CaDiCaL (+ DRAT) and also solves with CP-SAT.
"""
import sys, itertools, json, time, pickle
sys.path.insert(0, "research/audits/2026-10-15-E-028-scripts")
import numpy as np
from alib import *
from pysat.card import CardEnc, EncType
from pysat.solvers import Solver

kind = sys.argv[1] if len(sys.argv) > 1 else "X"
HX, HZ, LX, LZ = code_with_logicals()
H, Lg = (HZ, LZ) if kind == "X" else (HX, LX)      # X-check hooks are X errors, seen by HZ
LAB = ["A1", "A2", "A3", "B1", "B2", "B3"]

def sup(a_idx):
    a, b = divmod(a_idx, M_)
    if kind == "X":
        return [((a+9)%L_)*M_+b, a*M_+(b+1)%M_, a*M_+(b+2)%M_, N2+a*M_+b, N2+((a+2)%L_)*M_+b, N2+((a+7)%L_)*M_+b]
    return [N2+((a-9)%L_)*M_+b, N2+a*M_+(b-1)%M_, N2+a*M_+(b-2)%M_, a*M_+b, ((a-2)%L_)*M_+b, ((a-7)%L_)*M_+b]

Hc = HX if kind == "X" else HZ
for i in range(N2):
    assert sorted(sup(i)) == sorted(np.nonzero(Hc[i])[0].tolist())

def canon(U):
    U = frozenset(U)
    C = frozenset(range(6)) - U
    return min(tuple(sorted(U)), tuple(sorted(C)), key=lambda x: (len(x), x))

def realised(o):
    return {canon(o[:2]), canon(o[:3]), canon(o[4:])}

types = {}
for o in itertools.permutations(range(6)):
    types.setdefault(frozenset(realised(o)), o)
print("types", len(types))
assert len(types) == 90

def key(qs):
    v = np.zeros(N, np.int64); v[list(qs)] = 1
    return ((H @ v) % 2).tobytes() + ((Lg @ v) % 2).tobytes()

def min_logical_le(cols_sups, W):
    """cols_sups: list of qubit tuples (columns). SAT: subset with zero syndrome, odd logical, size <= W."""
    keys = {}
    for s in cols_sups:
        k = key(s)
        if k != key([]):
            keys.setdefault(k, s)
    cl = list(keys.values())
    n = len(cl)
    top = n; cls = []
    def chain(vs):
        nonlocal top, cls
        cur = vs[0]
        for v in vs[1:]:
            top += 1; y = top
            cls += [[-cur, -v, -y], [cur, v, -y], [cur, -v, y], [-cur, v, y]]
            cur = y
        return cur
    vecs = []
    for s in cl:
        v = np.zeros(N, np.int64); v[list(s)] = 1; vecs.append(v)
    V = np.array(vecs).T
    HS = (H @ V) % 2; LS = (Lg @ V) % 2
    for r in HS:
        vs = [int(j)+1 for j in np.nonzero(r)[0]]
        if vs: cls.append([-chain(vs)])
    cls.append([chain([int(j)+1 for j in np.nonzero(r)[0]]) for r in LS if r.any()])
    am = CardEnc.atmost(list(range(1, n+1)), bound=W, top_id=top, encoding=EncType.totalizer)
    with Solver(name="cd15", bootstrap_with=cls + am.clauses) as s:
        return s.solve()

t0 = time.time()
good, bad = [], []
for T, o in types.items():
    S = sup(0)
    cols = [(q,) for q in range(N)] + [tuple(S[k] for k in U) for U in T]
    (bad if min_logical_le(cols, 8) else good).append(T)
print("single-check types: good", len(good), "bad", len(bad), round(time.time()-t0, 1), "s", flush=True)

# weight-10 logicals
def enum_logicals(w):
    n = N; top = n; cls = []
    def chain(vs):
        nonlocal top, cls
        cur = vs[0]
        for v in vs[1:]:
            top += 1; y = top
            cls += [[-cur, -v, -y], [cur, v, -y], [cur, -v, y], [-cur, v, y]]
            cur = y
        return cur
    for r in H:
        cls.append([-chain([int(j)+1 for j in np.nonzero(r)[0]])])
    cls.append([chain([int(j)+1 for j in np.nonzero(r)[0]]) for r in Lg])
    lits = list(range(1, n+1))
    am = CardEnc.atmost(lits, bound=w, top_id=top, encoding=EncType.totalizer); cls += am.clauses
    al = CardEnc.atleast(lits, bound=w, top_id=am.nv, encoding=EncType.totalizer); cls += al.clauses
    out = []
    with Solver(name="cd15", bootstrap_with=cls) as s:
        while s.solve():
            m = s.get_model()
            S = tuple(j for j in range(n) if m[j] > 0)
            out.append(S); s.add_clause([-(j+1) for j in S])
    return out

t0 = time.time()
L10 = enum_logicals(10)
print("weight-10 logicals:", len(L10), round(time.time()-t0, 1), "s", flush=True)

# clauses
supsets = [sup(a) for a in range(N2)]
items_cache = {}
clauses = set()        # frozenset of (a, Ucanon)
nver = 0
for l in L10:
    ls = set(l)
    items = []
    for a in range(N2):
        S = supsets[a]
        inl = [k for k in range(6) if S[k] in ls]
        for size in (2, 3, 4):
            for U in itertools.combinations(inl, size):
                items.append((a, canon(U), frozenset(S[k] for k in U), size - 1))
    for it in items:
        if it[3] >= 2:
            clauses.add(frozenset([(it[0], it[1])]))
    pairs = [it for it in items if it[3] == 1]
    for i1, i2 in itertools.combinations(pairs, 2):
        if i1[2] & i2[2]:
            continue
        clauses.add(frozenset([(i1[0], i1[1]), (i2[0], i2[1])]))
    # verification of every combination used (explicit extended logical)
    for combo in [[it] for it in items if it[3] >= 2] + [[i1, i2] for i1, i2 in itertools.combinations(pairs, 2) if not (i1[2] & i2[2])]:
        used = set().union(*[c[2] for c in combo])
        colsq = [tuple(sorted(c[2])) for c in combo] + [(q,) for q in sorted(ls - used)]
        ks = [key(c) for c in colsq]
        assert len(set(ks)) == len(ks) <= 8
        v = np.zeros(N, np.int64)
        for c in colsq: v[list(c)] ^= 1
        assert not ((H @ v) % 2).any() and ((Lg @ v) % 2).any()
        nver += 1
print("clauses", len(clauses), "verified combos", nver, flush=True)
# drop clauses containing a column no good type realises (cannot fire) -- keep all, harmless
goodreal = set().union(*[set(T) for T in good])
# CNF
var = {}
def v(x):
    if x not in var: var[x] = len(var) + 1
    return var[x]
cnf = []
for a in range(N2):
    cnf.append([v(("y", a, T)) for T in good])
    for T in good:
        for U in T:
            cnf.append([-v(("y", a, T)), v(("r", a, U))])
for c in clauses:
    lits = [-v(("r", a, U)) for a, U in c]
    cnf.append(lits)
fn = f"results/E-028-audit/a6_dext_free_{kind}.cnf"
with open(fn, "w") as f:
    f.write(f"p cnf {len(var)} {len(cnf)}\n")
    for c in cnf: f.write(" ".join(map(str, c)) + " 0\n")
pickle.dump({"var": var, "good": good, "bad": bad, "L10": L10, "clauses": clauses}, open(f"results/E-028-audit/a6_{kind}.pkl", "wb"))
print("wrote", fn, "vars", len(var), "clauses", len(cnf), flush=True)
