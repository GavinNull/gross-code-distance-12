"""Own extended code of a schedule (no project code): for a memory basis b, the errors that matter are X (b = Z) or
Z (b = X); H = HZ, L = LZ (b = Z) or H = HX, L = LX (b = X).  Columns = residual data errors of single faults:
every data qubit, and every proper suffix (in CNOT-time order inside one instance) of the OTHER-type checks
(X checks for b = Z: X on the |+> ancilla spreads to the data of its remaining CNOTs; Z checks for b = X).
Columns are merged by key (H e, L e) (= residual modulo stabilisers) and zero keys dropped.
Translation group: 72 translations act on residuals; the column set must be invariant (asserted).
"""
import sys
sys.path.insert(0, "research/audits/2026-10-22-E-032-scripts")
import numpy as np
from alib32 import *


def ext_code(spec, basis, Lover=None):
    HX, HZ, LX, LZ = code()
    if basis == "Z":
        H, Lg, hook_checks = HZ, (LZ if Lover is None else Lover), spec["x_checks"]
    else:
        H, Lg, hook_checks = HX, (LX if Lover is None else Lover), spec["z_checks"]
    D = spec["period"]
    res = []   # residual vectors
    for c in range(N):
        e = np.zeros(N, np.uint8); e[c] = 1; res.append(e)
    for c in hook_checks:
        order = [a for _, a in sorted(((t - c["prep"]) % D, a) for a, t in c["cnots"])]
        for k in range(1, 6):          # fault after the k-th CNOT: suffix order[k:]
            e = np.zeros(N, np.uint8); e[order[k:]] = 1; res.append(e)
    def key(e):
        return (H.astype(int) @ e % 2).astype(np.uint8).tobytes() + (Lg.astype(int) @ e % 2).astype(np.uint8).tobytes()
    cols, rep_res, kidx = [], [], {}
    zero = bytes(H.shape[0] + Lg.shape[0])
    for e in res:
        k = key(e)
        if k == zero or k in kidx:
            continue
        kidx[k] = len(cols); cols.append(k); rep_res.append(e)
    # translation action on columns
    perms = []
    for a in range(L_):
        for b in range(M_):
            P, _ = translation(a, b)
            pm = []
            for e in rep_res:
                f = np.zeros(N, np.uint8); f[P[np.nonzero(e)[0]]] = 1
                k = key(f)
                assert k in kidx, "column set not translation invariant"
                pm.append(kidx[k])
            assert sorted(pm) == list(range(len(cols)))
            perms.append(pm)
    # orbits
    orb = [-1] * len(cols); reps = []
    for j in range(len(cols)):
        if orb[j] < 0:
            o = len(reps)
            members = sorted({pm[j] for pm in perms})
            for m in members:
                orb[m] = o
            reps.append(max(members))      # rep = largest index in the orbit (differs from the project's choice)
    nH = H.shape[0]
    Hb = [np.frombuffer(k[:nH], np.uint8) for k in cols]
    Lb = [np.frombuffer(k[nH:], np.uint8) for k in cols]
    return dict(cols=cols, res=rep_res, perms=perms, orb=orb, reps=reps, nH=nH, Hb=Hb, Lb=Lb, H=H, L=Lg)


def write_instance(E, path):
    with open(path, "w") as f:
        f.write(f"{len(E['cols'])} {E['nH']}\n")
        for h, l in zip(E["Hb"], E["Lb"]):
            hs, ls = np.nonzero(h)[0], np.nonzero(l)[0]
            f.write(f"{len(hs)} {' '.join(map(str, hs))} {len(ls)} {' '.join(map(str, ls))}\n")
        f.write(f"{len(E['reps'])}\n{' '.join(map(str, E['orb']))}\n{' '.join(map(str, E['reps']))}\n")


def expand(E, sols):
    out = set()
    for S in sols:
        for pm in E["perms"]:
            out.add(frozenset(pm[j] for j in S))
    return out


def verify(E, S):
    h = np.zeros(E["nH"], np.uint8); l = np.zeros(len(E["Lb"][0]), np.uint8)
    for j in S:
        h ^= E["Hb"][j]; l ^= E["Lb"][j]
    return not h.any() and l.any()
