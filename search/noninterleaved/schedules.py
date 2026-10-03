"""Depth-8 single-ancilla schedules for BB / 2BGA codes and a non-interleaving checker.

Term indices t in 0..5 = [A1, A2, A3, B1, B2, B3] (baselines.bb_code convention):
  X check i touches L[A_t(i)] (t<3) or R[B_{t-3}(i)];  Z check i touches R[A_t^T(i)] (t<3) or L[B^T(i)].
So data qubits in L see X terms {0,1,2} and Z terms {3,4,5}; data in R see X terms {3,4,5} and Z terms {0,1,2}.

Per-check timing (cyclic period 8, every ancilla busy all 8 slots, prep and measure are separate steps as in
IBM Table 5 / Strikis Fig. 12): prep at slot P, CNOTs at P+1..P+6 in the check's order, measure at P+7 (mod 8).

`build_schedule(code, x_spec, z_spec)`: x_spec[i] = (P, order-of-terms) for X check i (likewise Z).  A uniform
("tiled") circuit uses the same (P, order) for every check.

Non-interleaving (arXiv:2603.05481 v2 Sec. II.A; Corollary 1 needs a temporal X/Z partition):
`interleaving(sched)` unrolls the cyclic schedule (check instance = (check, round)); for every overlapping
(X check x, Z check z) pair it computes, for each relative round shift, whether all shared-qubit CNOTs of the Z
instance precede those of the X instance ('Z'), the opposite ('X') or mixed.  The circuit is called
non-interleaved iff (i) no pair is mixed for any round shift and (ii) the thresholds are consistent with a
global round relabelling: there are integers a_x, b_z with  "Z instance r precedes X instance s  <=>
s - r >= a_x - b_z"  for every overlapping pair (checked by BFS over the overlap graph).  Under (i)+(ii) the
circuit can be cut, round by round, into a Z part followed by an X part, which is exactly what the proofs of
Prop. 2 / Corollary 1 use.
"""
from __future__ import annotations

from collections import deque

import numpy as np

from baselines.schedule import Layer, Schedule, bb_layout

PERIOD = 8


def neighbours(code, kind: str, i: int, t: int) -> int:
    """Data column (0..n-1) touched by check i of `kind` via term t."""
    b, j = (code.x_check_neighbor if kind == "X" else code.z_check_neighbor)(t, i)
    return j if b == "L" else code.n2 + j


def build_schedule(code, x_spec, z_spec, name="ni") -> Schedule:
    lay = bb_layout(code)
    data = lay["L"] + lay["R"]
    layers = [Layer() for _ in range(PERIOD)]
    for kind, spec, qs in (("X", x_spec, lay["X"]), ("Z", z_spec, lay["Z"])):
        for i, q in enumerate(qs):
            P, order = spec[i]
            (layers[P % PERIOD].prep_x if kind == "X" else layers[P % PERIOD].prep_z).append(q)
            (layers[(P + 7) % PERIOD].meas_x if kind == "X" else layers[(P + 7) % PERIOD].meas_z).append(q)
            for k, t in enumerate(order):
                d = data[neighbours(code, kind, i, t)]
                layers[(P + 1 + k) % PERIOD].cnots.append((q, d) if kind == "X" else (d, q))
    for L in layers:
        L.cnots.sort()
    return Schedule(name=name, num_qubits=4 * code.n2, data=data, x_checks=lay["X"], z_checks=lay["Z"],
                    layers=layers)


def uniform_schedule(code, PX, sX, PZ, sZ, name="ni_uniform") -> Schedule:
    n2 = code.n2
    return build_schedule(code, [(PX, sX)] * n2, [(PZ, sZ)] * n2, name)


def data_conflict_free(PX, sX, PZ, sZ) -> bool:
    """Uniform schedule: every data qubit sees its 6 CNOTs in 6 distinct slots mod 8."""
    tx = {t: (PX + 1 + k) % PERIOD for k, t in enumerate(sX)}
    tz = {t: (PZ + 1 + k) % PERIOD for k, t in enumerate(sZ)}
    Lslots = [tx[0], tx[1], tx[2], tz[3], tz[4], tz[5]]
    Rslots = [tx[3], tx[4], tx[5], tz[0], tz[1], tz[2]]
    return len(set(Lslots)) == 6 and len(set(Rslots)) == 6


def layer_conflict_free(sched: Schedule) -> bool:
    for L in sched.layers:
        qs = L.qubits()
        if len(qs) != len(set(qs)):
            return False
    return True


def _check_times(sched: Schedule):
    """check qubit -> (prep slot, {data qubit: slot offset after prep (1..)})."""
    D = sched.depth
    xset = set(sched.x_checks)
    prep, ev = {}, {}
    for t, L in enumerate(sched.layers):
        for q in L.prep_x + L.prep_z:
            prep[q] = t
        for c, tg in L.cnots:
            chk, d = (c, tg) if c in xset else (tg, c)
            ev.setdefault(chk, []).append((t, d))
    out = {}
    for q, lst in ev.items():
        out[q] = (prep[q], {d: prep[q] + ((t - prep[q]) % D) for t, d in lst})   # absolute time in round 0
    return out


def interleaving(sched: Schedule) -> dict:
    """See module docstring.  Returns {'non_interleaved': bool, 'mixed_pairs': int, 'pairs': int,
    'consistent': bool, 'threshold_hist': {...}}."""
    D = sched.depth
    xset = set(sched.x_checks)
    T = _check_times(sched)
    by_data = {}
    for q, (_, m) in T.items():
        for d in m:
            by_data.setdefault(d, []).append(q)
    pairs = {}
    for d, qs in by_data.items():
        for x in qs:
            if x not in xset:
                continue
            for z in qs:
                if z in xset:
                    continue
                pairs.setdefault((x, z), []).append(d)
    mixed = 0
    thr = {}
    hist = {}
    for (x, z), shared in pairs.items():
        # X instance s at T[x] + D*s ; Z instance r at T[z] + D*r ; delta = s - r
        c = None
        bad = False
        for delta in range(-3, 4):
            o = {(T[x][1][d] + D * delta) > T[z][1][d] for d in shared}   # True: Z precedes X
            if len(o) > 1:
                bad = True
                break
            if o.pop() and c is None:
                c = delta          # smallest delta with Z first
        if bad:
            mixed += 1
            continue
        thr[(x, z)] = c
        hist[c] = hist.get(c, 0) + 1
    consistent = mixed == 0
    if consistent:
        # potentials: a_x - b_z = c(x,z)
        adj = {}
        for (x, z), c in thr.items():
            adj.setdefault(("x", x), []).append((("z", z), -c))   # b_z = a_x - c
            adj.setdefault(("z", z), []).append((("x", x), c))    # a_x = b_z + c
        pot = {}
        for s in adj:
            if s in pot:
                continue
            pot[s] = 0
            dq = deque([s])
            while dq and consistent:
                u = dq.popleft()
                for v, w in adj[u]:
                    if v not in pot:
                        pot[v] = pot[u] + w
                        dq.append(v)
                    elif pot[v] != pot[u] + w:
                        consistent = False
                        break
            if not consistent:
                break
    return {"non_interleaved": mixed == 0 and consistent, "mixed_pairs": mixed, "pairs": len(pairs),
            "consistent_potentials": consistent, "threshold_hist": {int(k): v for k, v in sorted(hist.items())}}
