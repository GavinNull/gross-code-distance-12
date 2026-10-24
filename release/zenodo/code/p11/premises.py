"""All rounds for the period-11 circuits: machine check of the premises of the gap argument (End Matter) and the bound R'.

Gap argument (End Matter, "All rounds for Theorem 1"; the same with the constants of c11 for Theorem 2).  Let D be the
period; check q starts instance j at s_q + jD and measures it Delta_q <= D - 1 layers later; Delta = max Delta_q,
S = max s_q - min s_q.  If all faults of F_< lie at layers <= a and all faults of F_> at layers >= b, a comparison
detector responds to both only if b - a <= 2D + Delta - 2, a final detector only if b - a <= D + S + Delta - 1, a
first-round detector only if b - a <= D (the data frame produced by F_< is constant from layer a + D - 1 on).  So a
fault-free window of G = max(2D + Delta - 1, D + S + Delta) layers splits an undetected logical into two undetected
parts whose logical effects add to a nonzero value.  By induction on the weight (no undetected logical of weight
< d_ext by Lemma 1; then none of weight d_ext; then none of weight d_ext + 1), a minimal undetected logical of weight w
spans at most (w - 1)(G - 1) layers.  With the insertion property (the noisy circuit with R + 1 rounds equals the one
with R rounds with one D-layer block inserted at any layer x in [lo, D R + c]), deleting fault-free blocks in front
leaves the first fault at a layer <= lo + D - 1, and deleting blocks behind (at x = f_last + 2D - 2, where the data
frame has settled and every ancilla in flight is fault-free) stops with R' = (lo + D - 1 + span + 2D - 2 - c) // D.

Checked here (noiseless circuits R = 2, 3, 5, 9 parsed layer by layer; SD6 circuits for the insertion):
  * every ancilla: instance j reset at s_q + D j with s_q independent of R, measured at s_q + D j + Delta_q with
    0 < Delta_q <= D - 1, its six CNOTs strictly inside the window; X ancillas are CNOT controls, Z ancillas targets;
    data: reset at layer 0, only CNOTs, final readout; the detector set is exactly {first measurement} +
    {consecutive comparisons} + {last measurement vs readout};
  * the insertion property layer by layer, both bases, for every R in --rins (default 2-12); the range of x is
    contiguous and the same affine function of R for all R; every block holds one measurement of every ancilla;
  * G, the spans for w = d_ext and d_ext + 1, and R'_w, which must not exceed the largest R of the lift (--rmax).
With --separated (non-wrapping circuits whose rounds are separated in time, e.g. c12): a fault-free round strictly
inside the span of a minimal undetected logical splits it, so a logical of weight w spans at most w rounds and maps
into a circuit with at most w + 3 rounds.

    python code/p11/premises.py --circuit u11 --rmax 31       # paper: S = 1, Delta = 10, G = 31, x in [1, 11R], R' = 31
    python code/p11/premises.py --circuit c11 --rmax 25       # paper: R'_8 = 22, R'_9 = 25
    python code/p11/premises.py --circuit c12 --separated --rmax 12
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_cli import Verdict, parse_range                       # noqa: E402
from p11 import common as C                                       # noqa: E402
from gross12.noise import add_sd6                                 # noqa: E402
from gross12.schedule import build_circuits, layout_for, unroll   # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--circuit", default="u11")
ap.add_argument("--rmax", type=int, default=None)
ap.add_argument("--rins", default="2-12")
ap.add_argument("--separated", action="store_true")
a = ap.parse_args()
fam = C.family_of(a.circuit)
dext = C.FAMILY[fam]["dext"]
code = C.load_code(fam)
spec = C.circuit(a.circuit).canonical()
D = spec.period
lay = layout_for(code)
n = lay.n
xa, za = set(lay.x_anc), set(lay.z_anc)
nanc = len(xa) + len(za)
H = {"Z": code.HZ, "X": code.HX}
anc = {"Z": list(lay.z_anc), "X": list(lay.x_anc)}
rmax = a.rmax or (31 if fam == "gross" else 25)
V = Verdict()

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
        for q in sorted(xa | za):
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
            bad.append(f"R{R}{basis} starts/Delta depend on R")
        want = set()
        for i, q in enumerate(anc[basis]):
            want.add(frozenset({(q, 0)}))
            want |= {frozenset({(q, j), (q, j - 1)}) for j in range(1, R)}
            want.add(frozenset({(int(d), 0) for d in np.flatnonzero(H[basis][i])} | {(q, R - 1)}))
        if set(dets) != want or len(dets) != len(want):
            bad.append(f"R{R}{basis} detector set")
S = max(starts0.values()) - min(starts0.values())
dmax = max(dm.values())
offs = sorted({s % D for s in starts0.values()})
G = max(2 * D + dmax - 1, D + S + dmax)
spans = {w: (w - 1) * (G - 1) for w in (dext, dext + 1)}
V(not bad, f"[{a.circuit}] structure (R = 2, 3, 5, 9, both bases): D = {D}, starts independent of R (offsets mod D "
           f"{offs}, S = {S}), Delta_max = {dmax} <= D - 1, CNOTs inside windows, template orientation, detector set "
           f"exact ({len(bad)} problems{': ' + '; '.join(bad[:5]) if bad else ''})")
V(True, f"[{a.circuit}] G = max(2D + Delta - 1, D + S + Delta) = {G}; a minimal undetected logical of weight "
        f"{dext} spans <= {spans[dext]} layers, of weight {dext + 1} <= {spans[dext + 1]} layers")


def layers(c):
    out, cur = [], []
    for op in c.flattened():
        if op.name == "TICK":
            out.append("\n".join(sorted(cur))); cur = []
        elif op.name not in ("DETECTOR", "OBSERVABLE_INCLUDE", "SHIFT_COORDS", "QUBIT_COORDS"):
            cur.append(str(op))
    out.append("\n".join(sorted(cur)))
    return out


lo_s, chi_s, nblk, contiguous, Rs = set(), set(), set(), True, parse_range(a.rins)
for basis in "ZX":
    prev = None
    for R in Rs:
        x = prev if prev is not None else layers(add_sd6(build_circuits(spec, code, R)[basis]))
        y = layers(add_sd6(build_circuits(spec, code, R + 1)[basis]))
        prev = y
        assert len(y) - len(x) == D
        ok = [i for i in range(len(x) + 1) if y[:i] == x[:i] and y[i + D:] == x[i:]]
        contiguous &= bool(ok) and ok == list(range(min(ok), max(ok) + 1))
        lo_s.add(min(ok)); chi_s.add(max(ok) - D * R)
        blk = y[min(ok):min(ok) + D]
        nblk.add(sum(len(s.split()) - 1 for l_ in blk for s in l_.split("\n") if s.split() and s.split()[0] in ("M", "MX")))
good = contiguous and len(lo_s) == 1 and len(chi_s) == 1 and nblk == {nanc}
lo, c_hi = max(lo_s), max(chi_s)
V(good, f"[{a.circuit}] insertion (SD6, R = {Rs[0]}..{Rs[-1]}, both bases): circuit(R+1) = circuit(R) + one {D}-layer "
        f"block inserted at any x in [{lo}, {D}R{f"{c_hi:+d}" if c_hi else ""}] (contiguous, layer by layer), {nanc} measurements per block")
if a.separated:
    sep = []
    for R in (3, 8, 12):
        U = unroll(spec, code, R)
        st = {j: min(U.start[q] + D * j for q in U.start) for j in range(R)}
        en = {}
        for t, lst in U.meas.items():
            for q, ty, j in lst:
                en[j] = max(en.get(j, -1), t)
        sep.append(all(en[j] < st[j + 1] for j in range(R - 1)))
    Rp = dext + 1 + 3
    V(all(sep) and good and Rp <= rmax,
      f"[{a.circuit}] rounds separated in time (R = 3, 8, 12): {sep}; a fault-free round splits a minimal undetected "
      f"logical, so one of weight <= {dext + 1} spans <= {dext + 1} rounds and maps into a circuit with R' <= "
      f"{dext + 1} + 3 = {Rp} rounds; the lift covers R <= {rmax}")
else:
    # the longer circuit has R + 1 rounds: admissible insertion layers x <= D (R + 1) + (c_hi - D)
    Rp = {w: (lo + D - 1 + spans[w] + 2 * D - 2 - (c_hi - D)) // D for w in spans}
    V(Rp[dext + 1] <= rmax and good,
      f"[{a.circuit}] deletion: a minimal undetected logical of weight {dext} maps into a circuit with R' <= "
      f"{Rp[dext]} rounds, one of weight {dext + 1} into R' <= {Rp[dext + 1]} rounds; the lift covers R <= {rmax}")
V.exit()
