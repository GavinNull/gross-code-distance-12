"""E-026 stage B (exact family enumeration): circuit logicals built from the COMPLETE list of weight-11 extended-code
logicals (E-018: 4224 per side; Fig. 12 and p18 share this extended code, E-024).  Uses the E-018 augmented-DEM
argument (Table I: every fault's image is 0 or one extended column, asserted):
  mode "w11"  : choose one fault per column of S (11 faults), detector XOR = 0  -> all weight-11 circuit logicals
                (complete for Fig. 12; must be empty for p18, which re-checks d_circ >= 12 at this R).
  mode "w11z" : 11 image faults + ONE zero-image fault (measurement/reset/ancilla-only), XOR = 0 -> weight-12 logicals
                of 'type (b)'.  Weight-12 logicals whose 12 images form a weight-12 extended logical ('type (a)') are NOT
                enumerated here (no complete weight-12 extended list exists) -> type (b) is a lower bound on W12.
All solutions are enumerated (frontier DP with predecessor lists), with the SD6 prior of every term at PE.
Output: results/E-026-gross-ler/lift/<circ>_<basis>_<mode>_R<R>.npz  (terms per logical, log-priors).

  uv run python -m search.experiments.e026.lift_enum --circ fig12 --basis Z --mode w11 --R 4 5
"""
import argparse, json, time, sys
from pathlib import Path
import numpy as np
import stim

from search.experiments.e026.common import OUT, spec, code
from evaluators.candidate import build_circuits
from evaluators.noise import add_noise
from search.experiments.e018 import common as C18

PE = 1e-3
OBS = {}   # (col, mask) -> observable bitmask (L part of the image)
KIND = {"Z": "X", "X": "Z"}


def ext_and_logicals(circ, kind):
    if circ == "fig12":
        E = C18.ext(kind)
        return E, E["key_idx"], [tuple(S) for S in C18.load_logicals(kind)]
    from search.experiments.e021.lift21 import label_orders, w11_from_fig12
    from search.experiments.e021.extgen import ext_general
    lab = label_orders(spec(circ))
    E = ext_general(kind, lab[kind])
    E["N"] = E["He"].shape[1]
    key_idx = {E["He"][:, j].tobytes() + E["Le"][:, j].tobytes(): j for j in range(E["N"])}
    return E, key_idx, w11_from_fig12(kind, E)


def groups(circ, basis, R, key_idx):
    c = code()
    noisy = add_noise(build_circuits(spec(circ), c, R)[basis], "sd6", PE).flattened()
    H, L = (np.asarray(c.HZ) % 2, np.asarray(c.LZ) % 2) if basis == "Z" else (np.asarray(c.HX) % 2, np.asarray(c.LX) % 2)
    nm = noisy.num_measurements; n = c.n
    ops = list(noisy)
    idx = max(i for i, op in enumerate(ops) if op.name in ("M", "MX"))
    tq = [t.value for t in ops[idx].targets_copy()]
    assert sorted(tq) == list(range(n))
    pos = {q: nm - n + k for k, q in enumerate(tq)}
    k0 = noisy.num_observables
    aug = noisy.copy()
    rows = [H[i] for i in range(H.shape[0])] + [L[i] for i in range(L.shape[0])]
    for r_i, row in enumerate(rows):
        aug.append("OBSERVABLE_INCLUDE", [stim.target_rec(pos[q] - nm) for q in np.nonzero(row)[0]], k0 + r_i)
    dem = aug.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    nH, nL = H.shape[0], L.shape[0]
    G, Z = {}, {}
    OBS.clear()
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        pr = inst.args_copy()[0]
        dm = 0; hb = np.zeros(nH, np.uint8); lb = np.zeros(nL, np.uint8); ob = np.zeros(k0, np.uint8)
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                dm ^= 1 << t.val
            elif t.is_logical_observable_id():
                v = t.val
                if v < k0: ob[v] ^= 1
                elif v < k0 + nH: hb[v - k0] ^= 1
                else: lb[v - k0 - nH] ^= 1
        assert (ob == lb).all()
        if not hb.any() and not lb.any():
            if dm:
                Z[dm] = Z.get(dm, 0.0) + pr
            continue
        key = hb.tobytes() + lb.tobytes()
        assert key in key_idx, "Table I violated"
        g = G.setdefault(key_idx[key], {})
        g[dm] = g.get(dm, 0.0) + pr
        OBS[(key_idx[key], dm)] = int(sum(1 << k for k in np.nonzero(lb)[0]))
    return G, Z, noisy.num_detectors


