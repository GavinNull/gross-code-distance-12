"""E-019 stage 3: detectors, sd6 fault signatures, structure checks, Prop. 1 fold condition, single-round DFS
instances -- for any family member. Port of the E-017 auditor's c2_instance.py + c3_rounds.py + c4_sparse.py
(research/audits/2026-10-08-E-017-scripts/) to general (l, m, A, B, hom, variant); logic unchanged.

usage: uv run python -m search.experiments.e019.instance <key> <basis Z|X> [T=4]

Memory basis B; only same-basis records (CSS relaxation; valid for lower bounds). Detectors derived from the GF(2)
kernel of noiseless samples (time-local blocks D_t on rounds t-1, t; final block with the readout). Faults: every
Pauli component of every sd6 location, projected. Checks: stim DEM term set == my signatures; locality; per-round
instance equivalence (time shift + translation); fold condition (general and local, auditor's basis-free form);
translation symmetry (K = ker f) on the round-1 instance; sparse (record-singleton) round-1 instance for adfs.
"""
from __future__ import annotations

import json
import pickle
import sys

import numpy as np
import stim

from search.experiments.e019.common import HOMS, get_code, logicals, memory, nullspace, rank, rref, spec

OUT = "/Users/ephemeral/Desktop/qec-ai-search/results/E-019-morphing-family/inst"
SEED = 12345


