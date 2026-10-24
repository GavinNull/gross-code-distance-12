"""SM S14 (round reduction for circuits A, B, C): machine check of the premises of the gap argument for circuit A.

From the noiseless memory circuits (R = 2, 3, 5, 9, both bases), parsed layer by layer:
  * every ancilla: instance j reset at s_q + D j with s_q independent of R, measured at s_q + D j + dm_q with
    0 < dm_q <= D - 1, its six CNOTs strictly inside the window; X ancillas are CNOT controls, Z ancillas targets
    (a freshly reset ancilla never pushes errors onto the data); data: reset at layer 0, only CNOTs, final readout;
  * the detector set is exactly {first measurement} + {consecutive comparisons} + {last measurement vs readout};
  * G = max(2D + dm_max - 1, D + S + dm_max) (paper: 52), so a weight-11 undetected logical spans <= 10 (G - 1) layers;
then, on the noisy SD6 circuits (R = 6, 12, both bases), the layer-by-layer insertion property: circuit(R + 1) equals
circuit(R) with one D-layer block inserted at layer x, for every x in a contiguous range [lo, D R + c]; every block
holds one measurement of each of the 144 ancillas.  Finally R' = (lo + D - 1 + 10 (G - 1) + 2 D - 2 - c) // D
(the deletion step; paper: 32), which must not exceed the largest R covered by the lift of SM S13 (--rmax, default 32).

With --separated (for circuit C, common frame): the rounds are separated in time (the last measurement of round j
precedes the first reset of round j+1, R = 3, 8, 14), so a weight-11 undetected logical occupies at most 11
consecutive rounds and, with the insertion property, any R reduces to R <= 13.

Optionally (--slab, for circuit B) premise (A) of the slab argument: on every data qubit, every spreading CNOT of
round k after the start of round k+1's slab precedes every reading CNOT of round k+1 (R = 3, 8, 24).

    python code/premises.py --circuit A --rmax 32
    python code/premises.py --circuit B --slab
    python code/premises.py --circuit C --separated --rmax 14
"""
import argparse

import numpy as np

from common_cli import Verdict, circuit, load_code
from gross12.noise import add_sd6
from gross12.schedule import build_circuits, layout_for, unroll

ap = argparse.ArgumentParser()
ap.add_argument("--circuit", default="A")
ap.add_argument("--rmax", type=int, default=32)
ap.add_argument("--slab", action="store_true")
ap.add_argument("--separated", action="store_true")
a = ap.parse_args()
code = load_code()
spec = circuit(a.circuit).canonical()
D = spec.period
lay = layout_for(code)
n = lay.n
xa, za = set(lay.x_anc), set(lay.z_anc)
H = {"Z": code.HZ, "X": code.HX}
anc = {"Z": list(lay.z_anc), "X": list(lay.x_anc)}
V = Verdict()

