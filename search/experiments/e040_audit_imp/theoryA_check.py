"""E-040 impossibility audit: spot checks of theory A (research/theory/2026-10-29-A-period-lower-bound.md).
 (a) table (iii) pair witnesses (results/theoryA/pairs_*.json): weight d, contain the pair's qubits of check 0,
     nontrivial logical of the right type;
 (b) Theorem 1 / Lemma F at P = 8 (and how far it reaches at P = 9, 10): for every canonical legal schedule build the
     explicit Lemma F witness (pair hook S2 = last two labels, or S4 with T = first two labels, on either side, + the
     other d-2 qubits of the pair logical as data faults after their last read, hook instance j in -4..4) and test it
     with the independent bulk test; weight d-1;
 (c) Lemma 1.1: the nine sums a_k + b_l are distinct (overlap structure);
 (d) period lemma: u11 / c11 signatures absent from T(8..10), u11's G with the stated other orders present at P = 8.
   PYTHONPATH=.:tests uv run python -m search.experiments.e040_audit_imp.theoryA_check
"""
import json
import sys

import numpy as np

from search.experiments.e040_audit_imp.bulk_a import applies, readers
from search.experiments.e040_audit_imp.codes_a import POLY, code, is_nontrivial_logical
from search.experiments.e040_audit_imp.enum_a import sig_keys

LAB = ["A1", "A2", "A3", "B1", "B2", "B3"]
OUT = "results/E-040-audit-imp"


def pairs_ok(name):
    C = code(name)
    res = {}
    for side in "XZ":
        J = json.load(open(f"results/theoryA/pairs_{name}_{side}.json"))
        TH = C["T"][side]
        good = 0
        for key, v in J.items():
            if len(key) != 4:
                continue
            labs = [LAB.index(key[0:2]), LAB.index(key[2:4])]
            w = v.get("wit")
            if w is None:
                continue
            e = np.zeros(C["NQ"], np.uint8)
            e[w] = 1
            ok = len(set(w)) == C["d"] and all(int(TH[0][m]) in w for m in labs) and is_nontrivial_logical(C, side, e)
            good += ok
        res[side] = good
    return res


def flat_cover(name, P, maxrows=None):
    C = code(name)
    z = np.load(f"{OUT}/canon_P{P}.npz")
    TX, TZ = z["TX"].astype(np.int64), z["TZ"].astype(np.int64)
    if P >= 10:
        _, idx = np.unique(sig_keys(TX, TZ, P), return_index=True)
        TX, TZ = TX[idx], TZ[idx]
    n = len(TX)
    killed = np.zeros(n, bool)
    wit = {s: json.load(open(f"results/theoryA/pairs_{name}_{s}.json")) for s in "XZ"}
    for side in "XZ":
        tH, tR = (TX, TZ) if side == "X" else (TZ, TX)
        rd = readers(C, side)
        TH = C["T"][side]
        oh = np.argsort(tH, 1)
        # last read label of each data qubit (per row): reader label with the largest reader time
        for hn in ("S2", "P2"):
            for code_o in np.unique((oh * 6 ** np.arange(6)).sum(1)):
                rows = np.flatnonzero(((oh * 6 ** np.arange(6)).sum(1) == code_o) & ~killed)
                if len(rows) == 0:
                    continue
                o = oh[rows[0]]
                S = sorted(o[4:]) if hn == "S2" else sorted(o[2:])
                T = sorted(o[4:]) if hn == "S2" else sorted(o[:2])
                key = "".join(LAB[m] for m in sorted(T))
                L = wit[side][key]["wit"]
                Tq = {int(TH[0][m]) for m in T}
                assert Tq <= set(L)
                rest = [q for q in L if q not in Tq]
                # data fault after the last read of q: label differs per row -> group rows by these labels
                lastlab = np.stack([np.array([b for _, b in rd[q]])[np.argmax(tR[rows][:, [b for _, b in rd[q]]], 1)]
                                    for q in rest], 1)
                kk = (lastlab * 6 ** np.arange(len(rest))).sum(1)
                for g in np.unique(kk):
                    sub = rows[kk == g]
                    labs = lastlab[np.flatnonzero(kk == g)[0]]
                    data = [("d", q, int(b), 0) for q, b in zip(rest, labs)]
                    for j in range(-4, 5):
                        f = data + [("h", 0, S, j)]
                        m = applies(C, side, f, tH[sub], tR[sub], P, rd)
                        killed[sub[m]] = True
                        sub = sub[~m]
                        if len(sub) == 0:
                            break
    return {"code": name, "P": P, "rows": n, "sig_reps": P >= 10, "killed_by_flat_pair_hook_weight_d-1": int(killed.sum())}