def build(key, basis, T=4, stim_check=True):
    name, hom, variant = key.split("_")
    code = get_code(name)
    N = code.N
    gates, meas, _, _ = spec(code, hom, variant)
    C = memory(code, gates, meas, T, basis)
    mop = "M" if basis == "Z" else "MX"
    HX, HZ = code.checks()
    tag = f"{key}_{basis}_T{T}"
    info = dict(key=key, basis=basis, T=T)

    # ------------------------------------------------------------ records
    recs = C.recs
    same = [i for i, (tg, op, q) in enumerate(recs) if op == mop]
    grp = {}
    for i in same:
        (r, kind), op, q = recs[i]
        k = "F" if (r == T and q < N) else r
        grp.setdefault(k, []).append(i)
    for k in grp:
        grp[k] = sorted(grp[k])
    assert all(len(grp[r]) == N // 2 for r in range(1, T + 1)) and len(grp["F"]) == N

    LOG = logicals(HX, HZ) if basis == "Z" else logicals(HZ, HX)
    kq = len(LOG)
    pchar = "X" if basis == "Z" else "Z"
    li_mid = [i for i, (ops, tg) in enumerate(C.layers) if tg == (1, "Fd2")][0]
    rand = stim.Circuit()
    for v in LOG:
        rand.append("E", [stim.target_x(q) if pchar == "X" else stim.target_z(q) for q in np.nonzero(v)[0]], 0.5)
    c_plain = C.stim()
    c_rand = C.stim({li_mid: rand})
    cols_all = same
    colpos = {c: i for i, c in enumerate(cols_all)}
    shots = max(1600, 3 * len(cols_all))

    def sample_kernel(circ, cols):
        s = circ.compile_sampler(seed=SEED).sample(shots).astype(np.uint8)
        d = s ^ s[0]
        return nullspace(d[:, cols])

    def embed(vecs, sub):
        out = np.zeros((len(vecs), len(cols_all)), np.uint8)
        for j, c in enumerate(sub):
            out[:, colpos[c]] = vecs[:, j]
        return out

    Kdet = sample_kernel(c_rand, cols_all)
    Kall = sample_kernel(c_plain, cols_all)

    def rand_before_round(r):
        if r <= 1:
            return c_rand
        li = [i for i, (ops, tg) in enumerate(C.layers) if tg == (r - 1, "M")][0]
        ini = stim.Circuit()
        ini.append("X_ERROR" if basis == "Z" else "Z_ERROR", list(range(2 * N)), 0.5)
        return C.stim({li: ini, li_mid: rand} if li_mid > li else {li: ini})

    blocks = {1: embed(sample_kernel(c_rand, grp[1]), grp[1])}
    for t in range(2, T + 1):
        sub = grp[t - 1] + grp[t]
        blocks[t] = embed(sample_kernel(rand_before_round(t - 1), sub), sub)
    if T >= 2:
        keep = []
        rk0 = rank(blocks[1])
        for v in blocks[2]:
            if rank(np.vstack([blocks[1]] + keep + [v[None]])) > rk0 + len(keep):
                keep.append(v[None])
        blocks[2] = np.vstack(keep)
    sub = grp[T] + grp["F"]
    fin = embed(sample_kernel(rand_before_round(T), sub), sub)
    base = blocks[T]
    rk = rank(base)
    extra = []
    for v in fin:
        if rank(np.vstack([base] + extra + [v[None]])) > rk + len(extra):
            extra.append(v[None])
    blocks[T + 1] = np.vstack(extra) if extra else np.zeros((0, len(cols_all)), np.uint8)

    def sparsify(B, first):
        if len(B) == 0:
            return B
        fs = set(colpos[c] for c in first)
        order_ = [colpos[c] for c in first] + [i for i in range(len(cols_all)) if i not in fs]
        Rm, _ = rref(B[:, order_])
        out = np.zeros_like(Rm)
        out[:, order_] = Rm
        return out

    for t in range(2, T + 1):
        blocks[t] = sparsify(blocks[t], grp[t])
    blocks[T + 1] = sparsify(blocks[T + 1], grp[T])
    Dall = np.vstack([blocks[t] for t in range(1, T + 2)])
    info.update(k=kq, dim_Kdet=len(Kdet), dim_Kall=len(Kall), block_dims={t: int(len(blocks[t])) for t in blocks},
                blocks_span_Kdet=bool(rank(np.vstack([Dall, Kdet])) == rank(Dall) == len(Kdet)))
    subL = grp.get(T - 1, []) + grp[T] + grp["F"]
    Klate = embed(sample_kernel(c_plain, subL), subL)
    obs = []
    cur = Kdet.copy()
    rk = rank(cur)
    for v in list(Klate) + list(Kall):
        t2 = np.vstack([cur, v])
        if rank(t2) > rk:
            obs.append(v)
            cur = t2
            rk += 1
    OBS = np.array(obs)
    info["n_obs"] = len(OBS)
    assert len(OBS) == kq, (len(OBS), kq)
    assert info["blocks_span_Kdet"]
    ann = stim.Circuit()
    for t in sorted(blocks):
        for v in blocks[t]:
            ann.append("DETECTOR", [stim.target_rec(cols_all[j] - C.nrec) for j in np.nonzero(v)[0]])
    for k, v in enumerate(OBS):
        ann.append("OBSERVABLE_INCLUDE", [stim.target_rec(cols_all[j] - C.nrec) for j in np.nonzero(v)[0]], k)
    open(f"{OUT}/ann_{tag}.stim", "w").write(str(ann))

    # ------------------------------------------------------------ faults
    touched = []
    for ops, tg in C.layers:
        s = set()
        for op, ts in ops:
            if op == "CX":
                for a, b in ts:
                    s.add(a)
                    s.add(b)
            else:
                s.update(ts)
        touched.append(s)

    def has(pp):
        return (pp in "XY") if basis == "Z" else (pp in "ZY")
    faults = []
    for li, (ops, tg) in enumerate(C.layers):
        r = tg[0]
        for op, ts in ops:
            if op == "CX":
                for (c, t) in ts:
                    for pc in "IXYZ":
                        for pt in "IXYZ":
                            if pc == pt == "I":
                                continue
                            comp = tuple((li + 1, q) for q, pp in ((c, pc), (t, pt)) if has(pp))
                            faults.append((r, li, "cx", (c, t), pc + pt, comp))
            elif op in ("R", "RX"):
                for q in ts:
                    pp = "X" if op == "R" else "Z"
                    faults.append((r, li, "reset", (q,), pp, ((li + 1, q),) if has(pp) else ()))
            elif op in ("M", "MX"):
                for q in ts:
                    pp = "X" if op == "M" else "Z"
                    faults.append((r, li, "meas", (q,), pp, ((li, q),) if has(pp) else ()))
        for q in range(2 * N):
            if q not in touched[li]:
                for pp in "XYZ":
                    faults.append((r, li, "idle", (q,), pp, ((li + 1, q),) if has(pp) else ()))

    points = sorted(set(cp for f in faults for cp in f[5]))
    pidx = {p: i for i, p in enumerate(points)}
    F = np.zeros((len(points), 2 * N), np.uint8)
    flips = np.zeros((len(points), len(cols_all)), np.uint8)
    by_layer = {}
    for i, (li, q) in enumerate(points):
        by_layer.setdefault(li, []).append((i, q))
    rec_ptr = 0
    for li, (ops, tg) in enumerate(C.layers):
        for (i, q) in by_layer.get(li, []):
            F[i, q] ^= 1
        for op, ts in ops:
            if op == "CX":
                cs = np.array([a for a, b in ts])
                tt = np.array([b for a, b in ts])
                if basis == "Z":
                    F[:, tt] ^= F[:, cs]
                else:
                    F[:, cs] ^= F[:, tt]
            elif op in ("M", "MX"):
                for q in ts:
                    if op == mop:
                        flips[:, colpos[rec_ptr]] = F[:, q]
                    rec_ptr += 1
            elif op in ("R", "RX"):
                F[:, list(ts)] = 0
    assert rec_ptr == C.nrec
    Hb = {t: (flips.astype(np.int64) @ blocks[t].T.astype(np.int64)) % 2 for t in blocks}
    Lb = (flips.astype(np.int64) @ OBS.T.astype(np.int64)) % 2

    def fsig(f):
        h = {t: np.zeros(len(blocks[t]), np.uint8) for t in blocks}
        lv = np.zeros(kq, np.uint8)
        for cp in f[5]:
            i = pidx[cp]
            for t in blocks:
                h[t] ^= Hb[t][i].astype(np.uint8)
            lv ^= Lb[i].astype(np.uint8)
        return h, lv
    sigs = [fsig(f) for f in faults]
    loc_bad = sum(1 for f, (h, lv) in zip(faults, sigs) for t in blocks if t not in (f[0], f[0] + 1) and np.any(h[t]))
    info["locality_violations"] = loc_bad
    info["weight1_logicals"] = sum(1 for (h, lv) in sigs if not any(np.any(h[t]) for t in h) and np.any(lv))

    if stim_check:
        import os
        sys.path.insert(0, "/Users/ephemeral/Desktop/qec-ai-search")
        from evaluators.noise import add_noise
        noisy = add_noise(c_plain, "sd6", 1e-3)
        nrec = C.nrec
        for t in sorted(blocks):
            for v in blocks[t]:
                noisy.append("DETECTOR", [stim.target_rec(cols_all[j] - nrec) for j in np.nonzero(v)[0]])
        for k, v in enumerate(OBS):
            noisy.append("OBSERVABLE_INCLUDE", [stim.target_rec(cols_all[j] - nrec) for j in np.nonzero(v)[0]], k)
        dem = noisy.detector_error_model(decompose_errors=False, allow_gauge_detectors=False)
        stim_set = set()
        for ins in dem.flattened():
            if ins.type == "error":
                ds = tuple(sorted(t.val for t in ins.targets_copy() if t.is_relative_detector_id()))
                ls = tuple(sorted(t.val for t in ins.targets_copy() if t.is_logical_observable_id()))
                stim_set.add((ds, ls))
        off = {}
        o = 0
        for t in sorted(blocks):
            off[t] = o
            o += len(blocks[t])
        mine = set()
        for (h, lv) in sigs:
            ds = tuple(sorted(off[t] + int(k) for t in h for k in np.nonzero(h[t])[0]))
            ls = tuple(int(k) for k in np.nonzero(lv)[0])
            if ds or ls:
                mine.add((ds, ls))
        info.update(stim_terms=len(stim_set), my_terms=len(mine), stim_eq_mine=stim_set == mine)

    # ------------------------------------------------------------ rounds, fold, symmetry (c3)
    f = HOMS[hom]
    Mlayers = set(i for i, (ops, tg) in enumerate(C.layers) if tg[1] == "M")

    def canon(comp):
        return tuple(sorted(((pt + 1) if (q < N and pt in Mlayers) else pt, q) for pt, q in comp))
    comp2sig = {}
    comp2first = {}
    for i, (ft, sg) in enumerate(zip(faults, sigs)):
        comp2sig.setdefault(canon(ft[5]), sg)
        if ft[5]:
            comp2first.setdefault(canon(ft[5]), i)

    def vec(sg, rows):
        h, lv = sg
        return np.concatenate([h[t] for t in rows] + [lv]).astype(np.uint8)

    rf_cache = {}

    def round_faults(r):
        if r not in rf_cache:
            rf_cache[r] = [i for i, ft in enumerate(faults) if ft[0] == r and len(ft[5]) > 0]
        return rf_cache[r]

    def instance(r):
        rows = [r, r + 1]
        nrow = sum(len(blocks[t]) for t in rows)
        cols = {}
        for i in round_faults(r):
            v = vec(sigs[i], rows)
            if not v.any():
                continue
            cols.setdefault(v.tobytes(), []).append(i)
        keys = list(cols)
        M = np.array([np.frombuffer(k, np.uint8) for k in keys]).T
        return M[:nrow], M[nrow:], keys, cols, nrow

    inst = {}
    for r in range(1, T + 1):
        H, Lm, keys, cols, nrow = instance(r)
        inst[r] = (H, Lm, keys, cols)
        info[f"round{r}"] = dict(rows=int(nrow), nonzero_rows=int(np.sum(H.any(axis=1))), rankH=rank(H),
                                 cols=H.shape[1], colweights=sorted(set(map(int, H.sum(0)))),
                                 zero_H_nonzero_L=int(np.sum((~H.any(axis=0)) & Lm.any(axis=0))))

    def check_map(fmap, r_from, r_to):
        src = round_faults(r_from)
        rows_f, rows_t = [r_from, r_from + 1], [r_to, r_to + 1]
        A = np.array([vec(sigs[i], rows_f) for i in src]).T
        Bl = []
        for i in src:
            j = fmap(i)
            if j is None:
                return dict(missing=True, ok=False)
            Bl.append(vec(sigs[j], rows_t))
        B = np.array(Bl).T
        na = sum(len(blocks[t]) for t in rows_f)
        nb = sum(len(blocks[t]) for t in rows_t)
        HA, HB = A[:na], B[:nb]
        rA, rB, rAB = rank(HA), rank(HB), rank(np.vstack([HA, HB]))
        sA, sB, sAB = rank(A), rank(B), rank(np.vstack([A, B]))
        img = [fmap(i) for i in src]
        cs_from = set(canon(faults[i][5]) for i in src)
        cs_img = set(canon(faults[j][5]) for j in img)
        cs_to = set(canon(faults[j][5]) for j in round_faults(r_to))
        return dict(rankH=(rA, rB, rAB), rankHL=(sA, sB, sAB),
                    ok=bool(rA == rB == rAB and sA == sB == sAB and len(cs_img) == len(cs_from) and cs_img == cs_to))

    def tmap(s, dr):
        def fm(i):
            comp = faults[i][5]
            im = canon([(pt + 8 * dr, code.translate_q(q, s)) for pt, q in canon(comp)])
            return comp2first.get(im)
        return fm

    LS = []
    for ops, tg in C.layers:
        d = {}
        for op, ts in ops:
            d[op] = d.get(op, frozenset()) | frozenset(ts)
        LS.append(d)

    def circuit_invariant(s, dr):
        for li in range(len(LS)):
            lj = li + 8 * dr
            if not (0 <= lj < len(LS)):
                continue
            a, b = LS[li], LS[lj]
            for op in set(a) | set(b):
                ts = a.get(op, frozenset())
                if op == "CX":
                    im = frozenset((code.translate_q(c, s), code.translate_q(t, s)) for c, t in ts)
                    bb = b.get(op, frozenset())
                else:
                    im = frozenset(code.translate_q(q, s) for q in ts if q >= N)
                    bb = frozenset(q for q in b.get(op, frozenset()) if q >= N)
                if bb != im:
                    return False
        return True

    G = [(i, j) for i in range(code.l) for j in range(code.m)]
    Kgrp = [s for s in G if f(s) == 0]
    Kc = [s for s in G if f(s) == 1]
    inv_K = [s for s in Kgrp if circuit_invariant(s, 0)]
    info["K_size"] = len(Kgrp)
    info["K_circuit_automorphisms"] = len(inv_K)
    info["nonK_automorphisms"] = len([s for s in Kc if circuit_invariant(s, 0)])
    iso = {}
    for r in range(1, T + 1):
        for r2 in range(r + 1, T + 1):
            dr = r2 - r
            if dr % 2 == 0:
                s = (0, 0)
            else:
                cand = [s for s in Kc if circuit_invariant(s, dr)]
                if not cand:
                    iso[f"{r}->{r2}"] = dict(ok=False, why="no K^c translation maps the rounds")
                    continue
                s = cand[0]
            iso[f"{r}->{r2}"] = dict(shift=s, **check_map(tmap(s, dr), r, r2))
    info["round_isomorphisms"] = iso
    info["all_rounds_equivalent"] = all(v.get("ok") for v in iso.values())

    comp_sets_by_round = {}
    for i, ft in enumerate(faults):
        if ft[5]:
            comp_sets_by_round.setdefault(ft[0], set()).add(canon(ft[5]))
    base = {r: [i for i, (ops, tg) in enumerate(C.layers) if tg == (r, "R")][0] for r in range(1, T + 1)}

    def mirror_comp(ft):
        r, li, kind, qs, pp, comp = ft
        b, b0 = base[r], base[r - 1]
        off = li - b
        out = []
        if off == 0:
            for (pt, q) in comp:
                assert pt == li + 1
                out.append((b0 + 7, q) if kind == "reset" else (b0 + 8, q))
        elif off == 7:
            for (pt, q) in comp:
                if kind == "meas":
                    assert pt == li
                else:
                    assert pt == li + 1
                out.append((b0 + 1, q))
        else:
            c, t = qs
            if 1 <= off <= 3:
                k = off - 1
                moff = 4 + (2 - k)
            else:
                k = off - 4
                moff = 1 + (2 - k)
            ml = b0 + moff
            xs = {q: 0 for q in (c, t)}
            for (pt, q) in comp:
                assert pt == li + 1
                xs[q] ^= 1
            if basis == "Z":
                xc, xt = xs[c], xs[t] ^ xs[c]
            else:
                xc, xt = xs[c] ^ xs[t], xs[t]
            if xc:
                out.append((ml + 1, c))
            if xt:
                out.append((ml + 1, t))
        return canon(out)

    Tb = sorted(blocks)

    def Hall(sg):
        return np.concatenate([sg[0][t] for t in Tb]).astype(np.uint8)
    mir_notfault = 0
    gen, loc = {}, {}
    for r in range(2, T + 1):
        src = round_faults(r)
        Psi = []
        for i in src:
            mc = mirror_comp(faults[i])
            if mc not in comp_sets_by_round[r - 1]:
                mir_notfault += 1
            ms = comp2sig[mc]
            Psi.append(np.concatenate([Hall(sigs[i]) ^ Hall(ms), sigs[i][1] ^ ms[1]]))
        Psi = np.array(Psi).T
        # general: Z_r = detectors vanishing on all faults of rounds < r
        early = [i for i, ft in enumerate(faults) if ft[0] < r and ft[5]]
        S_early = np.array([Hall(sigs[i]) for i in early]).T
        Y = nullspace(S_early.T)
        S_r = np.array([Hall(sigs[i]) for i in src]).T
        Zf = (Y.astype(np.int64) @ S_r.astype(np.int64)) % 2
        rz = rank(Zf)
        gen[r] = dict(dimZ=int(len(Y)), rank_on_round=int(rz), fold_ok=bool(rank(np.vstack([Zf, Psi])) == rz))
        # local: y in span(D_r, D_{r+1}) vanishing on round r-1 faults
        rows = [r, r + 1]
        prev = round_faults(r - 1)
        S_prev = np.array([np.concatenate([sigs[i][0][t] for t in rows]) for i in prev]).T
        Y2 = nullspace(S_prev.T)
        S_r2 = np.array([np.concatenate([sigs[i][0][t] for t in rows]) for i in src]).T
        Zf2 = (Y2.astype(np.int64) @ S_r2.astype(np.int64)) % 2
        rz2 = rank(Zf2)
        loc[r] = dict(dimZloc=int(len(Y2)), rank_on_round=int(rz2), fold_ok=bool(rank(np.vstack([Zf2, Psi])) == rz2))
    info["mirror_not_a_fault"] = mir_notfault
    info["fold_general"] = gen
    info["fold_local"] = loc
    info["fold_ok"] = bool(mir_notfault == 0 and all(v["fold_ok"] for v in gen.values())
                           and all(v["fold_ok"] for v in loc.values()))

    # symmetry on round-1 instance
    H, Lm, keys, cols = inst[1]
    colof = {}
    for c, k in enumerate(keys):
        for i in cols[k]:
            colof[i] = c
    perms = []
    sym_ok = True
    for s in inv_K:
        fm = tmap(s, 0)
        pi = {}
        good = True
        for c, k in enumerate(keys):
            ims = set(colof.get(fm(i), -1) for i in cols[k])
            if len(ims) != 1 or -1 in ims:
                good = False
                break
            pi[c] = ims.pop()
        if not good or sorted(pi.values()) != list(range(len(keys))):
            sym_ok = False
            break
        perm = [pi[c] for c in range(len(keys))]
        Hp, Lp = H[:, perm], Lm[:, perm]
        cond = rank(H) == rank(Hp) == rank(np.vstack([H, Hp])) and \
            rank(np.vstack([H, Lm])) == rank(np.vstack([Hp, Lp])) == rank(np.vstack([H, Lm, Hp, Lp]))
        if not cond:
            sym_ok = False
            break
        perms.append(perm)
    ncol = len(keys)
    orb = [-1] * ncol
    norb = 0
    if sym_ok:
        for c in range(ncol):
            if orb[c] < 0:
                for p in perms:
                    orb[p[c]] = norb
                norb += 1
    else:
        orb = list(range(ncol))
        norb = ncol
    info["sym_round1"] = dict(n_perms=len(perms), ok=sym_ok, n_orbits=norb)

    # sparse (record-singleton) basis of the round-1 instance, if span(D1 u D2) = all records of rounds 1, 2
    recs12 = [colpos[c] for c in grp[1] + grp[2]]
    D12 = np.vstack([blocks[1], blocks[2]])
    Hs = None
    if not np.any(np.delete(D12, recs12, axis=1)) and rank(D12[:, recs12]) == len(recs12) == D12.shape[0]:
        n = len(recs12)
        Aug = np.concatenate([D12[:, recs12].astype(np.uint8), np.eye(n, dtype=np.uint8)], axis=1)
        Rm, piv = rref(Aug)
        assert piv[:n] == list(range(n))
        Dinv = Rm[:, n:]
        Hs = (Dinv.astype(np.int64) @ H.astype(np.int64)) % 2
        assert rank(H) == rank(Hs) and rank(np.vstack([H, Lm])) == rank(np.vstack([Hs, Lm]))
    info["sparse_basis"] = Hs is not None
    Huse = Hs if Hs is not None else H
    # natural detector basis (contracted record of round 2 + round-1 records on its expanding support; round-1
    # memory-type records as singletons): an invertible transform of the record basis -> same column matroid,
    # smaller column weights (faster DFS).
    if Hs is not None:
        from search.experiments.e019.common import analyse
        _, ecx = analyse(code, gates, meas)
        sti = ecx["stabinfo"]
        recq = {}
        for pos, ci in enumerate(grp[1] + grp[2]):
            (rr, kind_), op_, q_ = recs[ci]
            recq[(rr, q_)] = pos
        n = len(recs12)
        Nm = np.zeros((n, n), np.uint8)
        for pos, ci in enumerate(grp[1] + grp[2]):
            (rr, kind_), op_, q_ = recs[ci]
            Nm[pos, pos] = 1
            if rr == 2:
                c2, c1 = 1, 0
                st = [k_ for k_, d_ in sti.items() if k_[0] == basis and d_[c2] == ("contract", q_)]
                assert len(st) == 1
                d1 = sti[st[0]][c1]
                assert d1[0] == "expand"
                for x in d1[2]:
                    Nm[pos, recq[(1, x)]] ^= 1
        assert rank(Nm) == n
        Hn = (Nm.astype(np.int64) @ Hs.astype(np.int64)) % 2
        assert rank(Hn) == rank(H) and rank(np.vstack([Hn, Lm])) == rank(np.vstack([H, Lm]))
        # a solution must have zero syndrome in both: check on random combos of the kernel
        Huse = Hn
        info["natural_basis"] = True
    info["inst_colweights"] = sorted(set(map(int, Huse.sum(0))))
    nz = [i for i in range(Huse.shape[0]) if Huse[i].any()]
    path = f"{OUT}/inst_{tag}_r1.txt"
    with open(path, "w") as fo:
        fo.write(f"{len(nz)} {ncol} {norb}\n")
        for c in range(ncol):
            rows_c = [nz.index(i) for i in np.nonzero(Huse[:, c])[0]]
            lmask = int(sum(1 << int(b) for b in np.nonzero(Lm[:, c])[0]))
            fo.write(f"{orb[c]} {lmask} {len(rows_c)} " + " ".join(map(str, rows_c)) + "\n")
    info["inst_path"] = path
    info["inst_rows"] = len(nz)
    pickle.dump(dict(faults=faults, keys=keys, cols=cols, orb=orb, H=H, L=Lm, info=info),
                open(f"{OUT}/inst_{tag}_r1.pkl", "wb"))
    json.dump(info, open(f"{OUT}/info_{tag}.json", "w"), indent=1, default=str)
    return info


if __name__ == "__main__":
    import os
    import time
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    key, basis = sys.argv[1], sys.argv[2]
    T = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    info = build(key, basis, T)
    summ = {k: info[k] for k in ("stim_eq_mine", "locality_violations", "weight1_logicals", "all_rounds_equivalent",
                                 "fold_ok", "sym_round1", "sparse_basis", "inst_rows", "inst_colweights",
                                 "K_circuit_automorphisms", "nonK_automorphisms") if k in info}
    summ["round1"] = info["round1"]
    summ["sec"] = round(time.time() - t0, 1)
    print(key, basis, T, json.dumps(summ, default=str), flush=True)
