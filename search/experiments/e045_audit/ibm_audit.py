"""E-045 audit, Part B: IBM decoder_setup.py model with R noisy + T noiseless cycles.  auditor.

Own code.  Uses only the E-037 AUDIT's independent pieces (search/experiments/e037_audit/mydem.py: BB code, the
decoder_setup.py cycle, fault_sites), never search/experiments/e037 or e045.

  premises   for every cycle-0 fault site f: noiseless frame states s_t (all qubits, start of cycle t, t = 1..K) ->
             exact eventual period (t0, p) with s_{t0+p} = s_{t0}; records m_t and logical l_t = L.data(s_t) must be
             constant on the period (else the column would oscillate with N).  N_min(f) = least N0 with
             K(f, N) = K(f, N0) for all N >= N0  (K(f, N) = (detectors in cycles < N, l_N)).  Reports max N_min,
             a = max first detector cycle, w = max (last - first) detector cycle, sites without detector, and
             the histogram of N_min by fault kind.  Both frame conventions (faithful: no clear at PrepX for X frame /
             PrepZ for Z frame; reset_all).
  structure  direct builds: Cols(R, T) == U_{c<R} shift_c Cols0  (Cols0 = cycle-0 columns at N = 1 + T) for T = 2,
             R = 1..20, and Cols(R, 2) == mydem.ibm_columns(R) (the E-037 audit builder) for R in a list.
  inclusion  Cols(R, T) subset of Cols(R+1, T)?  R = 1..18, T = 0, 1, 2; number of missing columns and which fault
             kinds they come from.

  uv run python -m search.experiments.e045_audit.ibm_audit premises|structure|inclusion
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "search/experiments/e037_audit"))
import mydem  # noqa: E402

OUT = ROOT / "results/E-045-audit/partB"


def sim(code, typ, R, T, reset_all=False, only_cycle0=False):
    """bit-parallel frame simulation of R + T cycles; faults in cycles < R (or only cycle 0).
    Returns D (ndet x F 0/1), Lm (k x F), sites, per-cycle-boundary states (list of Q x F) if only_cycle0."""
    cyc = code.cycle(with_round=True)
    N = R + T
    sites = []
    for c in range(N):
        if c >= R or (only_cycle0 and c > 0):
            continue
        for gi, (rnd, g) in enumerate(cyc):
            for before, qs in mydem.fault_sites(g, typ):
                sites.append((c, gi, before, qs, g[0], rnd))
    F = len(sites)
    st = np.zeros((code.Q, F), dtype=np.uint8)
    bef, aft = collections.defaultdict(list), collections.defaultdict(list)
    for f, (c, gi, b, qs, _, _) in enumerate(sites):
        (bef if b else aft)[(c, gi)].append((f, qs))
    measg = "MeasZ" if typ == "X" else "MeasX"
    resets = {"PrepX", "PrepZ"} if reset_all else ({"PrepZ"} if typ == "X" else {"PrepX"})
    chk = code.zc if typ == "X" else code.xc
    ci = {q: i for i, q in enumerate(chk)}
    rec = np.zeros((N, len(chk), F), dtype=np.uint8)
    states = [None]
    for c in range(N):
        for gi, (_, g) in enumerate(cyc):
            for f, qs in bef.get((c, gi), ()):
                for q in qs:
                    st[q, f] ^= 1
            k = g[0]
            if k == "CNOT":
                if typ == "X":
                    st[g[2]] ^= st[g[1]]
                else:
                    st[g[1]] ^= st[g[2]]
            elif k in resets:
                st[g[1]] = 0
            elif k == measg:
                rec[c, ci[g[1]]] = st[g[1]]
            for f, qs in aft.get((c, gi), ()):
                for q in qs:
                    st[q, f] ^= 1
        if only_cycle0:
            states.append(st.copy())
    det = rec.copy()
    det[1:] ^= rec[:-1]
    D = det.reshape(N * len(chk), F)
    Lop = (code.lz if typ == "X" else code.lx).astype(np.int64)
    data = code.dl + code.dr
    Lm = ((Lop @ st[data].astype(np.int64)) % 2).astype(np.uint8)
    return dict(D=D, L=Lm, sites=sites, rec=rec, states=states, nchk=len(chk))


def colset(D, L):
    out = set()
    for f in range(D.shape[1]):
        d = tuple(np.flatnonzero(D[:, f]).tolist()); o = tuple(np.flatnonzero(L[:, f]).tolist())
        if d or o:
            out.add((d, o))
    return out


def premises_one(code, typ, reset_all, K=14):
    S = sim(code, typ, 1, K - 1, reset_all, only_cycle0=True)   # N = K cycles, faults in cycle 0 only
    rec, states, nchk = S["rec"], S["states"], S["nchk"]
    F = len(S["sites"])
    Lop = (code.lz if typ == "X" else code.lx).astype(np.int64)
    data = code.dl + code.dr
    l = [None] + [((Lop @ states[t][data].astype(np.int64)) % 2).astype(np.uint8) for t in range(1, K + 1)]
    # states[t] = frame at end of cycle t-1 = start of cycle t, t = 1..K
    t0 = np.full(F, -1); per = np.full(F, -1)
    for a in range(1, K + 1):
        for p in range(1, K + 1 - a):
            m = (states[a] == states[a + p]).all(axis=0) & (t0 < 0)
            t0[m] = a; per[m] = p
    assert (t0 > 0).all()
    nmin = np.zeros(F, int); first = np.full(F, -1); last = np.full(F, -1)
    for f in range(F):
        a, p = int(t0[f]), int(per[f])
        assert a + p < K, "need larger K"
        # records m_t (t >= 1) are functions of s_t; on t >= a they are p-periodic; demand constant on one period
        for t in range(a, a + p):
            assert (rec[t, :, f] == rec[a, :, f]).all(), ("records oscillate", f)
            assert (l[t][:, f] == l[a][:, f]).all(), ("logical oscillates", f)
        dts = [t for t in range(0, a + 1) if (rec[t, :, f] ^ (rec[t - 1, :, f] if t else 0)).any()]
        # for t > a: m_t = m_a, so detector 0
        lastd = max(dts) if dts else -1
        # l_N constant for N >= a (periodic + constant on a period); walk down
        n0 = a
        while n0 > 1 and (l[n0 - 1][:, f] == l[a][:, f]).all():
            n0 -= 1
        nmin[f] = max(lastd + 1, n0, 1)
        if dts:
            first[f] = min(dts); last[f] = lastd
    kinds = collections.Counter()
    for f in range(F):
        c, gi, b, qs, g, rnd = S["sites"][f]
        kinds[(g, rnd, len(qs), int(nmin[f]))] += 1
    worst = sorted({(g, rnd, nq) for (g, rnd, nq, n), v in kinds.items() if n == nmin.max()})
    return dict(F=F, t0_max=int(t0.max()), period_hist=dict(collections.Counter(per.tolist())), Nmin_max=int(nmin.max()),
                Nmin_hist=dict(collections.Counter(nmin.tolist())), a=int(first.max()), w=int((last - first)[first >= 0].max()),
                no_det_sites=int((first < 0).sum()),
                no_det_flip=int(sum(1 for f in range(F) if first[f] < 0 and l[K][:, f].any())),
                worst_kinds=[list(x) for x in worst],
                E={T: bool(nmin.max() <= 1 + T) for T in range(4)})


def premises():
    OUT.mkdir(parents=True, exist_ok=True)
    res = []
    for name in ("gross", "bb108"):
        code = mydem.BB(name)
        for typ in ("X", "Z"):
            for ra in (False, True):
                r = dict(code=name, typ=typ, memory_basis="Z" if typ == "X" else "X", reset_all=ra,
                         **premises_one(code, typ, ra))
                k = 9 if name == "gross" else 7
                r["Rprime"] = k * r["w"] + r["a"] + 1
                print(json.dumps(r), flush=True)
                res.append(r)
    (OUT / "premises.json").write_text(json.dumps(res, indent=1))


def structure():
    OUT.mkdir(parents=True, exist_ok=True)
    res = []
    for name in ("gross", "bb108"):
        code = mydem.BB(name)
        for typ in ("X", "Z"):
            T = 2
            S0 = sim(code, typ, 1, T)
            nchk = S0["nchk"]
            K0 = colset(S0["D"], S0["L"])
            ok_union, ok_mydem = {}, {}
            for R in range(1, 21):
                S = sim(code, typ, R, T)
                C = colset(S["D"], S["L"])
                U = {(tuple(x + c * nchk for x in d), o) for c in range(R) for d, o in K0}
                ok_union[R] = C == U
                if R in (1, 2, 3, 5, 10, 12):
                    M = mydem.ibm_columns(name, typ, R)
                    ok_mydem[R] = C == set(zip(map(tuple, M["D"]), map(tuple, M["L"])))
            r = dict(code=name, typ=typ, T=T, union_eq=ok_union, mydem_eq=ok_mydem)
            print(json.dumps(r), flush=True)
            res.append(r)
    (OUT / "structure.json").write_text(json.dumps(res, indent=1))


def inclusion():
    OUT.mkdir(parents=True, exist_ok=True)
    res = []
    for name in ("gross", "bb108"):
        code = mydem.BB(name)
        for typ in ("X", "Z"):
            for T in (0, 1, 2):
                prev = None
                row = dict(code=name, typ=typ, T=T, missing={}, kinds={})
                for R in range(1, 20):
                    S = sim(code, typ, R, T)
                    cols = collections.defaultdict(list)
                    for f in range(S["D"].shape[1]):
                        d = tuple(np.flatnonzero(S["D"][:, f]).tolist()); o = tuple(np.flatnonzero(S["L"][:, f]).tolist())
                        if d or o:
                            cols[(d, o)].append(S["sites"][f])
                    if prev is not None:
                        miss = set(prev) - set(cols)
                        row["missing"][R - 1] = len(miss)
                        if miss and R - 1 in (1, 5, 12):
                            kk = collections.Counter()
                            for m in miss:
                                for (c, gi, b, qs, g, rnd) in prev[m]:
                                    kk[f"{g}@r{rnd}/c{c - (R - 1)}"] += 1
                            row["kinds"][R - 1] = dict(kk.most_common(6))
                    prev = cols
                print(json.dumps(row), flush=True)
                res.append(row)
    (OUT / "inclusion.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    {"premises": premises, "structure": structure, "inclusion": inclusion}[sys.argv[1]]()
