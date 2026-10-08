"""C2: detectors, fault signatures, structure checks, single-round instances.

usage: c2_instance.py <hom> <order> <basis Z|X> <T> [--stim-check]

Memory basis B. Only same-basis records are used (CSS relaxation): for Z memory, Z-basis records and the
X part of every fault; for X memory, X-basis records and Z parts.  Dropping detectors / the other
Pauli part can only create more 'undetectable' sets, so a lower bound on the relaxed problem is a lower
bound on the true circuit distance.

Detectors are found by sampling the noiseless circuit (stim) and taking the GF(2) kernel of the
record differences, (a) with 12 random mid-cycle logicals injected (-> detectors only),
(b) without (-> detectors + observables). Detector blocks D_t = deterministic parities supported on
same-basis records of rounds t-1, t (t=1..T), D_{T+1} = final block (rounds T-1, T and readout).

Faults (sd6, my own enumeration): every Pauli component of every noise location, projected to the
relevant part; signatures by my own bit-parallel frame propagation.
"""
import json
import pickle
import sys

import numpy as np
import stim

from common import N, bb_checks, memory, nullspace, rank, rref, HOMS, l as LL, m as MM, gid

hom, order, basis, T = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
STIM_CHECK = "--stim-check" in sys.argv
OUT = "/Users/ephemeral/Desktop/qec-ai-search/results/E-017-audit"
tag = f"{hom}_{order}_{basis}_T{T}"
rng_seed = 12345

C, gates, meas = memory(hom, order, T, basis)
mop = "M" if basis == "Z" else "MX"     # same-basis measurement op
rop = "R" if basis == "Z" else "RX"
HX, HZ = bb_checks()

# ---------------------------------------------------------------- records
recs = C.recs  # (tag=(round, kind), op, qubit)
same = [i for i, (tg, op, q) in enumerate(recs) if op == mop]
grp = {}
for i in same:
    (r, kind), op, q = recs[i]
    key = "F" if (r == T and q < N) else r
    grp.setdefault(key, []).append(i)
for k in grp:
    grp[k] = sorted(grp[k])
assert all(len(grp[r]) == 72 for r in range(1, T + 1)) and len(grp["F"]) == N

# ---------------------------------------------------------------- sampling
def logicals(Hstab, Hother):
    """basis of ker(Hother) modulo rowspace(Hstab)"""
    K = nullspace(Hother)
    out = []
    cur = Hstab.copy()
    rk = rank(cur)
    for v in K:
        t = np.vstack([cur, v])
        r2 = rank(t)
        if r2 > rk:
            out.append(v); cur = t; rk = r2
    return np.array(out)

# randomise mid-cycle logicals of the memory type's conjugate: Z memory -> X logicals (flip Z logical values)
if basis == "Z":
    LOG = logicals(HX, HZ)   # X-type logical ops (commute with Z stabs, not in X stab space)
    pchar = "X"
else:
    LOG = logicals(HZ, HX)
    pchar = "Z"
assert len(LOG) == 12, len(LOG)
# position: after round-1 inverse contraction (mid-cycle code), i.e. after layer tagged (1,'Fd2')
li_mid = [i for i, (ops, tg) in enumerate(C.layers) if tg == (1, "Fd2")][0]
rand = stim.Circuit()
for v in LOG:
    rand.append("E", [stim.target_x(q) if pchar == "X" else stim.target_z(q) for q in np.nonzero(v)[0]], 0.5)
c_plain = C.stim()
c_rand = C.stim({li_mid: rand})


def sample_kernel(circ, cols, shots=1600):
    s = circ.compile_sampler(seed=rng_seed).sample(shots).astype(np.uint8)
    d = s ^ s[0]
    return nullspace(d[:, cols])


cols_all = same
Kdet = sample_kernel(c_rand, cols_all)
Kall = sample_kernel(c_plain, cols_all)
colpos = {c: i for i, c in enumerate(cols_all)}


def embed(vecs, sub):
    out = np.zeros((len(vecs), len(cols_all)), np.uint8)
    for j, c in enumerate(sub):
        out[:, colpos[c]] = vecs[:, j]
    return out


# time-local detectors. regdet_t(s) only depends on the reset at round t-1 and the measurements of rounds
# t-1, t. So: D_1 = deterministic parities of round-1 records (comparison with the ideal initial values);
# D_t (t>=2) = parities on rounds t-1, t that stay deterministic when a uniformly random projected-type
# Pauli is applied to every qubit just before round t-1 (after the M layer of round t-2; for t=2 nothing
# precedes round 1 except the initial resets, so no randomisation is needed).
# Final block: parities on round T and the readout, random Pauli before round T.
def rand_before_round(r):
    if r <= 1:
        return c_rand
    li = [i for i, (ops, tg) in enumerate(C.layers) if tg == (r - 1, "M")][0]
    ini = stim.Circuit()
    ini.append("X_ERROR" if basis == "Z" else "Z_ERROR", list(range(2 * N)), 0.5)
    return C.stim({li: ini, li_mid: rand} if li_mid > li else {li: ini})


