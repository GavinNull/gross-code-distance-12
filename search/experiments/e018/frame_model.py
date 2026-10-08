"""E-018 stage c: analytic "frame model" of lifting for non-wrapping frame schedules (cpgen), used for design.

Z-basis memory (X faults, X-check hooks, Z checks read); X basis symmetric with roles swapped.
For an extended logical S whose columns have pairwise disjoint qubit supports, an 11-fault realisation exists in
the bulk (many rounds, away from the boundaries) iff the following difference-constraint system is feasible:
  variables h(c) in Z for every Z check c touching Q = union of supports (h(c) = the round in which c first sees
  the errors on Q∩c; all of Q∩c must be seen in the same round, since |Q∩c| is even and... each pair must agree)
  -- careful: the exact condition is "each round's parity even"; we use the stronger "all seen in the same round",
     which is exact when |Q∩c| = 2 and sufficient in general (so the model may over-report blocking when
     |Q∩c| >= 4; the exact DP decides);
  free data qubit w with Z checks c1, c2, c3 in read order: h(c3) <= h(c2) <= h(c1) <= h(c3) + 1;
  hook of check a after its k-th CNOT, residual qubit q: h(c_i(q)) = F_a + [c_i reads q before a's CNOT on q].
Feasible <=> no negative cycle (Bellman-Ford).
"""
from __future__ import annotations

import numpy as np

from search.experiments.e018.common import ext, orders


def read_tables(spec, basis):
    """For each data qubit: list of (time, check index) of reading checks (Z checks in Z basis), sorted; and
    for hooks: dict (check index of hooking type, data qubit) -> CNOT time."""
    rd = spec.z_checks if basis == "Z" else spec.x_checks
    hk = spec.x_checks if basis == "Z" else spec.z_checks
    reads = [[] for _ in range(144)]
    for i, c in enumerate(rd):
        for q, t in c.cnots:
            reads[q].append((t, i))
    for r in reads:
        r.sort()
    htime = {}
    for i, c in enumerate(hk):
        for q, t in c.cnots:
            htime[(i, q)] = t
    return reads, htime


def column_events(kind, j):
    """('d', q) or ('h', check, suffix support) for column j (first support)."""
    E = ext(kind)
    sups = E["col_sups"][j]
    for s in sups:
        if len(s) == 1:
            return ("d", s[0])
    xo, zo = orders()
    ords = xo if kind == "X" else zo
    s = set(sups[0])
    for i, o in enumerate(ords):
        if set(o[len(o) - len(s):]) == s:
            return ("h", i, tuple(o[len(o) - len(s):]))
    raise AssertionError


def feasible(S, kind, reads, htime):
    """Bellman-Ford on the difference constraints; returns True (lifts in the model), False, or None (overlapping
    supports, not modelled)."""
    evs = [column_events(kind, j) for j in S]
    qs = []
    for e in evs:
        qs += [e[1]] if e[0] == "d" else list(e[2])
    if len(set(qs)) != len(qs):
        return None
    # Q∩c per reading check
    from itertools import product
    qset = set(qs)
    rc = {}
    for q in qs:
        for _, i in reads[q]:
            rc.setdefault(i, []).append(q)

    def pairings(lst):
        if not lst:
            yield []
            return
        x = lst[0]
        for k in range(1, len(lst)):
            rest = lst[1:k] + lst[k + 1:]
            for p in pairings(rest):
                yield [(x, lst[k])] + p
    multi = [i for i, l in rc.items() if len(l) > 2]
    for i, l in rc.items():
        assert len(l) % 2 == 0, "odd |Q∩c|"
    for choice in product(*[list(pairings(sorted(rc[i]))) for i in multi]):
        cls = {}
        for i, l in rc.items():
            if len(l) == 2:
                cls[(i, l[0])] = cls[(i, l[1])] = (i, 0)
        for i, prs in zip(multi, choice):
            for k, (x, y) in enumerate(prs):
                cls[(i, x)] = cls[(i, y)] = (i, k)
        if _bf(evs, reads, htime, cls):
            return True
    return False


