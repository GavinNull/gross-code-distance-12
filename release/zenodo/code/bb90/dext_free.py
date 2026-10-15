"""Every per-check CNOT-order assignment of [[90,8,10]] has d_ext <= 8 on the X-check side: generator of the CNF.

This encoding is independent of the rest of the package (own construction of the code, of its logical operators and
of the clauses; only numpy and python-sat are used).

Statement.  For every choice of a CNOT order for each of the 45 X checks (the circuit need not be interleaved,
pipelined or translation invariant), the extended code of the X-check hooks (Z-basis memory: H = HZ, L = LZ) contains
a logical of weight <= 8.  Hence d_ext <= 8 = d - 2 for every single-ancilla circuit of this code.

Construction.
 1. Types.  The extended columns contributed by one check depend only on its "type" = the set of hook supports
    {o[:2], o[:3], o[4:]} (each taken modulo the complement within the check support); the 720 orders give 90 types.
    A type is "bad" if the data columns plus the three hook columns of check 0 alone already contain an extended
    logical of weight <= 8 (decided by SAT); bad types can be excluded (such a logical stays an extended logical
    when more columns are added).  Result: 54 good, 36 bad.
 2. The 558 weight-10 X-type logicals of the code, enumerated by SAT (the code distance is 10).
 3. Clauses.  For a weight-10 logical l and a realisable hook support U inside l (|U| = 3 or 4: reduction >= 2), or
    two disjoint pairs inside l, the hook columns together with the remaining data qubits of l form an extended
    logical of weight <= 8; so these hook columns cannot all be realised.  Each such combination is re-verified by
    building the extended logical explicitly (distinct column keys, zero syndrome, odd logical, at most 8 columns).
 4. CNF.  y[a,t]: check a uses good type t (at-least-one per check, no at-most-one: a stronger statement);
    r[a,U]: hook column (a, U) is realised; y[a,t] -> r[a,U] for every U realised by t; one clause (not r ...) per
    conflict of step 3.  r occurs only negatively in the conflict clauses, so no spurious UNSAT is possible.
Unsatisfiability of this CNF (certificates/bb90_dext_free/X_side.cnf.gz, DRAT proof checked by drat-trim, LRAT core by
cake_lpr; see certificates/proofs/bb90_dext_free.json) proves the statement.

    python code/bb90/dext_free.py OUT.cnf [--compare certificates/bb90_dext_free/X_side.cnf.gz]
Prints the counts (types 90, good 54, bad 36, logicals 558, clauses, verified combinations) and the sha256 of the
CNF; with --compare: PASS if it is byte-identical to the shipped one.  About 7 CPU minutes.
"""
import gzip
import hashlib
import itertools
import sys
import time

import numpy as np
from pysat.card import CardEnc, EncType
from pysat.solvers import Solver

L_, M_ = 15, 3
N2 = L_ * M_
N = 2 * N2


# ------------------------------------------------------------------ the code, from scratch

def shift(n, k):
    S = np.zeros((n, n), np.uint8)
    for i in range(n):
        S[i, (i + k) % n] = 1
    return S


def mono(a, b):
    return np.kron(shift(L_, a), shift(M_, b)) % 2


def bb_code():
    A = (mono(9, 0) + mono(0, 1) + mono(0, 2)) % 2
    B = (mono(0, 0) + mono(2, 0) + mono(7, 0)) % 2
    HX = np.concatenate([A, B], 1) % 2
    HZ = np.concatenate([B.T, A.T], 1) % 2
    assert not ((HX.astype(int) @ HZ.T.astype(int)) % 2).any()
    return HX.astype(np.uint8), HZ.astype(np.uint8)


def rref(M):
    M = (np.array(M, np.uint8) % 2).copy()
    r, piv = 0, []
    for c in range(M.shape[1]):
        p = next((i for i in range(r, M.shape[0]) if M[i, c]), None)
        if p is None:
            continue
        M[[r, p]] = M[[p, r]]
        for i in range(M.shape[0]):
            if i != r and M[i, c]:
                M[i] ^= M[r]
        piv.append(c)
        r += 1
        if r == M.shape[0]:
            break
    return M[:r], piv


def rank(M):
    return len(rref(M)[1])


def kernel(M):
    R, piv = rref(M)
    n = M.shape[1]
    out = []
    for f in [c for c in range(n) if c not in piv]:
        v = np.zeros(n, np.uint8)
        v[f] = 1
        for i, c in enumerate(piv):
            v[c] = R[i, f]
        out.append(v)
    return np.array(out, np.uint8)


def logicals(Hker, Hrow):
    """basis of ker(Hker) modulo rowspace(Hrow)."""
    base = list(Hrow)
    r0 = rank(np.array(base))
    out = []
    for v in kernel(Hker):
        if rank(np.array(base + [v])) > r0:
            base.append(v)
            r0 += 1
            out.append(v)
    return np.array(out, np.uint8)


