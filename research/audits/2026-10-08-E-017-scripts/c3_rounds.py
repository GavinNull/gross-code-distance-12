"""C3: per-round instances, round-to-round isomorphism, the Prop. 1 fold premise (mirror check),
translation symmetry, and DFS instance output.

usage: c3_rounds.py <hom> <order> <basis> <T>
Reads results/E-017-audit/c2_<tag>.pkl.
"""
import json
import pickle
import sys

import numpy as np

from common import N, HOMS, l as LL, m as MM, gid, rank, memory

hom, order, basis, T = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
OUT = "/Users/ephemeral/Desktop/qec-ai-search/results/E-017-audit"
tag = f"{hom}_{order}_{basis}_T{T}"
P = pickle.load(open(f"{OUT}/c2_{tag}.pkl", "rb"))
faults, sigs, blocks = P["faults"], P["sigs"], P["blocks"]
C, gates, meas = memory(hom, order, T, basis)
f = HOMS[hom]
res = {}
Mlayers = set(i for i, (ops, tg) in enumerate(C.layers) if tg[1] == "M")


def canon(comp):
    """left qubits are untouched between 'just before an M layer' and 'just after it': identify the points."""
    return tuple(sorted(((pt + 1) if (q < N and pt in Mlayers) else pt, q) for pt, q in comp))



# fault id by (round, layer, kind, qubits, pauli); keep only faults with nonzero projected part
key2i = {}
for i, ft in enumerate(faults):
    key2i[ft[:5]] = i
comp2sig = {}
for ft, sg in zip(faults, sigs):
    comp2sig.setdefault(canon(ft[5]), sg)


def vec(sg, rows):
    h, lv = sg
    return np.concatenate([h[t] for t in rows] + [lv]).astype(np.uint8)


def round_faults(r):
    return [i for i, ft in enumerate(faults) if ft[0] == r and len(ft[5]) > 0]


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
    M = np.array([np.frombuffer(k, np.uint8) for k in keys]).T  # (nrow+12) x ncol
    return M[:nrow], M[nrow:], keys, cols, nrow


# ---------------- per-round instances
inst = {}
for r in range(1, T + 1):
    H, Lm, keys, cols, nrow = instance(r)
    nzrows = int(np.sum(H.any(axis=1)))
    inst[r] = (H, Lm, keys, cols)
    res[f"round{r}"] = dict(rows=int(nrow), nonzero_rows=nzrows, rankH=rank(H), cols=H.shape[1],
                            colweights=sorted(set(map(int, H.sum(0)))),
                            zero_H_cols=int(np.sum(~H.any(axis=0))),
                            zero_H_nonzero_L=int(np.sum((~H.any(axis=0)) & Lm.any(axis=0))))
print(json.dumps(res))


# ---------------- maps between fault spaces, checked by rank conditions
def check_map(fmap, r_from, r_to):
    """fmap: fault index in round r_from -> fault index in round r_to (or None). Condition for
    (H x = 0, L x != 0) to be preserved both ways: rowspace([H]) and rowspace([H;L]) equal as functionals
    on the round-r_from fault space. Returns dict."""
    src = round_faults(r_from)
    rows_f, rows_t = [r_from, r_from + 1], [r_to, r_to + 1]
    A = np.array([vec(sigs[i], rows_f) for i in src]).T
    miss = 0
    Bl = []
    for i in src:
        j = fmap(i)
        if j is None:
            miss += 1
            Bl.append(np.zeros(A.shape[0] - 12 + 0, np.uint8))
            continue
        Bl.append(vec(sigs[j], rows_t))
    if miss:
        return dict(missing=miss)
    B = np.array(Bl).T
    na = sum(len(blocks[t]) for t in rows_f)
    nb = sum(len(blocks[t]) for t in rows_t)
    HA, HB = A[:na], B[:nb]
    rA, rB, rAB = rank(HA), rank(HB), rank(np.vstack([HA, HB]))
    FA, FB = A, B
    sA, sB, sAB = rank(FA), rank(FB), rank(np.vstack([FA, FB]))
    # bijectivity on faults
    img = [fmap(i) for i in src]
    cs_from = set(canon(faults[i][5]) for i in src)
    cs_img = set(canon(faults[j][5]) for j in img)
    cs_to = set(canon(faults[j][5]) for j in round_faults(r_to))
    return dict(rankH=(rA, rB, rAB), rankHL=(sA, sB, sAB), ok=bool(rA == rB == rAB and sA == sB == sAB),
                comp_bijective=bool(len(cs_img) == len(cs_from) and cs_img == cs_to))


