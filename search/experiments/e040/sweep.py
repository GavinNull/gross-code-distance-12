"""E-040 sweep: for one (code, P, kind) and weight bound W, find for every sector signature of T(P) a bulk witness of
weight <= W (finder: orbit representatives of the minimum-weight extended-logical list of the order's type, lifted
with measurement flips), transferring every new witness to all uncovered sector signatures (vec.test).

Sector signature (kind X): (sigma_X, sigma_Z|A, sigma_Z|B, G) -- the X-sector bulk model depends only on it;
kind Z: (sigma_Z, sigma_X|A, sigma_X|B, G).

    PYTHONPATH=.:tests uv run python -m search.experiments.e040.sweep --code bb90 --P 8 --kind X --W 9
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np

from search.experiments.e040 import vec
from search.experiments.e040.bulk import Sector
from search.experiments.e040.codes import MOD, OUT
from search.experiments.e040.enum import norm_row
from search.experiments.e040.finder import lift, realisations
from search.experiments.e040.lists import orbit_reps, type_rep


def rk(o, labs):
    return tuple(l for l in o if l in labs)


def sector_key(row, kind):
    oh, orr = (row["ox"], row["oz"]) if kind == "X" else (row["oz"], row["ox"])
    return (tuple(oh), rk(orr, (0, 1, 2)), rk(orr, (3, 4, 5)), tuple(row["G"]))


def load_rows(P):
    rows = json.loads((OUT / f"sigs_P{P}.json").read_text())
    for r in rows:
        r["tx"], r["tz"] = norm_row(r["tx"], r["tz"], P)
    return rows


def groups(P, kind):
    rows = load_rows(P)
    g = {}
    for i, r in enumerate(rows):
        g.setdefault(sector_key(r, kind), []).append(i)
    keys = sorted(g)
    return rows, keys, g


def hr(row, kind):
    return (row["tx"], row["tz"]) if kind == "X" else (row["tz"], row["tx"])


_PL = {}


def pairhook(code, kind, S, real, W, full):
    """lemma F / F' family: one hook on check 0 whose data set D is a suffix of the order, plus the data columns of
    L xor D for a weight-d logical L containing the hook's (or its complement's) qubits (pairlog_*.json)."""
    key = (code, kind)
    if key not in _PL:
        pth = OUT / f"pairlog_{code}_{kind}.json"
        _PL[key] = json.loads(pth.read_text()) if pth.exists() else {}
    if not _PL[key]:
        return None
    H, L = S.H, S.L

    def k_of(qs):
        v = np.zeros(S.NQ, np.uint8)
        v[list(qs)] = 1
        return (H @ v % 2).astype(np.uint8).tobytes() + (L @ v % 2).astype(np.uint8).tobytes()

    supp = {int(S.TH[0][m]) for m in range(6)}
    cands = []
    for Sx in S.suffixes():
        Dh = {int(S.TH[0][m]) for m in Sx}
        for lab in (Sx, frozenset(range(6)) - Sx):
            for Lq in _PL[key].get("".join(map(str, sorted(lab))), []):
                for base in (set(Lq), set(Lq) ^ supp):
                    rest = base ^ Dh
                    x = [k_of(Dh)] + [k_of([q]) for q in sorted(rest)]
                    if len(x) <= W and len(set(x)) == len(x) and all(k in real for k in x):
                        cands.append(x)
    cands.sort(key=len)
    for x in cands:
        f = lift(S, real, x, W - len(x), full=full)
        if f is not None:
            return f
    return None


def find(code, kind, row, P, W, pairs=0, full=False, onlypair=False):
    """minimum-weight witness found (weight from d_ext up to W), or None."""
    tX, tZ = row["tx"], row["tz"]
    S = Sector(code, kind, tX, tZ, P)
    trep = type_rep(code, S.order)
    dext, reps = orbit_reps(code, kind, trep)
    lists = {dext: reps}
    for w in range(dext + 1, W + 1):
        if (OUT / f"list{w}_{code}_{kind}_{MOD[code].name(trep)}.pkl").exists():
            lists[w] = orbit_reps(code, kind, trep, tag=f"list{w}")[1]
    real = realisations(S)
    f = pairhook(code, kind, S, real, W, False)
    if f is None:
        f = pairhook(code, kind, S, real, W, True)
    if f is not None or onlypair:
        return S, f, dext
    for w in range(dext, W + 1):
        for lw in sorted(lists):
            if lw > w:
                break
            for x in lists[lw]:
                f = lift(S, real, x, w - len(x), full=full)
                if f is not None:
                    return S, f, dext
    if pairs:
        # generalised Lemma 2 with one cancelling pair: x + [j, j] (j any column whose realisations meet x's checks)
        tc = {k: {c for _, ds in real[k] for c, _ in ds} for k in real}
        for w in range(dext + 2, W + 1):
            for lw in sorted(lists):
                if lw > w - 2:
                    break
                for x in lists[lw]:
                    cx = set().union(*(tc[k] for k in x))
                    for j in real:
                        if tc[j] & cx:
                            f = lift(S, real, list(x) + [j, j], w - len(x) - 2, full=full)
                            if f is not None:
                                return S, f, dext
    return S, None, dext


def to_json(f):
    return [[sorted(int(v) for v in y) if isinstance(y, frozenset) else (int(y) if not isinstance(y, str) else y) for y in x] for x in f]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--kind", required=True)
    ap.add_argument("--W", type=int, required=True)
    ap.add_argument("--max_sec", type=float, default=1e9)
    ap.add_argument("--tag", default="")
    ap.add_argument("--pairs", type=int, default=0)
    ap.add_argument("--onlypair", type=int, default=0)
    ap.add_argument("--rows", default="", help="explicit (normalised) rows file instead of all sector signatures")
    ap.add_argument("--full", type=int, default=0, help="complete anchor window in the lift DFS (slower)")
    ap.add_argument("--pool", nargs="*", default=[], help="witness jsonl files tested first (transfer only)")
    a = ap.parse_args()
    t0 = time.time()
    if a.rows:
        reps = json.loads((OUT / a.rows).read_text())
        keys = [json.dumps([r["tx"], r["tz"]]) for r in reps]
    else:
        rows, keys, g = groups(a.P, a.kind)
        reps = [rows[g[k][0]] for k in keys]
    tH = np.array([hr(r, a.kind)[0] for r in reps], np.int64)
    tR = np.array([hr(r, a.kind)[1] for r in reps], np.int64)
    n = len(keys)
    cover = np.full(n, -1)
    wt = np.full(n, 99)
    wits = []
    unres = []
    tag = a.tag or f"sweep_{a.code}_P{a.P}_{a.kind}_W{a.W}"
    fw = open(OUT / f"{tag}_witnesses.jsonl", "w")
    S0 = Sector(a.code, a.kind, reps[0]["tx"], reps[0]["tz"], a.P)
    nfind = 0
    for pf in a.pool:
        for l in open(pf):
            w = json.loads(l)
            if w["weight"] > a.W:
                continue
            f = [tuple(frozenset(y) if isinstance(y, list) else y for y in x) for x in w["faults"]]
            m = vec.test(S0, f, tH, tR, a.P)
            newly = m & ((cover == -1) | ((cover >= 0) & (wt > len(f))))
            if not newly.any():
                continue
            k = len(wits)
            wits.append(f)
            cover[newly] = k
            wt[newly] = len(f)
            fw.write(json.dumps({"k": k, "found_on": int(np.flatnonzero(m)[0]), "weight": len(f), "dext": w.get("dext"),
                                 "covers": int(newly.sum()), "faults": to_json(f), "from_pool": pf}) + "\n")
    print(json.dumps({"pool_witnesses": len(wits), "covered": int((cover >= 0).sum()), "n": n}), flush=True)
    for i in range(n):
        if cover[i] >= 0:
            continue
        if time.time() - t0 > a.max_sec:
            break
        S, f, dext = find(a.code, a.kind, reps[i], a.P, a.W, a.pairs, full=bool(a.full), onlypair=bool(a.onlypair))
        nfind += 1
        if f is None:
            cover[i] = -2
            unres.append(i)
            continue
        k = len(wits)
        wits.append(f)
        m = vec.test(S0, f, tH, tR, a.P)
        assert m[i], "witness does not pass its own row in vec.test"
        newly = m & ((cover == -1) | ((cover >= 0) & (wt > len(f))))
        cover[newly] = k
        wt[newly] = len(f)
        fw.write(json.dumps({"k": k, "found_on": i, "weight": len(f), "dext": dext, "covers": int(newly.sum()),
                             "faults": to_json(f)}) + "\n")
        fw.flush()
        if nfind % 50 == 0:
            print(json.dumps({"i": i, "n": n, "finds": nfind, "wits": len(wits), "covered": int((cover >= 0).sum()),
                              "unres": len(unres), "sec": round(time.time() - t0)}), flush=True)
    fw.close()
    res = {"code": a.code, "P": a.P, "kind": a.kind, "W": a.W, "sector_sigs": n, "finds": nfind,
           "witnesses": len(wits), "covered": int((cover >= 0).sum()), "unresolved": len(unres),
           "not_reached": int((cover == -1).sum()),
           "weight_hist": {int(w): int((wt == w).sum()) for w in np.unique(wt[cover >= 0])},
           "sec": round(time.time() - t0, 1)}
    np.savez(OUT / f"{tag}.npz", cover=cover, wt=wt, keys=np.array([json.dumps(k) for k in keys]))
    print(json.dumps(res), flush=True)
    with open(OUT / "sweep_summary.jsonl", "a") as f:
        f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
