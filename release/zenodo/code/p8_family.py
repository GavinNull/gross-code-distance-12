"""SM S16, "Completeness of the family encoding" and "At P = 8 all 944 legal deterministic circuits of the family were
also checked directly".

Family (colour-symmetric, period 8, orders in the class of Fig. 12): each (type, colour) class picks one of the 8
orders {Fig. 12 order, reversed} x {swap positions 1-2} x {swap positions 5-6} (applied position-wise to every check
of the class) and a start s in Z_8; reset at s, CNOT k (k = 1..6) at s + k, measurement at s + 7 (mod 8).
Legal: no data qubit in two CNOTs at one time mod 8.  Deterministic: for every overlapping X/Z check pair and every
instance offset k, #{shared qubit q : floor((T_X(q) - T_Z(q)) / 8) < k} is even.  (The SAT encodings use the
equivalent per-pair condition; stim's DEM construction is the final arbiter here.)  Class X0 starts at 0.

data/circuits/p8_colour_symmetric_944.json.gz lists the circuits compactly: for each circuit the (variant, start) of
the six classes X0 X1 X2 Z0 Z1 Z2 (variant bit 4 = reverse, 1 = swap positions 1-2, 2 = swap 5-6, applied in the
order swap, swap, then reversal of the Fig. 12 order; colour = (a + b) mod 3 of check 6a + b).

    python code/p8_family.py enumerate     # independent backtracking enumeration == the 944 listed circuits
    python code/p8_family.py check         # every listed circuit: legal, deterministic, extended code = Fig. 12's
    python code/p8_family.py encoding      # all models of the primary SAT encoding at P = 8 (no logical nogoods)
                                           # are exactly the 944 listed circuits (completeness of the encoding)
"""
import gzip
import json
import sys
import time

import numpy as np

from common_cli import Verdict, circuit, load_code
from gross12 import ext as GE
from gross12.paths import CIRCUITS
from gross12.schedule import Schedule, CheckTiming, build_circuits, validate_schedule

