"""E-006 method (c): lowest-weight fault configurations on which a decoder fails while the exact MLE succeeds.

Works per sector (decoding is per sector). A sector fault set of w columns is realisable by w circuit faults
(one joint mechanism per column), so the lowest failing column count = the lowest failing fault weight.
Search (decoder priors at --p):
  w=1: every column;  w=2: every pair of columns sharing a detector (exhaustive) + --hop2 random pairs at
  detector-graph distance 2 + --far uniformly random pairs;  w=3 (and w=4 with --w4): random "clustered" sets (each new column
  drawn from the <=2-hop neighbourhood of the previous ones) + uniform random sets, --n3 / --n4 of each.
Every decoder failure is re-decoded by the MLE; examples with ref success are archived (columns, a representative
joint DEM mechanism per column, circuit fault locations) and injection-verified on the noiseless joint circuit.

uv run python -m search.decoders.run_wdec --code bb72 --p 0.001 --n3 200000 --workers 6
"""
from __future__ import annotations

import argparse
import json
import time
from multiprocessing import get_context

import numpy as np
import scipy.sparse as sp

from search.decoders.common import RESULTS, build_model

OUT = RESULTS / "wdec"
_M = {}


def _setup(code, p, s, names):
    key = (code, p, s)
    if key not in _M:
        from search.decoders import decoders as D
        m = build_model(code, p)
        sec = m.sectors[s]
        _M.clear()
        _M[key] = (m, sec, D.make(sec, names), D.make_ref(sec))
    return _M[key]


def neighbours(sec, hops=2):
    H = sec.H.tocsc().astype(np.int32)
    A = (H.T @ H).tocsr()
    A.data[:] = 1
    if hops >= 2:
        A = (A @ A).tocsr()
        A.data[:] = 1
    return A


def decode_sets(args):
    code, p, s, names, sets, seed = args
    m, sec, decs, ref = _setup(code, p, s, names)
    t0 = time.process_time()
    ncol = sec.H.shape[1]
    Hr = sec.H.tocsr()
    res = []
    counts = {nm: 0 for nm in names}
    counts["ref_fail"] = 0
    counts["n"] = len(sets)
    for S in sets:
        e = np.zeros(ncol, np.uint8)
        e[list(S)] ^= 1
        syn = (Hr @ e) % 2
        ob = (sec.L @ e) % 2
        if not syn.any():
            continue
        fl = {}
        for nm, dec in decs.items():
            eh = dec.decode(syn)
            fl[nm] = bool(((sec.L @ eh) % 2 != ob).any())
            counts[nm] += fl[nm]
        if any(fl.values()):
            r = ref.decode(syn, time_limit=300)
            rf = bool(((sec.L @ r.e) % 2 != ob).any()) if r.e is not None else None
            counts["ref_fail"] += bool(rf)
            res.append({"cols": [int(c) for c in S], "fail": fl, "ref_fail": rf, "ref_status": r.status,
                        "W_true": float(sec.weights[list(S)].sum()), "W_ref": r.objective})
    return {"code": code, "s": s, "counts": counts, "hits": res, "cpu": time.process_time() - t0}


def chunks(lst, k):
    for i in range(0, len(lst), k):
        yield lst[i:i + k]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--p", type=float, default=0.001)
    ap.add_argument("--far", type=int, default=20000)
    ap.add_argument("--hop2", type=int, default=50000)
    ap.add_argument("--n3", type=int, default=100000)
    ap.add_argument("--n4", type=int, default=0)
    ap.add_argument("--n5", type=int, default=0)
    ap.add_argument("--n6", type=int, default=0)
    ap.add_argument("--skip12", action="store_true")
    ap.add_argument("--seed", type=int, default=6206)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--decoders", default="bposd,relay5,relay1")
    ap.add_argument("--tag", default=None)
    a = ap.parse_args(argv)
    assert a.workers <= 6
    names = tuple(a.decoders.split(","))
    tag = a.tag or f"{a.code}_p{a.p}"
    OUT.mkdir(parents=True, exist_ok=True)
    m = build_model(a.code, a.p)
    rng = np.random.default_rng(a.seed)
    jobs = []
    meta = {"args": vars(a), "sets": {}}
    for s in "ZX":
        sec = m.sectors[s]
        ncol = sec.H.shape[1]
        A1 = neighbours(sec, 1)
        nb1 = [A1.indices[A1.indptr[i]:A1.indptr[i + 1]] for i in range(ncol)]
        A = neighbours(sec, 2)
        nb = [A.indices[A.indptr[i]:A.indptr[i + 1]] for i in range(ncol)]
        groups = {}
        if not a.skip12:
            groups["w1"] = [(i,) for i in range(ncol)]
            pairs = [(i, int(j)) for i in range(ncol) for j in nb1[i] if j > i]
            hop2 = []
            for _ in range(a.hop2):
                i = int(rng.integers(ncol))
                j = int(rng.choice(nb[i]))
                if j != i:
                    hop2.append(tuple(sorted((i, j))))
            far = [tuple(sorted(rng.choice(ncol, 2, replace=False).tolist())) for _ in range(a.far)]
            groups["w2_adjacent_all"] = pairs
            groups["w2_hop2_sample"] = hop2
            groups["w2_far"] = far
        for w, n in ((3, a.n3), (4, a.n4), (5, a.n5), (6, a.n6)):
            if n <= 0:
                continue
            cl = []
            for _ in range(n):
                S = [int(rng.integers(ncol))]
                while len(S) < w:
                    base = S[int(rng.integers(len(S)))]
                    c = int(rng.choice(nb[base]))
                    if c not in S:
                        S.append(c)
                cl.append(tuple(sorted(S)))
            groups[f"w{w}_clustered"] = cl
            groups[f"w{w}_uniform"] = [tuple(sorted(rng.choice(ncol, w, replace=False).tolist()))
                                       for _ in range(n // 10)]
        for g, L in groups.items():
            meta["sets"][f"{s}_{g}"] = len(L)
            for ch in chunks(L, 4000):
                jobs.append((g, (a.code, a.p, s, names, ch, a.seed)))
    print("jobs", len(jobs), meta["sets"], flush=True)
    t0 = time.time()
    agg = {}
    hits = []
    cpu = 0.0
    with get_context("spawn").Pool(a.workers) as pool:
        for (g, _), r in zip(jobs, pool.imap(decode_sets, [j for _, j in jobs])):
            key = f"{r['s']}_{g}"
            c = agg.setdefault(key, {})
            for k, v in r["counts"].items():
                c[k] = c.get(k, 0) + v
            for h in r["hits"]:
                h["group"] = key
            hits += r["hits"]
            cpu += r["cpu"]
            print(key, r["counts"], f"cpu {r['cpu']:.0f}s total {cpu/3600:.2f}h wall {time.time()-t0:.0f}", flush=True)
    meta["counts"] = agg
    meta["cpu_hours"] = cpu / 3600
    (OUT / f"{tag}.json").write_text(json.dumps({"meta": meta, "hits": hits}, indent=1))
    print("done", tag, f"cpu {cpu/3600:.3f}h", "hits", len(hits))


if __name__ == "__main__":
    main()
