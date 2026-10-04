"""Auditor's independent construction of the E-013 two-colour BB108 schedule (from the TEXT rule only),
own stim memory circuit generator, own non-interleaving / partition test.  Does not import search/noninterleaved.

Group element g = x^a y^b  <-> index a*m + b  (baselines.bb_code: x = S_l (x) I_m).  Row coordinate y = b.
Terms t in 0..5 = [A1,A2,A3,B1,B2,B3] = [x^3, y, y^2, y^3, x, x^2].
X check i via term t: t<3 -> L[A_t(i)], t>=3 -> R[B_t(i)];  Z check i: t<3 -> R[A_t^T(i)], t>=3 -> L[B_t^T(i)].
"""
from __future__ import annotations
import numpy as np, stim
from baselines.bb_code import BBCode

L_, M_ = 9, 6
D = 8
X_TIMES = dict(prep=0, cn=[1, 2, 3, 4, 5, 6], meas=7)
Z_TIMES = dict(prep=4, cn=[5, 6, 7, 0, 1, 2], meas=3)
X_EVEN = [0, 1, 2, 3 + 2, 3 + 0, 3 + 1]
X_ODD = [2, 1, 0, 3 + 2, 3 + 0, 3 + 1]
Z_EVEN = [3 + 2, 3 + 1, 3 + 0, 0, 1, 2]
Z_ODD = [3 + 0, 3 + 1, 3 + 2, 0, 1, 2]