P = 8
FILE = CIRCUITS / "p8_colour_symmetric_944.json.gz"
f12 = circuit("fig12")
xo, zo = f12.orders()
col = lambda i: (i // 6 + i % 6) % 3  # noqa: E731
checks = [("X", i, xo[i], col(i)) for i in range(72)] + [("Z", i, zo[i], col(i)) for i in range(72)]
classes = [(t, c) for t in "XZ" for c in range(3)]
cls_of = [classes.index((t, c)) for t, _, _, c in checks]
OPTS = [(v, s) for v in range(8) for s in range(P)]


def variant(o, v):
    o = list(o)
    if v & 1:
        o[0], o[1] = o[1], o[0]
    if v & 2:
        o[4], o[5] = o[5], o[4]
    if v & 4:
        o = o[::-1]
    return o


def times(ci, opt):
    v, s = opt
    return {q: s + k + 1 for k, q in enumerate(variant(checks[ci][2], v))}


def expand(entry):
    """entry = [[v, s] x 6 classes] -> Schedule"""
    xs, zs = [], []
    for ci, (t, i, o, c) in enumerate(checks):
        v, s = entry[cls_of[ci]]
        T = times(ci, (v, s))
        ct = CheckTiming(s % P, (s + 7) % P, tuple(sorted((q, T[q] % P) for q in T)))
        (xs if t == "X" else zs).append(ct)
    return Schedule(P, tuple(xs), tuple(zs))


def canon(spec):
    return json.dumps(spec.canonical().to_dict(), sort_keys=True)


def enumerate_family():
    sup = [set(ch[2]) for ch in checks]
    pairs = [(a, b) for a in range(144) for b in range(a + 1, 144) if sup[a] & sup[b]]

    def ok_pair(a, b, Ta, Tb):
        sh = sup[a] & sup[b]
        if any((Ta[q] - Tb[q]) % P == 0 for q in sh):
            return False
        if checks[a][0] != checks[b][0]:
            Tx, Tz = (Ta, Tb) if checks[a][0] == "X" else (Tb, Ta)
            fl = [(Tx[q] - Tz[q]) // P for q in sh]
            for k in range(min(fl), max(fl) + 2):
                if sum(f < k for f in fl) % 2:
                    return False
        return True

    pc = {}
    for a, b in pairs:
        pc.setdefault((cls_of[a], cls_of[b]), []).append((a, b))
    comp = {}
    for (ca, cb), lst in pc.items():
        tab = np.zeros((64, 64), bool)
        for i, oa in enumerate(OPTS):
            Ta = {a: times(a, oa) for a, _ in lst}
            for j, ob in enumerate(OPTS):
                if ca == cb and i != j:
                    continue
                Tb = {b: times(b, ob) for _, b in lst}
                tab[i, j] = all(ok_pair(a, b, Ta[a], Tb[b]) for a, b in lst)
        comp[(ca, cb)] = tab

    def compat(ca, i, cb, j):
        if (ca, cb) in comp:
            return comp[(ca, cb)][i, j]
        if (cb, ca) in comp:
            return comp[(cb, ca)][j, i]
        return True
    sols = []

    def bt(k, ch):
        if k == 6:
            sols.append([list(OPTS[i]) for i in ch])
            return
        for i in range(64):
            if k == 0 and OPTS[i][1] != 0:
                continue
            if not compat(k, i, k, i):
                continue
            if all(compat(j, ch[j], k, i) for j in range(k)):
                ch.append(i); bt(k + 1, ch); ch.pop()
    bt(0, [])
    return sols


def load():
    return json.load(gzip.open(FILE))["circuits"]


if __name__ == "__main__":
    V = Verdict()
    code = load_code()
    listed = load()
    if sys.argv[1] == "enumerate":
        t0 = time.time()
        sols = enumerate_family()
        mine = {canon(expand(e)) for e in sols}
        theirs = {canon(expand(e)) for e in listed}
        V(len(sols) == len(mine) == 944 and mine == theirs,
          f"P = 8 colour-symmetric family: backtracking enumeration gives {len(sols)} circuits ({len(mine)} distinct "
          f"up to global time shift), equal to the {len(theirs)} listed ({time.time() - t0:.0f} s)")
    elif sys.argv[1] == "encoding":
        from sat.common import Family, colour, kernel, parse_orders, table
        from sat.enc_primary import Enc
        X = "A1A2A3B3B1B2,A1A2A3B1B2B3,A1A3A2B3B1B2"; Z = "A1A3A2B3B1B2,A1A2A3B1B2B3,A1A2A3B3B1B2"
        orders = {"X": parse_orders(X), "Z": parse_orders(Z)}
        F = Family(kernel((3, 1, 1)))
        ccol = [colour((3, 1, 1), F.reps[k]) for k in range(F.nc)]
        M = Enc(F, orders, ccol, P, 0)
        T = table()
        models = set()
        while M.S.solve():
            ms = set(l for l in M.S.get_model() if l > 0)
            t = {i: v for (i, v), var in M.x.items() if var in ms}
            st = {u: w for (u, w), var in M.s.items() if var in ms}
            d = {"format": "qec-schedule/v1", "period": P, "x_checks": [], "z_checks": []}
            for ty, key in (("X", "x_checks"), ("Z", "z_checks")):
                for i in range(72):
                    u = (ty, F.cls[i])
                    d[key].append({"prep": st[u] % P, "meas": (st[u] + P - 1) % P,
                                   "cnots": [[int(T[ty][i][l]), t[F.idx[(ty, F.cls[i], l)]] % P] for l in range(6)]})
            from gross12.schedule import parse_schedule
            models.add(canon(parse_schedule(d)))
            M.S.add_clause([-M.x[(i, v)] for i, v in t.items()])
        theirs = {canon(expand(e)) for e in listed}
        V(models == theirs, f"primary SAT encoding at P = 8 without logical nogoods: {len(models)} models, equal to the "
                            f"{len(theirs)} listed circuits")
    else:
        fk = {b: set(GE.ext_keys_from_file(code, b)) for b in "ZX"}
        n = [0, 0, 0]
        for e in listed:
            sp = expand(e)
            if validate_schedule(sp, code):
                continue
            n[0] += 1
            cs = build_circuits(sp.canonical(), code, 1)
            try:
                for c in cs.values():
                    c.detector_error_model()
                n[1] += 1
            except ValueError:
                continue
            n[2] += all(set(GE.ext_columns(code, b, sp)[0]) == fk[b] for b in "ZX")
        V(n == [944, 944, 944], f"listed circuits: legal {n[0]}, deterministic {n[1]}, extended code = Fig. 12's {n[2]} "
                                f"(of {len(listed)})")
    V.exit()
