"""E-045 Part B: IBM decoder_setup.py model (E-037 reconstruction, search/experiments/e037/ibm_model.py), R noisy
cycles + T noiseless cycles: d_circ for EVERY R.  experimenter.

Notation.  A single fault f is a fault site of ibm_model (gate, fault qubits) placed in cycle c (0 <= c < R).  The
model's frame simulation is linear and the circuit is cycle^(R+T) with every cycle the same gate list, so the effect
of a fault depends only on the gates after it.  Let N = R + T (total cycles), K(f, N) = (detector set, logical set)
of f placed in cycle 0 of an N-cycle circuit; detector (check i, cycle t) has index t * n2 + i.

  Shift lemma (exact, by construction).  f in cycle c of the (R, T) model has column  shift_c K(f, N - c)
     (every detector index + c * n2), because the gate sequence after it is that of the (N - c)-cycle circuit after
     cycle-0 position of f, and all records before the fault are 0 (first-cycle detectors are raw records, later
     ones XOR with the previous cycle; both read 0 before the fault).
  End condition (E_T): K(f, N) does not depend on N for N >= 1 + T, for every cycle-0 fault site f.
     Checked EXACTLY (for all N) by eventual periodicity: the noiseless dynamics s_{t+1} = M s_t of the full frame
     state (all qubits) at cycle boundaries is a deterministic map on a finite set, so s_{t0+p} = s_{t0} implies
     periodicity from t0; we find t0, p for every f (vectorised), then require the per-cycle records m_t and the
     logical l_t = L . data(s_t) to be constant on one period.  Then detectors at cycles > t0 vanish and the column
     is the same for every N >= N_min(f) := max(last nonzero detector cycle + 1, first t from which l is constant).
     (E_T) holds iff max_f N_min(f) <= 1 + T.
  Consequence (inclusion + persistence): under (E_T) the column set of the (R, T) model is
     U_{c < R} shift_c K0 with K0 = {K(f) : f}, and it grows with R (R -> R + 1 inclusion); a fault set placed in
     cycles 0..R0-1 has the same columns in every R >= R0.
  Compression.  Let a = max_f (first detector cycle of K(f)), w = max_f (last - first detector cycle of K(f)).
     If F is an undetectable logical (XOR of detector sets empty, XOR of logical sets nonempty) of k columns in the
     (R, T) model, some connected component C of F (columns adjacent iff their detector sets meet; every column has
     a detector) is itself an undetectable logical with |C| <= k.  The detector-cycle intervals of C form a connected
     union of length <= sum of widths <= k w; the cycles c_j of chosen representations satisfy
     first_j - a <= c_j <= first_j, so max c - min c <= k w + a.  Shifting C down by min c gives an undetectable
     logical with the same logical set in cycles 0..k w + a, i.e. (by the consequence above) in the (R', T) model
     with R' = k w + a + 1.  So "no undetectable logical of weight <= k for R = 1..k w + a + 1" implies it for ALL R.

    uv run python -m search.experiments.e045.ibm_allR premises      # (E_T) for T = 0..3, a, w, shift lemma check
    uv run python -m search.experiments.e045.ibm_allR inclusion     # Crocker's R -> R+1 check, T = 0, 1, 2
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "search/experiments/e037"))
import ibm_model as im  # noqa: E402

OUT = ROOT / "results" / "E-045-crocker" / "partB"


def build_dem_T(code, typ, R, T, ibm_faithful=True):
    """ibm_model.build_dem with T trailing noiseless cycles instead of 2 (same code otherwise; T = 2 asserted equal)."""
    cyc = im.cycle(code)
    ops = [(c, r, gt) for c in range(R + T) for r, g in enumerate(cyc) for gt in g]
    fq, fpos, fbefore, fdesc = [], [], [], []
    for oi, (c, r, gt) in enumerate(ops):
        if c >= R:
            continue
        before, fl = im.faults_for(gt, typ)
        for qs in fl:
            fq.append(qs); fpos.append(oi); fbefore.append(before); fdesc.append((c, r, gt, qs))
    F = len(fq)
    inj_before, inj_after = {}, {}
    for f in range(F):
        (inj_before if fbefore[f] else inj_after).setdefault(fpos[f], []).append(f)
    state = np.zeros((code.Q, F), dtype=np.uint8)
    meas_rec = {}
    meas_kind = "MeasZ" if typ == "X" else "MeasX"
    reset_kind = ({"PrepZ"} if typ == "X" else {"PrepX"}) if ibm_faithful else {"PrepX", "PrepZ"}
    for oi, (c, r, gt) in enumerate(ops):
        for f in inj_before.get(oi, []):
            for q in fq[f]:
                state[q, f] ^= 1
        k = gt[0]
        if k == "CNOT":
            if typ == "X":
                state[gt[2]] ^= state[gt[1]]
            else:
                state[gt[1]] ^= state[gt[2]]
        elif k in reset_kind:
            state[gt[1]] = 0
        elif k == meas_kind:
            meas_rec[(gt[1], c)] = state[gt[1]].copy()
        for f in inj_after.get(oi, []):
            for q in fq[f]:
                state[q, f] ^= 1
    checks = code.Zq if typ == "X" else code.Xq
    N = R + T
    det = np.zeros((len(checks) * N, F), dtype=np.uint8)
    for c in range(N):
        for i, q in enumerate(checks):
            v = meas_rec[(q, c)].copy()
            if c:
                v ^= meas_rec[(q, c - 1)]
            det[c * len(checks) + i] = v
    data = code.Lq + code.Rq
    Lop = code.lz if typ == "X" else code.lx
    final = state[data]
    logi = (Lop.astype(np.int64) @ final.astype(np.int64)) % 2
    return det, logi, fdesc


def colset(det, logi, drop_empty=True):
    out = set()
    for f in range(det.shape[1]):
        d = tuple(np.nonzero(det[:, f])[0].tolist())
        o = tuple(np.nonzero(logi[:, f])[0].tolist())
        if drop_empty and not d and not o:
            continue
        out.add((d, o))
    return out


def cycle0_dynamics(code, typ, K=10, ibm_faithful=True):
    """All cycle-0 fault sites; returns per-cycle records m[t] (nchk x F), logical l[t] = L.data(s_t) for t = 1..K
    (s_t = frame at the START of cycle t = end of cycle t-1), the states s_t, and fault descriptors."""
    cyc = im.cycle(code)
    sites = []
    for r, g in enumerate(cyc):
        for gt in g:
            before, fl = im.faults_for(gt, typ)
            for qs in fl:
                sites.append((r, gt, qs, before))
    F = len(sites)
    state = np.zeros((code.Q, F), dtype=np.uint8)
    meas_kind = "MeasZ" if typ == "X" else "MeasX"
    reset_kind = ({"PrepZ"} if typ == "X" else {"PrepX"}) if ibm_faithful else {"PrepX", "PrepZ"}
    checks = code.Zq if typ == "X" else code.Xq
    cidx = {q: i for i, q in enumerate(checks)}
    pos = {}
    for f, (r, gt, qs, before) in enumerate(sites):
        pos.setdefault((r, gt, before), []).append(f)
    data = code.Lq + code.Rq
    Lop = (code.lz if typ == "X" else code.lx).astype(np.int64)
    recs, logs, states = [], [None], [None]
    for t in range(K):
        m = np.zeros((len(checks), F), dtype=np.uint8)
        for r, g in enumerate(cyc):
            for gt in g:
                if t == 0:
                    for f in pos.get((r, gt, True), []):
                        for q in sites[f][2]:
                            state[q, f] ^= 1
                k = gt[0]
                if k == "CNOT":
                    if typ == "X":
                        state[gt[2]] ^= state[gt[1]]
                    else:
                        state[gt[1]] ^= state[gt[2]]
                elif k in reset_kind:
                    state[gt[1]] = 0
                elif k == meas_kind:
                    m[cidx[gt[1]]] = state[gt[1]]
                if t == 0:
                    for f in pos.get((r, gt, False), []):
                        for q in sites[f][2]:
                            state[q, f] ^= 1
        recs.append(m)
        states.append(state.copy())
        logs.append(((Lop @ state[data].astype(np.int64)) % 2).astype(np.uint8))
    return dict(sites=sites, recs=recs, logs=logs, states=states, K=K, nchk=len(checks))


def end_condition(code, typ, K=10, ibm_faithful=True):
    dyn = cycle0_dynamics(code, typ, K, ibm_faithful)
    recs, logs, states = dyn["recs"], dyn["logs"], dyn["states"]
    F = len(dyn["sites"])
    # eventual periodicity of the whole state, per fault: smallest (t0, p) with s_{t0+p} == s_{t0}, t0 >= 1
    t0s, ps = np.full(F, -1), np.full(F, -1)
    for t0 in range(1, K + 1):
        for p in range(1, K + 1 - t0):
            eq = (states[t0] == states[t0 + p]).all(axis=0) & (t0s < 0)
            t0s[eq] = t0; ps[eq] = p
    assert (t0s > 0).all(), "periodicity not reached within K cycles; increase K"
    # records m_t for t >= t0 and logicals l_t for t >= t0 are periodic; require constant on one period
    nmin = np.zeros(F, dtype=int)
    first_det, last_det, width = np.zeros(F, int), np.zeros(F, int), np.zeros(F, int)
    for f in range(F):
        t0, p = int(t0s[f]), int(ps[f])
        # records in cycle t depend on s_t (start of cycle t) for t >= 1 (no fault after cycle 0)
        for t in range(t0, t0 + p):
            assert (recs[t][:, f] == recs[t0][:, f]).all(), ("records not constant on the period", f)
            assert (logs[t][:, f] == logs[t0][:, f]).all(), ("logical not constant on the period", f)
        dets = []
        for t in range(0, t0 + p + 1):
            v = recs[t][:, f] ^ (recs[t - 1][:, f] if t else 0)
            if v.any():
                dets.append(t)
        assert all(t <= t0 for t in dets)
        last = max(dets) if dets else -1
        # first N from which l_N is constant: l_N = logs[N]
        ln = t0
        while ln > 1 and (logs[ln - 1][:, f] == logs[t0][:, f]).all():
            ln -= 1
        nmin[f] = max(last + 1, ln, 1)
        first_det[f] = min(dets) if dets else -1
        last_det[f] = last
        width[f] = (last - min(dets)) if dets else -1
    return dict(F=F, t0_max=int(t0s.max()), period_max=int(ps.max()), period_hist=np.bincount(ps).tolist(),
                Nmin_max=int(nmin.max()), Nmin_hist=np.bincount(nmin).tolist(), a=int(first_det.max()),
                w=int(width.max()), no_detector_sites=int((first_det < 0).sum()),
                nodet_flip=int(sum(1 for f in range(F) if first_det[f] < 0 and logs[t0s[f]][:, f].any()))), dyn, nmin


def K0_columns(dyn, N):
    """columns of all cycle-0 sites in an N-cycle circuit, from the dynamics (detector index t * nchk + i)"""
    recs, logs = dyn["recs"], dyn["logs"]
    nchk = dyn["nchk"]
    out = []
    for f in range(len(dyn["sites"])):
        d = []
        for t in range(N):
            v = recs[t][:, f] ^ (recs[t - 1][:, f] if t else 0)
            d += [t * nchk + int(i) for i in np.nonzero(v)[0]]
        out.append((tuple(d), tuple(np.nonzero(logs[N][:, f])[0].tolist())))
    return out


def premises():
    OUT.mkdir(parents=True, exist_ok=True)
    res = []
    for name in ("gross", "bb108"):
        code = im.Code(name)
        for typ in ("X", "Z"):
            for faithful in (True, False):
                info, dyn, nmin = end_condition(code, typ, K=16, ibm_faithful=faithful)
                rec = dict(code=name, typ=typ, basis="Z" if typ == "X" else "X", faithful=faithful, **info)
                for T in range(0, 4):
                    rec[f"E_T{T}"] = info["Nmin_max"] <= 1 + T
                # shift lemma + inclusion structure, checked on full builds: model(R, T=2) column set ==
                # U_c shift_c K(f, R + 2 - c);  and == ibm_model.build_dem (E-037, certified) for T = 2
                if faithful:
                    nchk = dyn["nchk"]
                    for R in (1, 2, 5, 12) if name == "gross" else (1, 2, 5, 10):
                        det, logi, _ = build_dem_T(code, typ, R, 2)
                        S = colset(det, logi)
                        U = set()
                        for c in range(R):
                            for d, o in K0_columns(dyn, R + 2 - c):
                                if d or o:
                                    U.add((tuple(x + c * nchk for x in d), o))
                        e37 = im.build_dem(code, typ, R)
                        S37 = set(zip(map(tuple, e37["D"]), map(tuple, e37["L"])))
                        rec[f"shift_union_eq_R{R}"] = (S == U)
                        rec[f"eq_E037_R{R}"] = (S == S37)
                        rec[f"ncols_R{R}"] = len(S)
                    k = 9 if name == "gross" else 7
                    rec["k"] = k
                    rec["R_prime"] = k * info["w"] + info["a"] + 1
                print(json.dumps(rec), flush=True)
                res.append(rec)
    (OUT / "premises.json").write_text(json.dumps(res, indent=1))


def inclusion():
    """Crocker's check: column set of the (R, T) model contained in that of the (R + 1, T) model."""
    OUT.mkdir(parents=True, exist_ok=True)
    res = []
    Rs = list(range(1, 19))
    for name in ("gross", "bb108"):
        code = im.Code(name)
        for typ in ("X", "Z"):
            for T in (0, 1, 2):
                prev = None
                row = dict(code=name, typ=typ, T=T, incl={}, missing={})
                for R in Rs + [19]:
                    det, logi, _ = build_dem_T(code, typ, R, T)
                    S = colset(det, logi)
                    if prev is not None and prev[0] + 1 == R:
                        miss = prev[1] - S
                        row["incl"][prev[0]] = not miss
                        row["missing"][prev[0]] = len(miss)
                    prev = (R, S)
                print(json.dumps(row), flush=True)
                res.append(row)
    (OUT / "inclusion.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    {"premises": premises, "inclusion": inclusion}[sys.argv[1]]()