def main(argv):
    out_path = argv[0]
    compare = argv[argv.index("--compare") + 1] if "--compare" in argv else None
    HX, HZ = bb_code()
    LZ = logicals(HX, HZ)
    H, Lg = HZ, LZ                   # X-check hooks are X errors, seen by HZ
    assert N - rank(HX) - rank(HZ) == 8 and len(LZ) == 8

    def sup(a_idx):                  # X check a = 3x + y: data qubits of the labels A1 A2 A3 B1 B2 B3
        a, b = divmod(a_idx, M_)
        return [((a + 9) % L_) * M_ + b, a * M_ + (b + 1) % M_, a * M_ + (b + 2) % M_, N2 + a * M_ + b,
                N2 + ((a + 2) % L_) * M_ + b, N2 + ((a + 7) % L_) * M_ + b]

    for i in range(N2):
        assert sorted(sup(i)) == sorted(np.nonzero(HX[i])[0].tolist())

    def canon(U):
        U = frozenset(U)
        C = frozenset(range(6)) - U
        return min(tuple(sorted(U)), tuple(sorted(C)), key=lambda x: (len(x), x))

    def realised(o):
        return {canon(o[:2]), canon(o[:3]), canon(o[4:])}

    types = {}
    for o in itertools.permutations(range(6)):
        types.setdefault(frozenset(realised(o)), o)
    assert len(types) == 90

    def key(qs):
        v = np.zeros(N, np.int64)
        v[list(qs)] = 1
        return ((H @ v) % 2).tobytes() + ((Lg @ v) % 2).tobytes()

    def xor_chain(vs, state):
        cur = vs[0]
        for v in vs[1:]:
            state["top"] += 1
            y = state["top"]
            state["cls"] += [[-cur, -v, -y], [cur, v, -y], [cur, -v, y], [-cur, v, y]]
            cur = y
        return cur

    def min_logical_le(cols_sups, W):
        """SAT: a set of the given columns with zero syndrome, odd logical part and at most W columns."""
        keys = {}
        for s in cols_sups:
            k = key(s)
            if k != key([]):
                keys.setdefault(k, s)
        cl = list(keys.values())
        n = len(cl)
        st = {"top": n, "cls": []}
        vecs = []
        for s in cl:
            v = np.zeros(N, np.int64)
            v[list(s)] = 1
            vecs.append(v)
        V = np.array(vecs).T
        HS, LS = (H @ V) % 2, (Lg @ V) % 2
        for r in HS:
            vs = [int(j) + 1 for j in np.nonzero(r)[0]]
            if vs:
                st["cls"].append([-xor_chain(vs, st)])
        st["cls"].append([xor_chain([int(j) + 1 for j in np.nonzero(r)[0]], st) for r in LS if r.any()])
        am = CardEnc.atmost(list(range(1, n + 1)), bound=W, top_id=st["top"], encoding=EncType.totalizer)
        with Solver(name="cd15", bootstrap_with=st["cls"] + am.clauses) as s:
            return s.solve()

    t0 = time.time()
    good, bad = [], []
    for T in types:
        S = sup(0)
        cols = [(q,) for q in range(N)] + [tuple(S[k] for k in U) for U in T]
        (bad if min_logical_le(cols, 8) else good).append(T)
    print(f"types 90: good {len(good)}, bad {len(bad)} ({time.time() - t0:.0f} s)", flush=True)

    def enum_logicals(w):
        st = {"top": N, "cls": []}
        for r in H:
            st["cls"].append([-xor_chain([int(j) + 1 for j in np.nonzero(r)[0]], st)])
        st["cls"].append([xor_chain([int(j) + 1 for j in np.nonzero(r)[0]], st) for r in Lg])
        lits = list(range(1, N + 1))
        am = CardEnc.atmost(lits, bound=w, top_id=st["top"], encoding=EncType.totalizer)
        al = CardEnc.atleast(lits, bound=w, top_id=am.nv, encoding=EncType.totalizer)
        out = []
        with Solver(name="cd15", bootstrap_with=st["cls"] + am.clauses + al.clauses) as s:
            while s.solve():
                m = s.get_model()
                S = tuple(j for j in range(N) if m[j] > 0)
                out.append(S)
                s.add_clause([-(j + 1) for j in S])
        return out

    t0 = time.time()
    L10 = enum_logicals(10)
    print(f"weight-10 X-type logicals: {len(L10)} ({time.time() - t0:.0f} s)", flush=True)

    supsets = [sup(a) for a in range(N2)]
    clauses = set()
    nver = 0
    for lg in L10:
        ls = set(lg)
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
        combos = [[it] for it in items if it[3] >= 2] + \
                 [[i1, i2] for i1, i2 in itertools.combinations(pairs, 2) if not (i1[2] & i2[2])]
        for combo in combos:
            used = set().union(*[c[2] for c in combo])
            colsq = [tuple(sorted(c[2])) for c in combo] + [(q,) for q in sorted(ls - used)]
            ks = [key(c) for c in colsq]
            assert len(set(ks)) == len(ks) <= 8
            v = np.zeros(N, np.int64)
            for c in colsq:
                v[list(c)] ^= 1
            assert not ((H @ v) % 2).any() and ((Lg @ v) % 2).any()
            nver += 1
    print(f"conflict clauses {len(clauses)}, verified combinations {nver}", flush=True)

    var = {}

    def v(x):
        if x not in var:
            var[x] = len(var) + 1
        return var[x]

    cnf = []
    for a in range(N2):
        cnf.append([v(("y", a, T)) for T in good])
        for T in good:
            for U in T:
                cnf.append([-v(("y", a, T)), v(("r", a, U))])
    for c in clauses:
        cnf.append([-v(("r", a, U)) for a, U in c])
    text = f"p cnf {len(var)} {len(cnf)}\n" + "".join(" ".join(map(str, c)) + " 0\n" for c in cnf)
    open(out_path, "w").write(text)
    sha = hashlib.sha256(text.encode()).hexdigest()
    print(f"wrote {out_path}: {len(var)} variables, {len(cnf)} clauses, sha256 {sha}", flush=True)
    if compare:
        ref = gzip.open(compare, "rb").read() if compare.endswith(".gz") else open(compare, "rb").read()
        same = ref == text.encode()
        print(("PASS" if same else "FAIL") + f"  bb90 d_ext <= 8 CNF regenerated: types good/bad {len(good)}/"
              f"{len(bad)}, {len(L10)} weight-10 logicals, {nver} verified conflict combinations, {len(cnf)} clauses; "
              f"{'byte-identical to' if same else 'DIFFERS from'} {compare}")
        return 0 if same else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
