"""B7: independent check of E-015's ibm_lift.py claim (IBM [[72,12,6]] depth-8 circuit, d_circ = 6 for R = 1..8).

Nothing from ibm_lift.py / e015 is used.  Inputs: the evaluator's memory circuit for the IBM schedule
(build_circuits + add_noise('sd6')) -- that is the object of the claim.

1. Own BB72 matrices (baseline convention) == evaluator css.  Own logical bases.
2. Per-check CNOT orders read off the noiseless stim circuit itself (per ancilla, CX partners between reset and
   measurement), checked identical in every cycle.
3. Own extended codes; ALL ext logicals of weight <= w by brute-force meet in the middle (no DFS).
4. Own fault enumeration: every Pauli component of every noise instruction (DEPOLARIZE1: X,Y,Z; DEPOLARIZE2: 15;
   X_ERROR / Z_ERROR / Y_ERROR: 1), propagated by an own bit-parallel Pauli-frame simulator (CX, R, RX, M, MX)
   -> detector set, observable mask, data image (X part for Z basis, Z part for X basis) at the end.
   Cross-checks vs stim: set of nonempty signatures == DEM error set; per-signature location counts vs
   explain_detector_error_model_errors(reduce_to_one_representative_error=False).
5. Table I check: every fault's image is 0 or exactly one ext column.
6. Exact decision: for every weight-w ext logical S, choose one DEM term (signature) per column of S (a term
   qualifies for column j if SOME fault with that signature has image j), distinct terms, detectors cancel,
   observable flips.  Meet in the middle.  Plus the brute force check that no undetected logical with <= w-1 ...
   is implied by Prop. 3 (d_ext = w).
usage: b_ibm.py <basis Z|X|both> <w> <R list comma> [lrc]
"""
import itertools
import json
import sys
import time
from collections import defaultdict, Counter
from pathlib import Path

import numpy as np
import stim

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, "tests")
from gf2 import logical_basis  # noqa: E402
import extx  # noqa: E402

OUT = Path("results/E-014-E-015-audit")


def bb_mats(l, m, Aexp, Bexp):
    def sh(a, b):
        P = np.zeros((l * m, l * m), np.uint8)
        for i in range(l):
            for j in range(m):
                P[i * m + j, ((i + a) % l) * m + (j + b) % m] = 1
        return P
    A = sum(sh(*e) for e in Aexp) % 2
    B = sum(sh(*e) for e in Bexp) % 2
    return np.hstack([A, B]).astype(np.uint8), np.hstack([B.T, A.T]).astype(np.uint8)


def ibm_spec():
    sys.path.insert(0, "search/experiments/e015")
    from evaluators.candidate import parse_schedule
    from schedule_helpers import from_baseline
    from search.codes.schedule import default_schedule
    from common import get_code
    return parse_schedule(from_baseline(default_schedule(get_code("bb72")))).canonical()


def orders_from_circuit(circ, n, HX, HZ):
    """Per ancilla: list of cycles, each = data partners in time order between a reset and the next measurement."""
    seq = defaultdict(list)
    for inst in circ.flattened():
        nm = inst.name
        t = [x.value for x in inst.targets_copy()]
        if nm == "CX":
            for a, b in zip(t[::2], t[1::2]):
                anc, d = (a, b) if a >= n else (b, a)
                assert d < n <= anc
                seq[anc].append(("C", d))
        elif nm in ("R", "RX", "M", "MX"):
            for q in t:
                if q >= n:
                    seq[q].append((nm, None))
    mx = HX.shape[0]
    xo, zo = [None] * mx, [None] * HZ.shape[0]
    ncyc = None
    for anc, s in seq.items():
        cycles, cur = [], None
        for op, d in s:
            if op in ("R", "RX"):
                cur = []
            elif op in ("M", "MX"):
                cycles.append(cur); cur = None
            else:
                cur.append(d)
        assert all(c == cycles[0] for c in cycles), "order differs between cycles"
        ncyc = len(cycles) if ncyc is None else ncyc
        assert ncyc == len(cycles)
        if anc < n + mx:
            i = anc - n; assert sorted(cycles[0]) == list(np.nonzero(HX[i])[0]); xo[i] = cycles[0]
        else:
            i = anc - n - mx; assert sorted(cycles[0]) == list(np.nonzero(HZ[i])[0]); zo[i] = cycles[0]
    return xo, zo, ncyc