blocks = {}
blocks[1] = embed(sample_kernel(c_rand, grp[1]), grp[1])
for t in range(2, T + 1):
    sub = grp[t - 1] + grp[t]
    blocks[t] = embed(sample_kernel(rand_before_round(t - 1), sub), sub)
# D_2 contains D_1 (round-1 singletons); keep only a complement
if T >= 2:
    keep = []
    rk0 = rank(blocks[1])
    for v in blocks[2]:
        if rank(np.vstack([blocks[1]] + keep + [v[None]])) > rk0 + len(keep):
            keep.append(v[None])
    blocks[2] = np.vstack(keep)
sub = grp[T] + grp["F"]
fin = embed(sample_kernel(rand_before_round(T), sub), sub)
# final block = complement of D_T inside fin
base = blocks[T]
rk = rank(base)
extra = []
for v in fin:
    t2 = np.vstack([base] + extra + [v[None]])
    if rank(t2) > rk + len(extra):
        extra.append(v[None])
blocks[T + 1] = np.vstack(extra) if extra else np.zeros((0, len(cols_all)), np.uint8)
# sparse canonical bases: RREF with the latest records as pivot columns first
def sparsify(B, first):
    if len(B) == 0:
        return B
    order_ = [colpos[c] for c in first] + [i for i in range(len(cols_all)) if i not in set(colpos[c] for c in first)]
    Rm, _ = rref(B[:, order_])
    out = np.zeros_like(Rm)
    out[:, order_] = Rm
    return out


for t in range(2, T + 1):
    blocks[t] = sparsify(blocks[t], grp[t])
blocks[T + 1] = sparsify(blocks[T + 1], grp[T])
Dall = np.vstack([blocks[t] for t in range(1, T + 2)])
info = dict(dim_Kdet=len(Kdet), dim_Kall=len(Kall), block_dims={t: int(len(blocks[t])) for t in blocks},
            rank_blocks=rank(Dall), blocks_span_Kdet=bool(rank(np.vstack([Dall, Kdet])) == rank(Dall) == len(Kdet)))
# observables: complement of Kdet in Kall, preferably supported late
subL = grp.get(T - 1, []) + grp[T] + grp["F"]
Klate = embed(sample_kernel(c_plain, subL), subL)
obs = []
cur = Kdet.copy(); rk = rank(cur)
for v in list(Klate) + list(Kall):
    t2 = np.vstack([cur, v])
    if rank(t2) > rk:
        obs.append(v); cur = t2; rk += 1
OBS = np.array(obs)
info["n_obs"] = len(OBS)
assert len(OBS) == 12
print(json.dumps(info))

# ---------------------------------------------------------------- faults (projected part only)
# injection point P_li = just before layer li. Basis vector (li, q) = Pauli part on q at P_li.
nl = len(C.layers)
touched = []
for ops, tg in C.layers:
    s = set()
    for op, ts in ops:
        if op == "CX":
            for a, b in ts:
                s.add(a); s.add(b)
        else:
            s.update(ts)
    touched.append(s)

# each fault: (round, layer, kind, qubits, components) ; components = list of (point, qubit)
faults = []
for li, (ops, tg) in enumerate(C.layers):
    r = tg[0]
    for op, ts in ops:
        if op == "CX":
            for (c, t) in ts:
                # DEPOLARIZE2 after the gate: 15 Paulis; projected part on (c, t) at P_{li+1}
                for pc in "IXYZ":
                    for pt in "IXYZ":
                        if pc == pt == "I":
                            continue
                        comp = []
                        for q, pp in ((c, pc), (t, pt)):
                            has = (pp in "XY") if basis == "Z" else (pp in "ZY")
                            if has:
                                comp.append((li + 1, q))
                        faults.append((r, li, "cx", (c, t), pc + pt, tuple(comp)))
        elif op in ("R", "RX"):
            for q in ts:
                # flip after reset: X_ERROR after R, Z_ERROR after RX
                pp = "X" if op == "R" else "Z"
                has = (pp == "X") if basis == "Z" else (pp == "Z")
                faults.append((r, li, "reset", (q,), pp, ((li + 1, q),) if has else ()))
        elif op in ("M", "MX"):
            for q in ts:
                pp = "X" if op == "M" else "Z"
                has = (pp == "X") if basis == "Z" else (pp == "Z")
                faults.append((r, li, "meas", (q,), pp, ((li, q),) if has else ()))
    for q in range(2 * N):
        if q not in touched[li]:
            for pp in "XYZ":
                has = (pp in "XY") if basis == "Z" else (pp in "ZY")
                faults.append((r, li, "idle", (q,), pp, ((li + 1, q),) if has else ()))