def translate_q(q, s):
    i, j = (q % N) // MM, (q % N) % MM
    return (N if q >= N else 0) + gid(i + s[0], j + s[1])


def tmap(s, dr):
    """component-level map: fault i in round r -> some fault in round r+dr whose projected components are
    the time-shifted, translated components of fault i (kinds may differ at the boundary, e.g. left reset
    flip vs left idle X: same projected Pauli at the same place)."""
    def fm(i):
        comp = faults[i][5]
        im = canon([(pt + 8 * dr, translate_q(q, s)) for pt, q in canon(comp)])
        return comp2first.get(im)
    return fm


comp2first = {}
for i, ft in enumerate(faults):
    if ft[5]:
        comp2first.setdefault(canon(ft[5]), i)


# circuit invariance of every layer under translations s
def layer_sets(Cc):
    out = []
    for ops, tg in Cc.layers:
        d = {}
        for op, ts in ops:
            d[op] = d.get(op, frozenset()) | frozenset(ts)
        out.append(d)
    return out


LS = layer_sets(C)


def circuit_invariant(s, dr):
    for li in range(len(LS)):
        lj = li + 8 * dr
        if not (0 <= lj < len(LS)):
            continue
        a, b = LS[li], LS[lj]
        for op, ts in a.items():
            if op == "CX":
                im = frozenset((translate_q(c, s), translate_q(t, s)) for c, t in ts)
            else:
                ts = frozenset(q for q in ts if q >= N)
                im = frozenset(translate_q(q, s) for q in ts)
            bb = b.get(op, frozenset())
            if op != "CX":
                bb = frozenset(q for q in bb if q >= N)
            if bb != im:
                return False
    return True


Kgrp = [(i, j) for i in range(LL) for j in range(MM) if f((i, j)) == 0]
Kc = [(i, j) for i in range(LL) for j in range(MM) if f((i, j)) == 1]
inv_K = [s for s in Kgrp if circuit_invariant(s, 0)]
res["K_size"] = len(Kgrp)
res["K_circuit_automorphisms"] = len(inv_K)
# any non-K translation that is an automorphism?
res["nonK_automorphisms"] = [s for s in Kc if circuit_invariant(s, 0)]

# round isomorphisms: r -> r+2 (pure time shift), r -> r+1 (time shift + a K^c translation)
iso = {}
for r in range(1, T + 1):
    for r2 in range(r + 1, T + 1):
        dr = r2 - r
        if dr % 2 == 0:
            s = (0, 0)
        else:
            cand = [s for s in Kc if circuit_invariant(s, dr)]
            if not cand:
                iso[f"{r}->{r2}"] = "no K^c translation maps the rounds"
                continue
            s = cand[0]
        iso[f"{r}->{r2}"] = dict(shift=s, **check_map(tmap(s, dr), r, r2))
res["round_isomorphisms"] = iso
print(json.dumps(iso, default=str))

# ---------------- mirror (Prop. 1 premise)
comp_sets_by_round = {}
for i, ft in enumerate(faults):
    if ft[5]:
        comp_sets_by_round.setdefault(ft[0], set()).add(canon(ft[5]))
base = {r: [i for i, (ops, tg) in enumerate(C.layers) if tg == (r, "R")][0] for r in range(1, T + 1)}