def enumerate_solutions(Glist, cap=10 ** 6):
    """Glist: list of dict mask->prob. All choices (one per group) with XOR 0. Returns list of tuples of masks."""
    G = [list(g.keys()) for g in Glist]
    sup = [0] * len(G)
    for i, g in enumerate(G):
        for m in g:
            sup[i] |= m
    order, rem, opened = [], set(range(len(G))), 0
    while rem:
        i = max(rem, key=lambda i: (bin(sup[i] & opened).count("1") - 0.01 * len(G[i]), -i)) if opened else \
            min(rem, key=lambda i: len(G[i]))
        order.append(i); rem.discard(i); opened |= sup[i]
    later = [0] * (len(order) + 1)
    for p in range(len(order) - 1, -1, -1):
        later[p] = later[p + 1] | sup[order[p]]
    layers = [{0: []}]
    for p, i in enumerate(order):
        closed = ~later[p + 1]
        nxt = {}
        for s in layers[-1]:
            for m in G[i]:
                t = s ^ m
                if t & closed:
                    continue
                nxt.setdefault(t, []).append((s, m))
        if not nxt:
            return [], order
        layers.append(nxt)
    if 0 not in layers[-1]:
        return [], order
    # enumerate paths backwards
    sols = []
    def back(p, s, acc):
        if len(sols) >= cap:
            return
        if p == 0:
            sols.append(tuple(acc)); return
        for prev, m in layers[p][s]:
            acc[order[p - 1]] = m
            back(p - 1, prev, acc)
    back(len(order), 0, [None] * len(order))
    return sols, order


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--circ", required=True); ap.add_argument("--basis", required=True)
    ap.add_argument("--mode", default="w11"); ap.add_argument("--R", type=int, nargs="+", default=[4, 5])
    a = ap.parse_args()
    kind = KIND[a.basis]
    E, key_idx, logs = ext_and_logicals(a.circ, kind)
    od = OUT / "lift"; od.mkdir(parents=True, exist_ok=True)
    for R in a.R:
        t0 = time.process_time()
        G, Z, ndet = groups(a.circ, a.basis, R, key_idx)
        terms = {}      # (col, mask) -> id ; zero-image: (-1, mask)
        tprob = []
        def tid(col, m, pr):
            k = (col, m)
            if k not in terms:
                terms[k] = len(tprob); tprob.append(pr)
            return terms[k]
        out_logs = []
        for S in logs:
            gl = [G[j] for j in S] + ([Z] if a.mode == "w11z" else [])
            cols = list(S) + ([-1] if a.mode == "w11z" else [])
            sols, _ = enumerate_solutions(gl)
            for sol in sols:
                out_logs.append(sorted(tid(cols[k], sol[k], gl[k][sol[k]]) for k in range(len(cols))))
        W = 11 if a.mode == "w11" else 12
        arr = np.array(out_logs, dtype=np.int32).reshape(-1, W)
        uniq = np.unique(arr, axis=0) if len(arr) else arr
        tdets, toff, tobs = [], [0], []
        for (col, m), i in sorted(terms.items(), key=lambda kv: kv[1]):
            ds = [b for b in range(m.bit_length()) if (m >> b) & 1]
            tdets += ds; toff.append(len(tdets)); tobs.append(OBS.get((col, m), 0))
        np.savez_compressed(od / f"{a.circ}_{a.basis}_{a.mode}_R{R}.npz", logs=uniq, logq=np.log(np.array(tprob)),
                            nlog_raw=len(arr), ndet=ndet, tdets=np.array(tdets, np.int32),
                            toff=np.array(toff, np.int64), tobs=np.array(tobs, np.int64))
        print(a.circ, a.basis, a.mode, "R", R, "logicals", len(uniq), "(raw", len(arr), ") terms", len(tprob),
              "cpu", round(time.process_time() - t0, 1), flush=True)


if __name__ == "__main__":
    main()
