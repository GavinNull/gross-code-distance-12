"""c1: legality, coupler set vs Kunlun (Fig. S3 spec of E-036, lead-checked), determinism, per-check injection.
usage: uv run python -m search.experiments.e041_audit.c1_legal"""
import json
import os

import numpy as np

from search.experiments.e041_audit import core as C

SPEC = "search/experiments/e041/bb18_w9_d4_spec.json"
OUT = "results/E-041-audit"


def kunlun_path():
    from search.experiments.e036.common import kunlun_spec
    os.makedirs(OUT, exist_ok=True)
    p = f"{OUT}/kunlun_spec.json"
    with open(p, "w") as f:
        json.dump(kunlun_spec("bb18").to_dict(), f)
    return p


def edges(S):
    return {(k, q) for k, (pi, mu, T) in S["sched"].items() for q in T}


def layer_table(S):
    P = S["P"]
    rows = {}
    for k, (pi, mu, T) in S["sched"].items():
        rows[k] = dict(prep=pi % P, meas=mu % P, cnot_layers=sorted(t % P for t in T.values()),
                       span=(min(T.values()), max(T.values())), window=mu - pi)
    per_layer = {l: dict(prep=[], meas=[], cx=0) for l in range(P)}
    for k, (pi, mu, T) in S["sched"].items():
        per_layer[pi % P]["prep"].append(f"{k[0]}{k[1]}")
        per_layer[mu % P]["meas"].append(f"{k[0]}{k[1]}")
        for t in T.values():
            per_layer[t % P]["cx"] += 1
    return rows, per_layer


def inject_test(S, basis_err, R=3, Pst=None):
    """noiseless; put a single Pauli on data q just before layer Pst (no data CNOT there); the detectors that fire
    must be exactly D(k, 1) for the opposite-type measured checks k containing q."""
    Pst = Pst or S["P"]
    mem = "Z" if basis_err == "X" else "X"
    bad = 0
    for q in range(C.ND):
        c, dmap = C.circuit(S, mem, R, inject=[(Pst, "pre", q, basis_err)], Pst=Pst)
        s = c.compile_detector_sampler()
        d, o = s.sample(1, separate_observables=True)
        fired = set(np.nonzero(d[0])[0].tolist())
        want = {dmap[(k, 1)] for k in C.KS if k[0] == mem and q in C.SUPP[k]}
        if fired != want:
            bad += 1
    return bad


def main():
    S = C.load(SPEC)
    K = C.load(kunlun_path())
    res = {}
    res["legal_problems_w9"] = C.legal(S)
    res["legal_problems_kunlun"] = C.legal(K)
    # any data CNOT at a layer that wraps? which layers have CX / meas / prep
    rows, per_layer = layer_table(S)
    res["per_layer"] = per_layer
    res["rows"] = {f"{k[0]}{k[1]}": v for k, v in rows.items()}
    eS, eK = edges(S), edges(K)
    tanner = {(k, q) for k in C.KS for q in C.SUPP[k]}
    res["edges"] = dict(w9=len(eS), kunlun=len(eK), equal=eS == eK, equal_tanner=eS == tanner)
    # data qubit: at most one gate per absolute layer is asserted inside circuit(); also ancilla
    det = {}
    for reset in (True, False):
        for basis in "ZX":
            for R in (1, 2, 3, 5):
                c, _ = C.circuit(S, basis, R, p=1e-3, reset=reset)
                c.detector_error_model(decompose_errors=False)   # raises if any detector/obs is nondeterministic
                c0, _ = C.circuit(S, basis, R, p=0.0, reset=reset)
                d, o = c0.compile_detector_sampler().sample(200, separate_observables=True)
                det[f"{basis}{R}{'r' if reset else 'n'}"] = bool(not d.any() and not o.any())
    res["deterministic_and_noiseless_zero"] = all(det.values())
    res["inject_bad"] = dict(w9_X=inject_test(S, "X"), w9_Z=inject_test(S, "Z"),
                             w9_P10_X=inject_test(S, "X", Pst=10), w9_P10_Z=inject_test(S, "Z", Pst=10),
                             kunlun_X=inject_test(K, "X"), kunlun_Z=inject_test(K, "Z"))
    # negative control: break determinism by swapping two CNOT times of X0 so that an X/Z parity becomes odd
    import copy
    bad_nondet = 0
    tried = 0
    k0 = ("X", 0)
    pi, mu, T = S["sched"][k0]
    qs = sorted(T)
    for a in range(6):
        for b in range(a + 1, 6):
            S2 = copy.deepcopy(S)
            T2 = dict(T)
            T2[qs[a]], T2[qs[b]] = T[qs[b]], T[qs[a]]
            S2["sched"][k0] = (pi, mu, T2)
            if C.legal(S2):
                continue
            try:
                c, _ = C.circuit(S2, "Z", 2, p=1e-3)
            except AssertionError:
                continue
            tried += 1
            try:
                c.detector_error_model(decompose_errors=False)
                cx, _ = C.circuit(S2, "X", 2, p=1e-3)
                cx.detector_error_model(decompose_errors=False)
            except ValueError:
                bad_nondet += 1
    res["swap_control"] = dict(tried_layer_legal_swaps=tried, nondeterministic=bad_nondet)
    print(json.dumps(res, indent=1, default=str))
    with open(f"{OUT}/c1_legal.json", "w") as f:
        json.dump(res, f, indent=1, default=str)


if __name__ == "__main__":
    main()