def lemma11(name):
    l, m, A, B, *_ = POLY[name]
    s = {((a[0] + b[0]) % l, (a[1] + b[1]) % m) for a in A for b in B}
    return len(s) == 9


def times_from_spec(name, path):
    C = code(name)
    s = json.load(open(path))
    P = s["period"]
    t = {}
    for ty, key in (("X", "x_checks"), ("Z", "z_checks")):
        for i, ch in enumerate(s[key]):
            v = [None] * 6
            for q, L in ch["cnots"]:
                lab = list(C["T"][ty][i]).index(q)
                v[lab] = ch["prep"] + (L - ch["prep"]) % P
            if i == 0:
                t[ty] = v
            else:
                assert [(x - y) for x, y in zip(v, t[ty])] == [0] * 6, "not translation invariant"
    return t["X"], t["Z"], P


def canon(tX, tZ, P):
    s = min(tX)
    tX = [v - s for v in tX]
    tZ = [v - s for v in tZ]
    k = (tX[0] - tZ[3]) // P
    return tX, [v + k * P for v in tZ]


def main():
    out = {"lemma11": {n: lemma11(n) for n in POLY}, "pairs_ok(of 15)": {n: pairs_ok(n) for n in POLY}}
    print(json.dumps(out), flush=True)
    for n, path in (("gross", "search/experiments/e032/u11_spec.json"), ("bb90", "search/experiments/e030/c11_spec.json")):
        tX, tZ, P = times_from_spec(n, path)
        tX, tZ = canon(tX, tZ, P)
        ox, oz = np.argsort(tX), np.argsort(tZ)
        G = np.array([(tX[i] - tZ[3 + j]) // P for i in range(3) for j in range(3)])
        key = sig_keys(np.array([tX]), np.array([tZ]), P, norm=True)[0]
        pres = {}
        for Q in (8, 9, 10):
            zz = np.load(f"{OUT}/canon_P{Q}.npz")
            pres[Q] = bool(np.isin(key, sig_keys(zz["TX"], zz["TZ"], Q, norm=True)))
        print(json.dumps({"circuit": path, "P": P, "ox": [LAB[i] for i in ox], "oz": [LAB[i] for i in oz],
                          "G": (G - G.min()).reshape(3, 3).tolist(), "signature_present_at": pres}), flush=True)
        if n == "gross":
            # theory A: same G with X order B2B3A1A2A3B1, Z order B1A1A2A3B2B3 is realisable at P = 8
            zz = np.load(f"{OUT}/canon_P8.npz")
            TX8, TZ8 = zz["TX"].astype(int), zz["TZ"].astype(int)
            want_ox = [LAB.index(x) for x in ("B2", "B3", "A1", "A2", "A3", "B1")]
            want_oz = [LAB.index(x) for x in ("B1", "A1", "A2", "A3", "B2", "B3")]
            G8 = np.stack([np.floor_divide(TX8[:, i] - TZ8[:, 3 + j], 8) for i in range(3) for j in range(3)], 1)
            G8 = G8 - G8.min(1, keepdims=True)
            hit = ((np.argsort(TX8, 1) == want_ox).all(1) & (np.argsort(TZ8, 1) == want_oz).all(1)
                   & (G8 == (G - G.min())).all(1))
            print(json.dumps({"u11_G_with_other_orders_at_P8": int(hit.sum())}), flush=True)
    for n in POLY:
        for P in (8, 9):
            print(json.dumps(flat_cover(n, P)), flush=True)


if __name__ == "__main__":
    main()