def mirror_comp(ft):
    """projected Pauli components of the time-reversed partner (in round r-1) of fault ft (round r)."""
    r, li, kind, qs, pp, comp = ft
    b, b0 = base[r], base[r - 1]
    off = li - b
    out = []
    if off == 0:  # R layer: reset X after reset (q right) or left idle after layer
        for (pt, q) in comp:
            assert pt == li + 1
            if kind == "reset":
                out.append((b0 + 7, q))           # measurement flip before M of round r-1
            else:
                out.append((b0 + 8, q))           # idle after the M layer of round r-1
    elif off == 7:  # M layer
        for (pt, q) in comp:
            if kind == "meas":
                assert pt == li
                if q >= N:
                    out.append((b0 + 1, q))       # reset flip after R of round r-1
                else:
                    out.append((b0 + 1, q))       # final left readout flip -> left idle in R layer
            else:
                assert pt == li + 1
                out.append((b0 + 1, q))           # left idle in R layer
    else:
        c, t = qs
        # fault after gate g in layer off (1..6); mirror layer: Fd_k (off=1+k) -> F_{2-k} (off 4+2-k); F_k (off 4+k) -> Fd_{2-k} (off 1+2-k)
        if 1 <= off <= 3:
            k = off - 1; moff = 4 + (2 - k)
        else:
            k = off - 4; moff = 1 + (2 - k)
        ml = b0 + moff
        xs = {q: 0 for q in (c, t)}
        for (pt, q) in comp:
            assert pt == li + 1
            xs[q] ^= 1
        # Pauli placed *before* g in the mirrored layer = conjugated by g, placed after g
        if basis == "Z":   # X parts: X_c -> X_c X_t
            xc, xt = xs[c], xs[t] ^ xs[c]
        else:              # Z parts: Z_t -> Z_c Z_t
            xc, xt = xs[c] ^ xs[t], xs[t]
        if xc:
            out.append((ml + 1, c))
        if xt:
            out.append((ml + 1, t))
    return canon(out)


mir = {}
for r in range(2, T + 1):
    src = round_faults(r)
    rows_next = r + 1
    Hn = np.array([sigs[i][0][rows_next] for i in src]).T
    Psi = []
    notfault = 0
    for i in src:
        mc = mirror_comp(faults[i])
        if mc not in comp_sets_by_round[r - 1]:
            notfault += 1
        msig = comp2sig.get(mc)
        if msig is None:
            # compute directly not available -> count
            Psi.append(None)
            continue
        h, lv = sigs[i]
        mh, mlv = msig
        Psi.append(np.concatenate([h[r] ^ mh[r], mh[r - 1], lv ^ mlv]))
    if any(p is None for p in Psi):
        mir[r] = dict(mirror_not_a_fault=notfault, missing_sig=sum(p is None for p in Psi))
        continue
    Psi = np.array(Psi).T
    rh = rank(Hn)
    ok = rank(np.vstack([Hn, Psi])) == rh
    # paper's stronger per-fault statements
    per_fault_Dr_equal = all(not np.any(Psi[:len(blocks[r]), k]) for k in range(Psi.shape[1]))
    per_fault_L_equal = all(not np.any(Psi[-12:, k]) for k in range(Psi.shape[1]))
    mir[r] = dict(mirror_not_a_fault=notfault, n=len(src), fold_condition=bool(ok),
                  per_fault_D_r_equal=per_fault_Dr_equal, per_fault_L_equal=per_fault_L_equal)
res["mirror"] = mir
print(json.dumps(mir))

# ---------------- symmetry on the round-r instance + DFS instance file
for r in (1, 2):
    H, Lm, keys, cols = inst[r]
    nrow = H.shape[0]
    kidx = {k: c for c, k in enumerate(keys)}
    colof = {}
    for c, k in enumerate(keys):
        for i in cols[k]:
            colof[i] = c
    perms = []
    ok_all = True
    for s in inv_K:
        fm = tmap(s, 0)
        pi = {}
        good = True
        for c, k in enumerate(keys):
            ims = set(colof[fm(i)] for i in cols[k])
            if len(ims) != 1:
                good = False
                break
            pi[c] = ims.pop()
        if not good or sorted(pi.values()) != list(range(len(keys))):
            ok_all = False
            break
        perm = [pi[c] for c in range(len(keys))]
        # rank conditions as functionals on column space
        Hp, Lp = H[:, perm], Lm[:, perm]
        cond = rank(H) == rank(Hp) == rank(np.vstack([H, Hp])) and \
            rank(np.vstack([H, Lm])) == rank(np.vstack([Hp, Lp])) == rank(np.vstack([H, Lm, Hp, Lp]))
        if not cond:
            ok_all = False
            break
        perms.append(perm)
    # orbits
    ncol = len(keys)
    orb = [-1] * ncol
    norb = 0
    for c in range(ncol):
        if orb[c] < 0:
            for p in perms:
                orb[p[c]] = norb
            norb += 1
    sizes = sorted(set(orb.count(o) for o in range(norb)))
    res[f"sym_round{r}"] = dict(n_perms=len(perms), ok=ok_all, n_orbits=norb, orbit_sizes=sizes)
    print(r, res[f"sym_round{r}"])
    # write instance: drop all-zero rows
    nz = [i for i in range(nrow) if H[i].any()]
    Hn = H[nz]
    with open(f"{OUT}/inst_{tag}_r{r}.txt", "w") as fo:
        fo.write(f"{len(nz)} {ncol} {norb}\n")
        for c in range(ncol):
            rows_c = np.nonzero(Hn[:, c])[0].tolist()
            lmask = int(sum(1 << b for b in np.nonzero(Lm[:, c])[0]))
            fo.write(f"{orb[c]} {lmask} {len(rows_c)} " + " ".join(map(str, rows_c)) + "\n")
    # orbit reps: first column of each orbit; the DFS uses orbit labels directly
    pickle.dump(dict(keys=keys, cols=cols, orb=orb, perms=perms, H=H, L=Lm, nz=nz),
                open(f"{OUT}/inst_{tag}_r{r}.pkl", "wb"))
