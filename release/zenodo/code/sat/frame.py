"""Bulk Pauli-frame model of weight-11 logicals (SM S9, S16).

A weight-11 extended logical S is modelled by realising each column: a data column as a free data error, a residual
column with support U of check a as errors on the qubits V = U (if |U| <= 3) or V = a \\ U, pinned at a's CNOT
times on V (the ancilla fault after the corresponding CNOT spreads to exactly these qubits, up to the check).
Each data qubit is read by three checks of the other type.  In the bulk, a data error at time theta is first seen by
check c in the first instance whose CNOT on that qubit comes after theta; writing H_c for that instance index, the
logical is undetected iff every reading check sees an even number of its errors in each instance, i.e. iff the
difference constraints below have a solution (no negative cycle):
    free qubit q read by c and d (same pairing class):  H_c - H_d <= floor((t_d(q) - t_c(q)) / P) + 1
    pinned qubit q of residual F read by c:              H_c - F  <= floor((t_a(q) - t_c(q)) / P) + 1   (hook+)
                                                          F - H_c  <= -(floor((t_a(q) - t_c(q)) / P) + 1)  (hook-)
A reading check that sees more than two qubits of S is handled by enumerating pairings of those qubits; the logical
lifts if some pairing is feasible.  Logicals whose realised qubit sets overlap are not modelled (skipped; this only
weakens the model, which is fine for UNSAT statements).  If the constraints are feasible for a circuit, that circuit
has a weight-11 undetected error for sufficiently many rounds.

A nogood for a feasible potential pi: at least one constraint that is tight-or-violatable must change, i.e. the OR
over edges of "t_i2 - t_i1 <= (K-1) P - 1" (free / hook+) or "t_i2 - t_i1 >= -K P" (hook-), K = pi_u - pi_w.
"""
from __future__ import annotations

import itertools

from .common import N2


def pairings(lst):
    if not lst:
        yield []
        return
    for k in range(1, len(lst)):
        for p in pairings(lst[1:k] + lst[k + 1:]):
            yield [(lst[0], lst[k])] + p


def column_real(F, kind, E, j):
    """('d', q) for a data column, ('h', a, V) for a residual column (V = pinned qubits of check a)."""
    sups = E["col_sups"][j]
    for s in sups:
        if len(s) == 1:
            return ("d", s[0])
    s = set(sups[0])
    for a in range(N2):
        qa = set(int(q) for q in F.T[kind][a])
        if s <= qa:
            V = s if len(s) <= 3 else qa - s
            return ("h", a, tuple(sorted(V)))
    raise AssertionError


def prepare(F, kind_data, kinds="XZ"):
    """kind_data[kind] = (E, sols): extended code and the weight-11 logicals as column-index tuples.  Keeps one
    representative per orbit of the family's subgroup.  Returns (records, number skipped)."""
    recs, skipped = [], 0
    Hs = set(F.Hs)
    for kind in kinds:
        rd = "Z" if kind == "X" else "X"
        E, sols = kind_data[kind]
        perms = [P for g, P in zip(E["group"], E["perms"]) if tuple(g) in Hs]
        seen, reps = set(), []
        for S in sols:
            if S in seen:
                continue
            for P in perms:
                seen.add(tuple(sorted(int(P[j]) for j in S)))
            reps.append(S)
        for S in reps:
            evs = [column_real(F, kind, E, j) for j in S]
            qs = []
            for e in evs:
                qs += [e[1]] if e[0] == "d" else list(e[2])
            if len(set(qs)) != len(qs):
                skipped += 1
                continue
            rc = {}
            for q in qs:
                for ty, c, lab in F.touch[q]:
                    if ty == rd:
                        rc.setdefault(c, []).append(q)
            assert all(len(v) % 2 == 0 for v in rc.values())
            recs.append({"kind": kind, "S": tuple(int(j) for j in S), "evs": evs, "rc": rc, "rd": rd})
    return recs, skipped


def skeleton(F, r, cls):
    kind, rd = r["kind"], r["rd"]
    cons = []
    for e in r["evs"]:
        if e[0] == "d":
            q = e[1]
            rds = [(cls[(c, q)], F.item(rd, c, lab)) for ty, c, lab in F.touch[q] if ty == rd]
            for (nc, ic), (nd, idd) in itertools.permutations(rds, 2):
                cons.append((nc, nd, "free", (ic, idd)))
        else:
            a = e[1]
            Fn = ("F", a)
            for q in e[2]:
                ia = F.item(kind, a, F.label_of(kind, a, q))
                for ty, c, lab in F.touch[q]:
                    if ty != rd:
                        continue
                    ic = F.item(rd, c, lab)
                    cons.append((cls[(c, q)], Fn, "hook+", (ic, ia)))
                    cons.append((Fn, cls[(c, q)], "hook-", (ic, ia)))
    return cons


def evaluate(F, recs, feasible):
    """all modelled logicals that lift for the current times: list of (record, constraints, potential).
    feasible(cons) returns a potential or None."""
    out = []
    for r in recs:
        rc = r["rc"]
        multi = [c for c, l in rc.items() if len(l) > 2]
        for choice in itertools.product(*[list(pairings(sorted(rc[c]))) for c in multi]):
            cls = {}
            for c, l in rc.items():
                if len(l) == 2:
                    cls[(c, l[0])] = cls[(c, l[1])] = ("c", c, 0)
            for c, prs in zip(multi, choice):
                for k, (x, y) in enumerate(prs):
                    cls[(c, x)] = cls[(c, y)] = ("c", c, k)
            cons = skeleton(F, r, cls)
            pi = feasible(cons)
            if pi is not None:
                out.append((r, cons, pi))
                break
    return out