def _bf(evs, reads, htime, cls):
    var = {}

    def v(key):
        if key not in var:
            var[key] = len(var)
        return var[key]
    cons = []                      # (u, w, c): h[u] - h[w] <= c
    for e in evs:
        if e[0] == "d":
            q = e[1]
            cs = [v(("c", cls[(i, q)])) for _, i in reads[q]]
            cons += [(cs[2], cs[1], 0), (cs[1], cs[0], 0), (cs[0], cs[2], 1)]
        else:
            a = e[1]; F = v(("F", a))
            for q in e[2]:
                ta = htime[(a, q)]
                for t, i in reads[q]:
                    c = v(("c", cls[(i, q)]))
                    off = 1 if t < ta else 0
                    cons += [(c, F, off), (F, c, -off)]
    n = len(var)
    d = np.zeros(n)
    for _ in range(n + 1):
        ch = False
        for u, w, c in cons:          # h[u] <= h[w] + c
            if d[w] + c < d[u]:
                d[u] = d[w] + c; ch = True
        if not ch:
            return True
    return False


# ----------------------------------------------------------------------------- general (pipelined) version
def abs_tables(spec, basis):
    """Absolute times: a check's instance 0 starts at its prep p in [0,P); CNOT at p + ((t - p) mod P)."""
    P = spec.period
    rd = spec.z_checks if basis == "Z" else spec.x_checks
    hk = spec.x_checks if basis == "Z" else spec.z_checks
    reads = [[] for _ in range(144)]
    for i, c in enumerate(rd):
        for q, t in c.cnots:
            reads[q].append((c.prep + (t - c.prep) % P, i))
    htime = {}
    for i, c in enumerate(hk):
        for q, t in c.cnots:
            htime[(i, q)] = c.prep + (t - c.prep) % P
    return reads, htime, P


def feasible_general(S, kind, reads, htime, P):
    """Difference-constraint model for any periodic schedule (absolute times, instance index H_c per check):
    free qubit w, checks c, d: H_c - H_d <= floor((t_d - t_c)/P) + 1;  hook a on residual q:
    H_c = F_a + floor((t_a - t_c)/P) + 1.  |Q∩c| > 2 handled by pairing enumeration (as `feasible`)."""
    from itertools import product
    evs = [column_events(kind, j) for j in S]
    qs = []
    for e in evs:
        qs += [e[1]] if e[0] == "d" else list(e[2])
    if len(set(qs)) != len(qs):
        return None
    rc = {}
    for q in qs:
        for _, i in reads[q]:
            rc.setdefault(i, []).append(q)

    def pairings(lst):
        if not lst:
            yield []
            return
        for k in range(1, len(lst)):
            for p in pairings(lst[1:k] + lst[k + 1:]):
                yield [(lst[0], lst[k])] + p
    multi = [i for i, l in rc.items() if len(l) > 2]
    for choice in product(*[list(pairings(sorted(rc[i]))) for i in multi]):
        cls = {}
        for i, l in rc.items():
            if len(l) == 2:
                cls[(i, l[0])] = cls[(i, l[1])] = (i, 0)
        for i, prs in zip(multi, choice):
            for k, (x, y) in enumerate(prs):
                cls[(i, x)] = cls[(i, y)] = (i, k)
        var, cons = {}, []

        def v(key):
            if key not in var:
                var[key] = len(var)
            return var[key]
        for e in evs:
            if e[0] == "d":
                q = e[1]
                for tc, c in reads[q]:
                    for td, d in reads[q]:
                        if c != d:
                            cons.append((v(("c", cls[(c, q)])), v(("c", cls[(d, q)])), (td - tc) // P + 1))
            else:
                a = e[1]; F = v(("F", a))
                for q in e[2]:
                    ta = htime[(a, q)]
                    for tc, c in reads[q]:
                        off = (ta - tc) // P + 1
                        cv = v(("c", cls[(c, q)]))
                        cons += [(cv, F, off), (F, cv, -off)]
        n = len(var)
        d = [0] * n
        ok = False
        for _ in range(n + 1):
            ch = False
            for u, w, c in cons:
                if d[w] + c < d[u]:
                    d[u] = d[w] + c; ch = True
            if not ch:
                ok = True
                break
        if ok:
            return True
    return False