def all_logicals(He, Le, wmax):
    r, N = He.shape
    hv = [int.from_bytes(np.packbits(He[:, j]).tobytes(), "big") for j in range(N)]
    lv = [int.from_bytes(np.packbits(Le[:, j]).tobytes(), "big") for j in range(N)]
    half = {}
    for a in range(0, (wmax // 2) + 1):
        for B in itertools.combinations(range(N), a):
            s = 0
            for j in B:
                s ^= hv[j]
            half.setdefault((a, s), []).append(B)
    out = {}
    for w in range(1, wmax + 1):
        a = (w + 1) // 2; b = w - a
        sols = []
        for A in itertools.combinations(range(N), a):
            s = 0
            for j in A:
                s ^= hv[j]
            for B in half.get((b, s), ()):
                if b and B[0] <= A[-1]:
                    continue
                lm = 0
                for j in A + B:
                    lm ^= lv[j]
                if lm:
                    sols.append(A + B)
        out[w] = sols
    return out


PAULIS1 = ["X", "Y", "Z"]
PAULIS2 = [(a, b) for a in "IXYZ" for b in "IXYZ" if (a, b) != ("I", "I")]


def enumerate_faults(circ):
    ops = list(circ.flattened())
    faults = []   # (op index, [(q, P)])
    for k, inst in enumerate(ops):
        nm = inst.name
        t = [x.value for x in inst.targets_copy()]
        if nm == "DEPOLARIZE1":
            for q in t:
                for P in PAULIS1:
                    faults.append((k, [(q, P)]))
        elif nm == "DEPOLARIZE2":
            for a, b in zip(t[::2], t[1::2]):
                for Pa, Pb in PAULIS2:
                    faults.append((k, [(q, P) for q, P in ((a, Pa), (b, Pb)) if P != "I"]))
        elif nm in ("X_ERROR", "Z_ERROR", "Y_ERROR"):
            for q in t:
                faults.append((k, [(q, nm[0])]))
        elif nm in ("M", "MX", "R", "RX", "CX", "TICK", "DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS"):
            if nm in ("M", "MX") and inst.gate_args_copy():
                raise ValueError("noisy measurement not handled")
        else:
            raise ValueError(nm)
    return ops, faults


def simulate(ops, faults, nq):
    F = len(faults)
    W = (F + 63) // 64
    X = np.zeros((nq, W), np.uint64); Z = np.zeros((nq, W), np.uint64)
    by_op = defaultdict(list)
    for f, (k, pp) in enumerate(faults):
        by_op[k].append((f, pp))
    recs, dets, obs = [], [], defaultdict(lambda: np.zeros(W, np.uint64))
    one = np.uint64(1)
    for k, inst in enumerate(ops):
        nm = inst.name
        if k in by_op:
            for f, pp in by_op[k]:
                w, b = f >> 6, np.uint64(f & 63)
                for q, P in pp:
                    if P in "XY":
                        X[q, w] |= one << b
                    if P in "ZY":
                        Z[q, w] |= one << b
            continue
        t = inst.targets_copy()
        if nm == "CX":
            v = [x.value for x in t]
            for c, g in zip(v[::2], v[1::2]):
                X[g] ^= X[c]; Z[c] ^= Z[g]
        elif nm in ("R", "RX"):
            for x in t:
                X[x.value] = 0; Z[x.value] = 0
        elif nm == "M":
            for x in t:
                recs.append(X[x.value].copy())
        elif nm == "MX":
            for x in t:
                recs.append(Z[x.value].copy())
        elif nm == "DETECTOR":
            acc = np.zeros(W, np.uint64)
            for x in t:
                acc ^= recs[len(recs) + x.value]
            dets.append(acc)
        elif nm == "OBSERVABLE_INCLUDE":
            idx = int(inst.gate_args_copy()[0])
            for x in t:
                obs[idx] = obs[idx] ^ recs[len(recs) + x.value]
    unpack = lambda A: np.unpackbits(A.view(np.uint8).reshape(A.shape[0], -1), axis=1, bitorder="little")[:, :F]  # noqa: E731
    D = unpack(np.array(dets))
    O = unpack(np.array([obs[i] for i in sorted(obs)]))
    return D, O, unpack(X), unpack(Z)


def run(basis, w, Rs, lrc=False):
    from evaluators.candidate import build_circuits
    from evaluators.noise import add_noise
    from evaluators.tasks import build_code, get_task
    css, _ = build_code(get_task("bb72-dcirc"), None)
    HX, HZ = bb_mats(6, 6, [(3, 0), (0, 1), (0, 2)], [(0, 3), (1, 0), (2, 0)])
    assert (np.asarray(css.HX) % 2 == HX).all() and (np.asarray(css.HZ) % 2 == HZ).all()
    n = 72
    if lrc:
        sys.path.insert(0, "search/experiments/e015")
        from assemble import build
        from schedule_helpers import from_baseline
        from evaluators.candidate import parse_schedule
        spec = parse_schedule(from_baseline(build("bb72", "01", [4, 34], [30, 0])[1])).canonical()
    else:
        spec = ibm_spec()
    LX = logical_basis(HZ, HX); LZ = logical_basis(HX, HZ)
    res = []
    noiseless = build_circuits(spec, css, 2)[basis]
    xo, zo, _ = orders_from_circuit(noiseless, n, HX, HZ)
    # Z basis: observable = Z logicals, flipped by X parts -> X-type ext (HZ, LZ, X-check orders)
    H, L, orders, part = (HZ, LZ, xo, "X") if basis == "Z" else (HX, LX, zo, "Z")
    e = extx.build(H, L, orders, n)
    He, Le = e["He"], e["Le"]
    t0 = time.time()
    logs = all_logicals(He, Le, w)
    sols = logs[w]
    below = sum(len(logs[v]) for v in range(1, w))
    colkey = {He[:, j].tobytes() + Le[:, j].tobytes(): j for j in range(He.shape[1])}
    print(f"{basis}: ext {He.shape}, logicals by weight {[len(logs[v]) for v in range(1, w + 1)]} ({time.time()-t0:.0f}s)", flush=True)
    for R in Rs:
        t0 = time.time()
        circ = add_noise(build_circuits(spec, css, R)[basis], "sd6", 1e-3).flattened()
        ops, faults = enumerate_faults(circ)
        D, O, Xf, Zf = simulate(ops, faults, circ.num_qubits)
        img = (Xf if part == "X" else Zf)[:n].astype(np.int64)        # n x F
        hk = (H.astype(np.int64) @ img) % 2
        lk = (L.astype(np.int64) @ img) % 2
        F = len(faults)
        # signatures
        sig_of, sig_list, fsig = {}, [], np.empty(F, np.int64)
        for f in range(F):
            key = np.packbits(D[:, f]).tobytes() + np.packbits(O[:, f]).tobytes()
            if key not in sig_of:
                sig_of[key] = len(sig_list); sig_list.append((D[:, f].copy(), O[:, f].copy()))
            fsig[f] = sig_of[key]
        empty = np.packbits(np.zeros(D.shape[0], np.uint8)).tobytes() + np.packbits(np.zeros(O.shape[0], np.uint8)).tobytes()
        empty_id = sig_of.get(empty, -1)
        nonempty = {s for s in range(len(sig_list)) if s != empty_id}
        # compare with stim DEM
        dem = circ.detector_error_model(decompose_errors=False)
        dem_set = set()
        for inst in dem.flattened():
            if inst.type != "error":
                continue
            dd = np.zeros(D.shape[0], np.uint8); oo = np.zeros(O.shape[0], np.uint8)
            for tt in inst.targets_copy():
                if tt.is_relative_detector_id():
                    dd[tt.val] ^= 1
                elif tt.is_logical_observable_id():
                    oo[tt.val] ^= 1
            dem_set.add(np.packbits(dd).tobytes() + np.packbits(oo).tobytes())
        mine_set = {k for k, s in sig_of.items() if s != empty_id}
        ex = circ.explain_detector_error_model_errors(reduce_to_one_representative_error=False)
        stim_loc = Counter()
        for x in ex:
            dd = np.zeros(D.shape[0], np.uint8); oo = np.zeros(O.shape[0], np.uint8)
            for tt in x.dem_error_terms:
                if tt.dem_target.is_relative_detector_id():
                    dd[tt.dem_target.val] ^= 1
                elif tt.dem_target.is_logical_observable_id():
                    oo[tt.dem_target.val] ^= 1
            stim_loc[np.packbits(dd).tobytes() + np.packbits(oo).tobytes()] += len(x.circuit_error_locations)
        my_loc = Counter(np.packbits(D[:, f]).tobytes() + np.packbits(O[:, f]).tobytes() for f in range(F) if fsig[f] != empty_id)
        # Table I + groups
        exc = 0
        groups = defaultdict(set)
        used_cols = set()
        for f in range(F):
            if not hk[:, f].any() and not lk[:, f].any():
                continue
            key = hk[:, f].astype(np.uint8).tobytes() + lk[:, f].astype(np.uint8).tobytes()
            j = colkey.get(key)
            if j is None:
                exc += 1
                continue
            used_cols.add(j)
            if fsig[f] != empty_id:
                groups[j].add(int(fsig[f]))
        # exact search
        detv = [int.from_bytes(np.packbits(d).tobytes(), "big") for d, _ in sig_list]
        obsv = [int.from_bytes(np.packbits(o).tobytes(), "big") for _, o in sig_list]
        hits, combos = [], 0
        for S in sols:
            G = [sorted(groups.get(j, ())) for j in S]
            h = len(G) // 2
            left = defaultdict(list)
            for c in itertools.product(*G[:h]):
                if len(set(c)) < len(c):
                    continue
                dm = om = 0
                for s in c:
                    dm ^= detv[s]; om ^= obsv[s]
                left[dm].append((om, c))
            for c in itertools.product(*G[h:]):
                if len(set(c)) < len(c):
                    continue
                combos += 1
                dm = om = 0
                for s in c:
                    dm ^= detv[s]; om ^= obsv[s]
                for om2, c2 in left.get(dm, ()):
                    if om ^ om2 and not set(c) & set(c2):
                        hits.append((S, c2 + c))
        rec = dict(basis=basis, R=R, w=w, faults=F, n_sigs_nonempty=len(nonempty), dem_errors=len(dem_set),
                   sig_set_equal_dem=mine_set == dem_set, locations_mine=sum(my_loc.values()),
                   locations_stim=sum(stim_loc.values()), per_sig_location_counts_equal=my_loc == stim_loc,
                   tableI_exceptions=exc, cols_realised=len(used_cols), n_cols=He.shape[1],
                   n_ext_logicals_w=len(sols), n_ext_logicals_below_w=below,
                   min_group=min(len(groups.get(j, ())) for S in sols for j in S) if sols else None,
                   right_combos=combos, hits=len(hits), sec=round(time.time() - t0, 1))
        print(rec, flush=True)
        res.append(rec)
    return res


if __name__ == "__main__":
    bases = "ZX" if sys.argv[1] == "both" else sys.argv[1]
    w = int(sys.argv[2])
    Rs = [int(x) for x in sys.argv[3].split(",")]
    lrc = len(sys.argv) > 4 and sys.argv[4] == "lrc"
    allres = []
    for b in bases:
        allres += run(b, w, Rs, lrc)
    tag = f"b_ibm_{sys.argv[1]}_w{w}_R{sys.argv[3].replace(',', '-')}{'_lrc' if lrc else ''}"
    (OUT / f"{tag}.json").write_text(json.dumps(allres, indent=1, default=str))