# ---------------------------------------------------------------- frame propagation
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
            cs = np.array([a for a, b in ts]); tt = np.array([b for a, b in ts])
            if basis == "Z":   # X parts: control -> target
                F[:, tt] ^= F[:, cs]
            else:              # Z parts: target -> control
                F[:, cs] ^= F[:, tt]
        elif op in ("M", "MX"):
            for q in ts:
                if op == mop:
                    flips[:, colpos[rec_ptr]] = F[:, q]
                rec_ptr += 1
        elif op in ("R", "RX"):
            F[:, list(ts)] = 0
for (i, q) in by_layer.get(nl, []):
    pass  # after last layer: no effect
assert rec_ptr == C.nrec

Hb = {t: (flips.astype(np.int64) @ blocks[t].T.astype(np.int64)) % 2 for t in blocks}
Lb = (flips.astype(np.int64) @ OBS.T.astype(np.int64)) % 2


def fsig(f):
    comp = f[5]
    h = {t: np.zeros(len(blocks[t]), np.uint8) for t in blocks}
    lv = np.zeros(12, np.uint8)
    for cp in comp:
        i = pidx[cp]
        for t in blocks:
            h[t] ^= Hb[t][i].astype(np.uint8)
        lv ^= Lb[i].astype(np.uint8)
    return h, lv


sigs = [fsig(f) for f in faults]

# locality: round-r faults touch only D_r, D_{r+1}
loc_bad = 0
for f, (h, lv) in zip(faults, sigs):
    r = f[0]
    for t in blocks:
        if t not in (r, r + 1) and np.any(h[t]):
            loc_bad += 1
info["locality_violations"] = loc_bad
print("locality violations", loc_bad)

# weight-1 logicals?
w1 = sum(1 for (h, lv) in sigs if not any(np.any(h[t]) for t in h) and np.any(lv))
info["weight1_logicals"] = w1

pickle.dump(dict(faults=faults, sigs=sigs, blocks=blocks, OBS=OBS, grp=grp, cols_all=cols_all, recs=recs,
                 info=info, T=T), open(f"{OUT}/c2_{tag}.pkl", "wb"))

# ---------------------------------------------------------------- stim cross-check
if STIM_CHECK:
    sys.path.insert(0, "/Users/ephemeral/Desktop/qec-ai-search")
    from evaluators.noise import add_noise
    noisy = add_noise(c_plain, "sd6", 1e-3)
    nrec = C.nrec
    rows = [(t, k) for t in sorted(blocks) for k in range(len(blocks[t]))]
    for (t, k) in rows:
        v = blocks[t][k]
        noisy.append("DETECTOR", [stim.target_rec(cols_all[j] - nrec) for j in np.nonzero(v)[0]])
    for k, v in enumerate(OBS):
        noisy.append("OBSERVABLE_INCLUDE", [stim.target_rec(cols_all[j] - nrec) for j in np.nonzero(v)[0]], k)
    dem = noisy.detector_error_model(decompose_errors=False, allow_gauge_detectors=False)
    stim_set = set()
    for inst in dem.flattened():
        if inst.type == "error":
            ds = tuple(sorted(t.val for t in inst.targets_copy() if t.is_relative_detector_id()))
            ls = tuple(sorted(t.val for t in inst.targets_copy() if t.is_logical_observable_id()))
            stim_set.add((ds, ls))
    off = {}
    o = 0
    for t in sorted(blocks):
        off[t] = o; o += len(blocks[t])
    mine = set()
    for (h, lv) in sigs:
        ds = tuple(sorted(off[t] + int(k) for t in h for k in np.nonzero(h[t])[0]))
        ls = tuple(int(k) for k in np.nonzero(lv)[0])
        if ds or ls:
            mine.add((ds, ls))
    info["stim_terms"] = len(stim_set)
    info["my_terms"] = len(mine)
    info["stim_eq_mine"] = stim_set == mine
    info["stim_minus_mine"] = len(stim_set - mine)
    info["mine_minus_stim"] = len(mine - stim_set)
    print("stim check", info["stim_terms"], info["my_terms"], info["stim_eq_mine"])
json.dump(info, open(f"{OUT}/c2_{tag}.json", "w"), indent=1, default=str)