json.dump(res, open(f"{OUT}/c3_{tag}.json", "w"), indent=1, default=str)

# ---------------- general (basis-free) fold condition
# Z_r = detectors (in the full span) that vanish on every fault of rounds < r. The fold of the round-r part E
# of an undetectable F (last round r) is valid iff for every E with Z_r(E) = 0:
#   H_all(E) = H_all(mu E)  and  L(E) = L(mu E).
from common import nullspace as _ns
Tb = sorted(blocks)
def Hall(sg):
    return np.concatenate([sg[0][t] for t in Tb]).astype(np.uint8)
gen = {}
for r in range(2, T + 1):
    early = [i for i, ft in enumerate(faults) if ft[0] < r and ft[5]]
    S_early = np.array([Hall(sigs[i]) for i in early]).T          # ndet x n_early
    Y = _ns(S_early.T)                                            # rows y with y^T S_early = 0
    src = round_faults(r)
    S_r = np.array([Hall(sigs[i]) for i in src]).T
    Zf = (Y.astype(np.int64) @ S_r.astype(np.int64)) % 2          # functionals on round-r faults
    Psi = []
    for i in src:
        mc = mirror_comp(faults[i])
        ms = comp2sig[mc]
        Psi.append(np.concatenate([Hall(sigs[i]) ^ Hall(ms), sigs[i][1] ^ ms[1]]))
    Psi = np.array(Psi).T
    rz = rank(Zf)
    ok = rank(np.vstack([Zf, Psi])) == rz
    # which part fails
    okH = rank(np.vstack([Zf, Psi[:-12]])) == rz
    gen[r] = dict(dimZ=int(len(Y)), rankZ_on_round=int(rz), fold_ok=bool(ok), H_part_ok=bool(okH))
print("general fold", gen)
res["mirror_general"] = gen
json.dump(res, open(f"{OUT}/c3_{tag}.json", "w"), indent=1, default=str)

# ---------------- local version of the fold condition (depends only on rounds r-1, r and blocks D_{r-1..r+1}),
# so that by periodicity it covers every T: Z_loc = y in span(D_r, D_{r+1}) vanishing on round-(r-1) faults.
loc = {}
for r in range(2, T + 1):
    rows = [r, r + 1]
    prev = round_faults(r - 1)
    S_prev = np.array([np.concatenate([sigs[i][0][t] for t in rows]) for i in prev]).T
    Y = _ns(S_prev.T)
    src = round_faults(r)
    S_r = np.array([np.concatenate([sigs[i][0][t] for t in rows]) for i in src]).T
    Zf = (Y.astype(np.int64) @ S_r.astype(np.int64)) % 2
    Psi = []
    for i in src:
        ms = comp2sig[mirror_comp(faults[i])]
        Psi.append(np.concatenate([Hall(sigs[i]) ^ Hall(ms), sigs[i][1] ^ ms[1]]))
    Psi = np.array(Psi).T
    rz = rank(Zf)
    loc[r] = dict(dimZloc=int(len(Y)), rank_on_round=int(rz), fold_ok=bool(rank(np.vstack([Zf, Psi])) == rz))
print("local fold", loc)
res["mirror_local"] = loc
json.dump(res, open(f"{OUT}/c3_{tag}.json", "w"), indent=1, default=str)
