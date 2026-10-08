"""Audit E-018 (a3): own implementation of the bulk lifting model for single-hook logicals, used by a3_enum / a4.

Schedule representation (any period P, pipelined allowed): sched[(type, i)] = (s, offs) with offs[k] = offset of the
k-th CNOT in Fig. 12's order of that check, 0 < offs[0] < ... < offs[5] < P-1 (meas at s+offs[5]+1 <= s+P-1).
Absolute time of instance n of check (type,i) on data q: s + offs[pos(q)] + n P.

Z-basis memory, X faults (kind "X": X-check hooks; reading checks = Z checks).
 * data X fault on w at time theta: Z check c (instance-0 read time T_c) flips detector instance
   H_c = min{n : T_c + nP > theta}, i.e. theta in the open interval (T_c + (H_c-1)P, T_c + H_c P).
   3 such intervals (length P, integer endpoints) intersect iff pairwise  =>  H_c - H_d <= floor((T_d - T_c)/P) + 1.
   (1-D Helly.)  A fault right after the latest-left-endpoint read is a legal SD6 location (2q depolarising after
   the CNOT, component X_data x I_anc).
 * hook: X on the ancilla of X check a after its 4th CNOT (instance F) = X on q5 at T_a(q5)+FP and q6 at T_a(q6)+FP;
   H_c = F + floor((T_a(q) - T_c)/P) + 1 for every Z check c reading q in {q5, q6}.
 * undetected  <=>  every Z check c sees its 2 qubits of Q in the same instance (|Q∩c| = 2 for all 18 checks: a1).
Feasible system (no negative cycle) => an 11-fault undetected logical exists in the bulk.
"""
import pickle, sys, collections
sys.path.insert(0, "research/audits/2026-10-08-E-018-scripts")
from a1_common import xo, zo, HX, HZ, LX, LZ
import numpy as np

POS = {("X", i): {q: k for k, q in enumerate(o)} for i, o in enumerate(xo)} | \
      {("Z", j): {q: k for k, q in enumerate(o)} for j, o in enumerate(zo)}
ZREAD = collections.defaultdict(list)   # data q -> Z checks
XREAD = collections.defaultdict(list)
for j, o in enumerate(zo):
    for q in o: ZREAD[q].append(("Z", j))
for i, o in enumerate(xo):
    for q in o: XREAD[q].append(("X", i))


def single_hook_logicals(kind="X"):
    """(free data qubits, hook check, (q5, q6)) for all 10-data + 1-r2 weight-11 logicals of `kind`, derived from the
    experimenter's stored set but re-verified with own matrices (H x = 0, L x != 0)."""
    from search.experiments.e018.common import ext
    E = ext(kind)
    H, L, ords, t = (HZ, LZ, xo, "X") if kind == "X" else (HX, LX, zo, "Z")
    out = []
    for S in pickle.load(open(f"results/E-018-gross-interleaved-12/w11_all_{kind}.pkl", "rb")):
        free, hooks = [], []
        for j in S:
            cs = E["col_sups"][j]
            d = [s for s in cs if len(s) == 1]
            if d: free.append(d[0][0])
            else: hooks.append(cs[0])
        if len(free) != 10 or len(hooks) != 1 or len(hooks[0]) != 2:
            continue
        r = set(hooks[0])
        a = next(i for i, o in enumerate(ords) if set(o[4:]) == r)
        x = np.zeros(144, np.uint8); x[free] = 1; x[list(r)] ^= 1
        assert not ((H @ x) % 2).any() and ((L @ x) % 2).any()
        out.append((tuple(free), (t, a), tuple(ords[a][4:])))
    return out


def T(sched, chk, q):
    s, offs = sched[chk]
    return s + offs[POS[chk][q]]


def lifts(sched, P, L, basis="Z"):
    """True if single-hook logical L = (free, hookcheck, (q5,q6)) is realisable undetected in the bulk."""
    free, a, res = L
    RD = ZREAD if basis == "Z" else XREAD
    var = {"F": 0}
    def v(c):
        if c not in var: var[c] = len(var)
        return var[c]
    cons = []                       # x_u - x_w <= c  as (u, w, c)
    for w in free:
        cs = RD[w]
        for c in cs:
            for d in cs:
                if c != d:
                    cons.append((v(c), v(d), (T(sched, d, w) - T(sched, c, w)) // P + 1))
    for q in res:
        ta = T(sched, a, q)
        for c in RD[q]:
            off = (ta - T(sched, c, q)) // P + 1
            cons.append((v(c), 0, off)); cons.append((0, v(c), -off))
    n = len(var); d = [0] * n
    for _ in range(n + 1):
        ch = False
        for u, w, c in cons:
            if d[w] + c < d[u]:
                d[u] = d[w] + c; ch = True
        if not ch:
            return True
    return False


def witness(sched, P, L, basis="Z"):
    """Potentials H (dict check -> instance, 'F' -> hook instance) and, per free qubit, a fault time just after a read
    (absolute tick of the CNOT after which the data fault is placed), or None if blocked."""
    free, a, res = L
    RD = ZREAD if basis == "Z" else XREAD
    keys = ["F"] + sorted({c for w in list(free) + list(res) for c in RD[w]})
    idx = {k: i for i, k in enumerate(keys)}
    cons = []
    for w in free:
        for c in RD[w]:
            for d in RD[w]:
                if c != d:
                    cons.append((idx[c], idx[d], (T(sched, d, w) - T(sched, c, w)) // P + 1))
    for q in res:
        ta = T(sched, a, q)
        for c in RD[q]:
            off = (ta - T(sched, c, q)) // P + 1
            cons.append((idx[c], 0, off)); cons.append((0, idx[c], -off))
    n = len(keys); d = [0] * n
    for it in range(n + 1):
        ch = False
        for u, w, c in cons:
            if d[w] + c < d[u]:
                d[u] = d[w] + c; ch = True
        if not ch: break
    else:
        return None
    H = {k: d[i] for k, i in idx.items()}
    times = {}
    for w in free:
        # intervals (T_c + (H_c-1)P, T_c + H_c P); fault right after the latest left endpoint (a read of w)
        lefts = [T(sched, c, w) + (H[c] - 1) * P for c in RD[w]]
        rights = [T(sched, c, w) + H[c] * P for c in RD[w]]
        assert max(lefts) < min(rights)
        times[w] = max(lefts)
    return H, times
