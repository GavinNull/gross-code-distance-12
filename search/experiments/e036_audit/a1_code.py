"""Audit claim 1 + claim 2: code parameters, chip edges, pair-in-weight-4-logical property.  Own code only."""
import itertools
import json

import numpy as np

from search.experiments.e036_audit.core import (HX_FULL, HZ_FULL, VARIANTS, checks, code_mats, logical_basis, rank,
                                                support)


def min_logical(Hc, Hs):
    n = Hc.shape[1]
    rs = rank(Hs)
    for w in range(1, n + 1):
        for S in itertools.combinations(range(n), w):
            v = np.zeros(n, np.uint8)
            v[list(S)] = 1
            if (Hc @ v % 2).any():
                continue
            if rank(np.vstack([Hs, v])) > rs:
                return w, S


def all_logicals_weight(Hc, Hs, w):
    n = Hc.shape[1]
    rs = rank(Hs)
    out = []
    for S in itertools.combinations(range(n), w):
        v = np.zeros(n, np.uint8)
        v[list(S)] = 1
        if (Hc @ v % 2).any():
            continue
        if rank(np.vstack([Hs, v])) > rs:
            out.append(set(S))
    return out


def main():
    rep = {}
    rep["HX==HZ"] = bool((HX_FULL == HZ_FULL).all())
    rep["row_weights"] = sorted(set(HX_FULL.sum(1).tolist()))
    rep["col_weights"] = sorted(set(HX_FULL.sum(0).tolist()))
    rep["HX_rows"] = ["".join(map(str, r[:9])) + " " + "".join(map(str, r[9:])) for r in HX_FULL]
    rep["full_rank"] = rank(HX_FULL)
    for var in ("bb18", "q1863", "full"):
        HX, HZ = code_mats(var)
        k = 18 - rank(HX) - rank(HZ)
        dX = min_logical(HZ, HX)   # X logical: commutes with Z checks
        dZ = min_logical(HX, HZ)
        same_group = rank(np.vstack([HX, HX_FULL])) == rank(HX) and rank(np.vstack([HZ, HZ_FULL])) == rank(HZ)
        edges = sum(len(support(c)) for c in checks(var))
        r = {"rank_HX": rank(HX), "rank_HZ": rank(HZ), "k": k, "dX": dX[0], "dZ": dZ[0],
             "same_stabilizer_group_as_18_checks": bool(same_group), "n_checks": len(checks(var)),
             "tanner_edges(couplers)": edges, "qubits": 18 + len(checks(var))}
        # claim 2: every pair in every measured check's support lies in a weight-(d) logical of the same type
        if var in ("bb18", "q1863"):
            d = min(dX[0], dZ[0])
            LXw = all_logicals_weight(HZ, HX, 4)
            LZw = all_logicals_weight(HX, HZ, 4)
            bad = []
            for kind, r_ in checks(var):
                Ls = LXw if kind == "X" else LZw   # X-check hook spreads X errors
                sup = support((kind, r_))
                for pr in itertools.combinations(sup, 2):
                    if not any(set(pr) <= Lg for Lg in Ls):
                        bad.append([kind, r_, list(pr)])
            r["n_weight4_X_logicals"] = len(LXw)
            r["n_weight4_Z_logicals"] = len(LZw)
            r["pairs_not_in_weight4_logical"] = len(bad)
            r["pairs_total"] = 15 * len(checks(var))
        rep[var] = r
    # removed checks are redundant for bb18?
    xs, zs = VARIANTS["bb18"]
    rep["bb18_removed_X_in_span"] = [int(i) for i in (2, 8)
                                     if rank(np.vstack([HX_FULL[xs], HX_FULL[i]])) == rank(HX_FULL[xs])]
    rep["bb18_removed_Z_in_span"] = [int(i) for i in (3, 4)
                                     if rank(np.vstack([HZ_FULL[zs], HZ_FULL[i]])) == rank(HZ_FULL[zs])]
    print(json.dumps(rep, indent=1))
    json.dump(rep, open("results/E-036-audit/a1_code.json", "w"), indent=1)


if __name__ == "__main__":
    main()