if not a.slab:
    bad = []
    starts0 = dm = None
    for R in (2, 3, 5, 9):
        for basis in "ZX":
            c = build_circuits(spec, code, R)[basis]
            ev, meas_of, cnt, dets = {}, [], {}, []
            layer = 0
            for op in c.flattened():
                nm = op.name
                if nm == "TICK":
                    layer += 1
                    continue
                tg = [t.value for t in op.targets_copy()] if nm not in ("DETECTOR", "OBSERVABLE_INCLUDE") else None
                if nm in ("R", "RX"):
                    for q in tg:
                        ev.setdefault(q, []).append((layer, "R"))
                elif nm == "CX":
                    for x, y in zip(tg[::2], tg[1::2]):
                        if not ((x in xa and y < n) or (y in za and x < n)):
                            bad.append(f"R{R}{basis} CX {x},{y} orientation")
                        ev.setdefault(x, []).append((layer, "C")); ev.setdefault(y, []).append((layer, "C"))
                elif nm in ("M", "MX"):
                    for q in tg:
                        k = cnt.get(q, 0); cnt[q] = k + 1
                        meas_of.append((q, k)); ev.setdefault(q, []).append((layer, "M"))
                elif nm == "DETECTOR":
                    dets.append(frozenset(meas_of[len(meas_of) + t.value] for t in op.targets_copy()))
                elif nm != "OBSERVABLE_INCLUDE":
                    bad.append(f"R{R}{basis} unexpected op {nm}")
            END = layer
            starts, dmq = {}, {}
            for q in list(xa | za):
                e = ev[q]
                if len(e) != 8 * R:
                    bad.append(f"R{R}{basis} ancilla {q} has {len(e)} operations"); continue
                for j in range(R):
                    blk = e[8 * j: 8 * j + 8]
                    if [k for _, k in blk] != ["R"] + ["C"] * 6 + ["M"]:
                        bad.append(f"R{R}{basis} ancilla {q} instance {j} pattern"); continue
                    r, m = blk[0][0], blk[7][0]
                    starts.setdefault(q, r - D * j)
                    dmq.setdefault(q, m - r)
                    if r != starts[q] + D * j or m - r != dmq[q] or not (0 < m - r <= D - 1):
                        bad.append(f"R{R}{basis} ancilla {q} instance {j} timing")
                    if not all(r < t < m for t, _ in blk[1:7]):
                        bad.append(f"R{R}{basis} ancilla {q} instance {j} window")
            for q in range(n):
                e = ev[q]
                if e[0] != (0, "R") or e[-1] != (END, "M") or any(k != "C" for _, k in e[1:-1]):
                    bad.append(f"R{R}{basis} data {q} pattern")
            if starts0 is None:
                starts0, dm = starts, dmq
            elif starts != starts0 or dmq != dm:
                bad.append(f"R{R}{basis} starts/dm depend on R")
            S_ = max(starts.values()) - min(starts.values()); dmax_ = max(dmq.values())
            if any(END > starts[q] + D * (R - 1) + S_ + dmax_ + 1 for q in starts):
                bad.append(f"R{R}{basis} readout bound")
            want = set()
            for i, q in enumerate(anc[basis]):
                want.add(frozenset({(q, 0)}))
                want |= {frozenset({(q, j), (q, j - 1)}) for j in range(1, R)}
                want.add(frozenset({(int(d), 0) for d in np.flatnonzero(H[basis][i])} | {(q, R - 1)}))
            if set(dets) != want or len(dets) != len(want):
                bad.append(f"R{R}{basis} detector set")
    S = max(starts0.values()) - min(starts0.values())
    dmax = max(dm.values())
    G = max(2 * D + dmax - 1, D + S + dmax)
    span = 10 * (G - 1)
    V(not bad, f"[{a.circuit}] structure (R = 2, 3, 5, 9, both bases): D = {D}, starts independent of R, "
               f"dm_max = {dmax} <= D - 1, S = {S}, CNOTs inside windows, template orientation, detector set exact "
               f"({len(bad)} problems{': ' + '; '.join(bad[:5]) if bad else ''})")
    V(True, f"[{a.circuit}] G = max(2D + dm_max - 1, D + S + dm_max) = {G}; a weight-11 undetected logical spans "
            f"<= 10 (G - 1) = {span} layers")

    def layers(c):
        out, cur = [], []
        for op in c.flattened():
            if op.name == "TICK":
                out.append("\n".join(sorted(cur))); cur = []
            elif op.name not in ("DETECTOR", "OBSERVABLE_INCLUDE", "SHIFT_COORDS", "QUBIT_COORDS"):
                cur.append(str(op))
        out.append("\n".join(sorted(cur)))
        return out

    lo_s, chi_s, nblk, contiguous = set(), set(), set(), True
    for basis in "ZX":
        for R in (6, 12):
            x = layers(add_sd6(build_circuits(spec, code, R)[basis]))
            y = layers(add_sd6(build_circuits(spec, code, R + 1)[basis]))
            assert len(y) - len(x) == D
            ok = [i for i in range(len(x) + 1) if y[:i] == x[:i] and y[i + D:] == x[i:]]
            contiguous &= ok == list(range(min(ok), max(ok) + 1))
            lo_s.add(min(ok)); chi_s.add(max(ok) - D * (R + 1))
            blk = y[min(ok):min(ok) + D]
            nblk.add(sum(len(s.split()) - 1 for l_ in blk for s in l_.split("\n") if s.split() and s.split()[0] in ("M", "MX")))
    good = contiguous and len(lo_s) == 1 and len(chi_s) == 1 and nblk == {144}
    lo, c_hi = max(lo_s), max(chi_s)
    V(good, f"[{a.circuit}] insertion (SD6, R = 6, 12, both bases): circuit(R+1) = circuit(R) + one {D}-layer block "
            f"inserted at any x in [{lo}, {D}R{c_hi + D:+d}] (contiguous), 144 measurements per block")
    if a.separated:
        sep = []
        for R in (3, 8, 14):
            U = unroll(spec, code, R)
            st = {j: min(U.start[q] + D * j for q in U.start) for j in range(R)}
            en = {}
            for t, lst in U.meas.items():
                for q, ty, j in lst:
                    en[j] = max(en.get(j, -1), t)
            sep.append(all(en[j] < st[j + 1] for j in range(R - 1)))
        V(all(sep) and good, f"[{a.circuit}] rounds separated in time (R = 3, 8, 14): {sep}; a fault-free round splits "
                             f"an undetected logical, so a weight-11 one spans <= 11 rounds; with the insertion property "
                             f"any R reduces to R' <= 13 <= {a.rmax}")
        V.exit()
    Rp = (lo + D - 1 + span + 2 * D - 2 - c_hi) // D
    V(Rp <= a.rmax, f"[{a.circuit}] deletion: every weight-11 undetected logical maps into a circuit with R' <= {Rp} "
                    f"rounds; the lift (SM S13) covers R <= {a.rmax}" + (" (paper: G = 52, R' = 32)" if a.circuit == "A" else ""))
else:
    for R in (3, 8, 24):
        U = unroll(spec, code, R)
        typ = {}
        for t, lst in U.preps.items():
            for q, ty in lst:
                typ[q] = ty
        ev = []
        for t, lst in U.cnots.items():
            for x, y in lst:
                an = x if x in U.start else y
                dq = y if an == x else x
                ev.append((t, dq, typ[an], (t - U.start[an]) // D))
        st = {j: min(U.start[q] + D * j for q in U.start) for j in range(R)}
        res = []
        for basis, spread, read in (("Z", "X", "Z"), ("X", "Z", "X")):
            late_by_q, read_by_q = {}, {}
            for t, dq, ty, j in ev:
                if ty == spread and j < R - 1 and t >= st[j + 1]:
                    late_by_q.setdefault((dq, j), []).append(t)
                if ty == read and j >= 1:
                    read_by_q.setdefault((dq, j - 1), []).append(t)
            viol = sum(1 for k_, ts in late_by_q.items() if k_ in read_by_q and min(read_by_q[k_]) < max(ts))
            res.append(viol)
        V(res == [0, 0], f"[{a.circuit}] slab premise (A), R = {R}: violations (Z basis, X basis) = {tuple(res)}")
V.exit()
