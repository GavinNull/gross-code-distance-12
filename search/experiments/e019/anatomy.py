"""E-019: anatomy of a below-d witness. Every fault of the (single-round) witness is propagated (projected Pauli
part) to the end of its round (just before the M layer); report its left-qubit support (= data error on the
end-cycle code C~_c entering the next round) and right-qubit support (flips of round-r records). The total left
error must be an end-cycle logical of weight >= d_end; 'amplification' = faults whose left weight is >= 2.
usage: uv run python -m search.experiments.e019.anatomy <key> <basis>
"""
from __future__ import annotations

import json
import sys

import numpy as np

from search.experiments.e019.common import get_code, logicals, memory, spec

RES = "/Users/ephemeral/Desktop/qec-ai-search/results/E-019-morphing-family"


def main(key, basis):
    s = json.load(open(f"{RES}/solve_{key}_{basis}_T4.json"))
    wit = s["injections"]["dfs_witness"]
    name, hom, v = key.split("_")
    code = get_code(name)
    N = code.N
    gates, meas, _, _ = spec(code, hom, v)
    C = memory(code, gates, meas, 4, basis)
    want = "X" if basis == "Z" else "Z"
    tot = np.zeros(2 * N, np.uint8)
    per = []
    for f in wit["faults"]:
        r, li, kind = f["round"], f["layer"], f["kind"]
        e = np.zeros(2 * N, np.uint8)
        for q, p in zip(f["qubits"], f["pauli"]):
            if p in (want, "Y"):
                e[q] ^= 1
        # measurement flip before M: equivalent to a Pauli on the measured qubit just before M
        start = li if kind == "meas" else li + 1
        mlayer = 8 * (r - 1) + 7
        for L in range(start, mlayer):
            ops, tg = C.layers[L]
            for op, ts in ops:
                if op == "CX":
                    for (c, t) in ts:
                        if basis == "Z":
                            e[t] ^= e[c]
                        else:
                            e[c] ^= e[t]
                elif op in ("R", "RX"):
                    e[list(ts)] = 0
        left = [int(q) for q in np.nonzero(e[:N])[0]]
        right = [int(q) for q in np.nonzero(e[N:])[0] + N]
        per.append(dict(kind=kind, layer_in_round=li % 8, pauli=f["pauli"], left_weight=len(left),
                        right_weight=len(right)))
        tot ^= e
    c = (s["basis"] and 0) if False else 0
    # end-cycle code after round 1 (first_c = 0 -> contraction 0)
    z = np.load(f"{RES}/ec/{key}_c0.npz")
    Hs, Ho = (z["HX"], z["HZ"]) if want == "X" else (z["HZ"], z["HX"])
    Lo = logicals(Ho, Hs)
    tl = tot[:N]
    out = dict(key=key, basis=basis, weight=len(per), per_fault=per,
               total_left_weight=int(tl.sum()), total_right_flips=int(tot[N:].sum()),
               left_is_ec_codeword=bool(not np.any((Ho.astype(int) @ tl) % 2)),
               left_is_ec_logical=bool(np.any((Lo.astype(int) @ tl) % 2)),
               n_amplifying=sum(1 for p in per if p["left_weight"] >= 2))
    print(json.dumps(out))
    json.dump(out, open(f"{RES}/anatomy_{key}_{basis}.json", "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