def code():
    return BBCode(L_, M_, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"])


def col(code, side, j):
    return j if side == "L" else code.n2 + j


def term_orders(xe=X_EVEN, xo=X_ODD, ze=Z_EVEN, zo=Z_ODD):
    return xe, xo, ze, zo


def build(xe=X_EVEN, xo=X_ODD, ze=Z_EVEN, zo=Z_ODD):
    """Returns dict with per-check (prep, meas, [(col, t), ...] in CNOT order)."""
    c = code()
    out = {"X": [], "Z": []}
    for i in range(c.n2):
        b = i % M_
        terms = xe if b % 2 == 0 else xo
        cn = [(col(c, *c.x_check_neighbor(t, i)), X_TIMES["cn"][k]) for k, t in enumerate(terms)]
        out["X"].append((X_TIMES["prep"], X_TIMES["meas"], cn))
        terms = ze if b % 2 == 0 else zo
        cn = [(col(c, *c.z_check_neighbor(t, i)), Z_TIMES["cn"][k]) for k, t in enumerate(terms)]
        out["Z"].append((Z_TIMES["prep"], Z_TIMES["meas"], cn))
    return c, out


def to_spec(sched):
    from evaluators.candidate import CheckTiming, ScheduleSpec
    mk = lambda lst: tuple(CheckTiming(p, m, tuple(sorted(cn))) for p, m, cn in lst)
    return ScheduleSpec(D, mk(sched["X"]), mk(sched["Z"]), name="E-013-auditor")


def orders(sched):
    """CNOT order (data cols) per check, read cyclically from prep."""
    res = {}
    for T in ("X", "Z"):
        res[T] = [[a for a, t in sorted(cn, key=lambda e: (e[1] - p) % D)] for p, m, cn in sched[T]]
    return res


def legality(c, sched):
    probs = []
    for T, H in (("X", c.HX), ("Z", c.HZ)):
        for i, (p, m, cn) in enumerate(sched[T]):
            cols = sorted(a for a, _ in cn)
            if cols != sorted(np.nonzero(H[i])[0].tolist()):
                probs.append(f"{T}{i} support mismatch")
            offs = [(t - p) % D for _, t in cn]
            if len(set(offs)) != 6 or not all(0 < o < (m - p) % D for o in offs):
                probs.append(f"{T}{i} window")
    use = {}
    for T in ("X", "Z"):
        for i, (p, m, cn) in enumerate(sched[T]):
            for a, t in cn:
                use.setdefault((t, a), []).append(f"{T}{i}")
    for k, v in use.items():
        if len(v) > 1:
            probs.append(f"data {k[1]} t={k[0]} used by {v}")
    return probs


# ------------------------------------------------------------------ own memory circuit
def memory(c, sched, basis, rounds, p=1e-3):
    """Own unrolling: instance j of a check: prep at prep+8j (+8 shift for Z prep 4 handled by window),
    cnots at prep + off, meas at prep + off_meas.  Global time origin: data reset at tick 0, checks start at
    tick 1 + (offset).  SD6 noise: DEPOLARIZE2 after CX, DEPOLARIZE1 on idle qubits each tick, flip after reset,
    flip before measurement."""
    n, n2 = c.n, c.n2
    xa = [n + i for i in range(n2)]
    za = [n + n2 + i for i in range(n2)]
    ev = {}  # tick -> list of ops (kind, args)
    def add(t, op):
        ev.setdefault(t, []).append(op)
    meas_order = []  # (tick, type, row, round)
    for T, anc in (("X", xa), ("Z", za)):
        for i, (pp, mm, cn) in enumerate(sched[T]):
            dm = (mm - pp) % D
            for j in range(rounds):
                s = 1 + pp + D * j     # X prep 0 -> tick 1; Z prep 4 -> tick 5
                add(s, ("R" + T, anc[i]))
                for a, t in cn:
                    tt = s + (t - pp) % D
                    add(tt, ("CX", (anc[i], a) if T == "X" else (a, anc[i])))
                add(s + dm, ("M" + T, anc[i], T, i, j))
    last = max(ev)
    fin = last + 1
    # data reset at tick 0
    nq = n + 2 * n2
    circ = stim.Circuit()
    allq = list(range(nq))
    mrec = []  # list of keys in measurement order
    for t in range(0, fin + 1):
        busy = set()
        ops = ev.get(t, [])
        if t == 0:
            circ.append("R" if basis == "Z" else "RX", list(range(n)))
            circ.append("X_ERROR" if basis == "Z" else "Z_ERROR", list(range(n)), p)
            busy |= set(range(n))
        resets = [o for o in ops if o[0] in ("RX", "RZ")]
        for o in resets:
            circ.append("RX" if o[0] == "RX" else "R", [o[1]])
            circ.append("Z_ERROR" if o[0] == "RX" else "X_ERROR", [o[1]], p)
            assert o[1] not in busy; busy.add(o[1])
        cx = [o[1] for o in ops if o[0] == "CX"]
        for a, b in cx:
            assert a not in busy and b not in busy, (t, a, b)
            busy |= {a, b}
            circ.append("CX", [a, b]); circ.append("DEPOLARIZE2", [a, b], p)
        ms = [o for o in ops if o[0] in ("MX", "MZ")]
        for o in ms:
            assert o[1] not in busy; busy.add(o[1])
            circ.append("Z_ERROR" if o[0] == "MX" else "X_ERROR", [o[1]], p)
            circ.append("MX" if o[0] == "MX" else "M", [o[1]])
            mrec.append(("anc",) + o[2:])
        if t == fin:
            circ.append("X_ERROR" if basis == "Z" else "Z_ERROR", list(range(n)), p)
            circ.append("M" if basis == "Z" else "MX", list(range(n)))
            for q in range(n):
                mrec.append(("data", q))
            busy |= set(range(n))
        idle = [q for q in allq if q not in busy]
        if idle and t not in (0,):
            circ.append("DEPOLARIZE1", idle, p)
        circ.append("TICK")
    idx = {k: i for i, k in enumerate(mrec)}
    N = len(mrec)
    rec = lambda k: stim.target_rec(idx[k] - N)
    H = c.HZ if basis == "Z" else c.HX
    for i in range(n2):
        for j in range(rounds):
            tg = [rec(("anc", basis, i, j))]
            if j > 0:
                tg.append(rec(("anc", basis, i, j - 1)))
            circ.append("DETECTOR", tg)
        tg = [rec(("anc", basis, i, rounds - 1))] + [rec(("data", q)) for q in np.nonzero(H[i])[0]]
        circ.append("DETECTOR", tg)
    Lops = c.logical_z() if basis == "Z" else c.logical_x()
    for k, v in enumerate(Lops):
        circ.append("OBSERVABLE_INCLUDE", [rec(("data", q)) for q in np.nonzero(v)[0]], k)
    return circ


# ------------------------------------------------------------------ non-interleaving / partition test
def interleave_tests(c, sched, rounds=6):
    """pairwise: for each (X instance, Z instance) sharing data qubits, the CNOT sequence on the shared qubits
    is all-X-before-all-Z or all-Z-before-all-X (2603.05481 v2 Sec II.A non-interleaved).
    partition: precedence graph on check instances (edges between consecutive CNOTs on each data qubit);
    partitionable iff no SCC contains an X/Z type-change edge (equivalently a consistent global phase
    exists, nondecreasing along each data line and increasing on every type change)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    nodes, ev = {}, {}
    for T in ("X", "Z"):
        for i, (pp, mm, cn) in enumerate(sched[T]):
            for j in range(rounds):
                nid = nodes.setdefault((T, i, j), len(nodes))
                s = pp + D * j
                for a, t in cn:
                    ev.setdefault(a, []).append((s + (t - pp) % D, nid, T))
    seq, edges = {}, {}
    for a, Lst in ev.items():
        Lst.sort()
        assert len({t for t, _, _ in Lst}) == len(Lst)
        for (t1, u, Tu), (t2, v, Tv) in zip(Lst, Lst[1:]):
            if u != v:
                edges[(u, v)] = max(edges.get((u, v), 0), int(Tu != Tv))
        for k, (t1, u, Tu) in enumerate(Lst):
            for (t2, v, Tv) in Lst[k + 1:]:
                if Tu != Tv:
                    key = (u, v) if Tu == "X" else (v, u)
                    seq.setdefault(key, set()).add("XZ" if Tu == "X" else "ZX")
    mixed = [k for k, v in seq.items() if len(v) > 1]
    Nn = len(nodes)
    r = [a for a, b in edges]; cc = [b for a, b in edges]
    G = coo_matrix((np.ones(len(r)), (r, cc)), shape=(Nn, Nn)).tocsr()
    _, lab = connected_components(G, directed=True, connection="strong")
    bad = [(a, b) for (a, b), w in edges.items() if w and lab[a] == lab[b]]
    return dict(rounds=rounds, overlapping_pairs=len(seq), mixed_pairs=len(mixed), partitionable=not bad,
                type_change_edges_in_scc=len(bad), largest_scc=int(np.bincount(lab).max()))
