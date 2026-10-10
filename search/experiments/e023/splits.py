"""E-023 stage C: structural failure cores from low-weight logicals, tested on the actual decoders.  experimenter.

For every found (symmetry-closed) undetectable logical L of weight W <= --wmax and every subset S ⊂ L with
--tmin <= |S| <= --tmax:  S and L\\S have the same syndrome and differ by a nontrivial logical, so ANY decoder fails
on at least one of them.
  ideal(S)   : 1 if logodds(L\\S) > logodds(S) for some found L (MLE prefers the complement), 1/2 on a tie, else 0
               (evaluated with the DEM priors at p = 1e-3 and, rescaled, at p = 1e-4) -- a lower bound on the
               MLE failure (only found complements are used).
  dec(S)     : decoder D (fixed priors = DEM at P_DEC) actually decoded on syndrome(S), compared with logical(S).
Subsets are Horvitz-Thompson subsampled per size t (deterministic hash of S, ~--cap kept per size and sector).

    PYTHONPATH=. uv run python -m search.experiments.e023.splits --prob m54_paper --model sd6 --tmax 4 --wmax 8
"""
from __future__ import annotations

import argparse
import itertools
import json
import time
import zlib
from multiprocessing import get_context

import numpy as np

from search.experiments.e023.common import OUT, P_DEC, make_decoder, sectors
from search.experiments.e023.fixedweight import decode_one


def build_cores(sec, logicals, tmin, tmax, wmax, cap, seed=0, wmin=1):
    """All subsets S (tmin <= |S| <= tmax) of found logicals of weight <= wmax, Horvitz-Thompson subsampled per size t
    with a deterministic hash (inclusion prob rho_t, the same for every source logical), rho_t chosen so that about
    `cap` subsets of size t are kept (counting with multiplicity).  Returns {S: [logodds S, max logodds complement,
    |complement| of the best, HT weight 1/rho_t]}."""
    from math import comb
    lr = np.log(sec.q) - np.log1p(-sec.q)          # log odds at P_DEC
    logicals = [L for L in logicals if wmin <= len(L) <= wmax]
    rho = {}
    for t in range(tmin, tmax + 1):
        tot = sum(comb(len(L), t) for L in logicals if len(L) > t)
        rho[t] = 1.0 if tot <= cap else cap / tot
    best = {}
    for L in logicals:
        W = len(L)
        tot = lr[list(L)].sum()
        for t in range(tmin, min(tmax, W - 1) + 1):
            thr = rho[t] * 2 ** 32
            for S in itertools.combinations(L, t):
                if rho[t] < 1 and zlib.crc32(np.array(S, np.int64).tobytes(), seed) >= thr:
                    continue
                a = lr[list(S)].sum()
                c = tot - a
                # ideal non-minimality: some proper subset S' of S already fails against this same L
                nonmin = False
                for k in range(1, t):
                    for Sp in itertools.combinations(S, k):
                        ap_ = lr[list(Sp)].sum()
                        if tot - ap_ > ap_ + 1e-9:
                            nonmin = True
                            break
                    if nonmin:
                        break
                prev = best.get(S)
                if prev is None:
                    best[S] = [a, c, W - t, 1.0 / rho[t], nonmin]
                else:
                    if c > prev[1]:
                        prev[1] = c
                        prev[2] = W - t
                    prev[4] = prev[4] or nonmin
    return best, rho


def _work(args):
    prob, model, si, chunk, names = args
    secs = sectors(prob, model, P_DEC)
    sec = secs[si]
    decs = {nm: make_decoder(sec, nm) for nm in names}
    Hc = sec.H.tocsc()
    out = np.zeros((len(chunk), len(names)), bool)
    t0 = time.process_time()
    for i, S in enumerate(chunk):
        e = np.zeros(sec.ncol, np.uint8)
        e[list(S)] = 1
        syn = ((Hc @ e) % 2).astype(np.uint8)
        tr = (sec.L @ e) % 2
        for k, nm in enumerate(names):
            out[i, k] = bool((decode_one(sec, decs[nm], syn, nm) != tr).any())
    return si, out, time.process_time() - t0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--prob", required=True)
    ap.add_argument("--model", default="sd6")
    ap.add_argument("--tmin", type=int, default=1)
    ap.add_argument("--tmax", type=int, default=4)
    ap.add_argument("--wmax", type=int, default=8)
    ap.add_argument("--wmin", type=int, default=1)
    ap.add_argument("--tag", default="")
    ap.add_argument("--cap", type=int, default=1500, help="approx. number of size-t subsets decoded per sector")
    ap.add_argument("--decoders", default="bposd,relay")
    ap.add_argument("--src", default=None, help="lowweight json name (default = prob)")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args(argv)
    assert a.workers <= 3
    names = tuple(a.decoders.split(",")) if a.decoders else ()
    D = json.loads((OUT / "lowweight" / f"{a.src or a.prob}.json").read_text())
    secs = sectors(a.prob, a.model, P_DEC)
    res = {"args": vars(a), "sectors": {}}
    jobs, cores = [], {}
    for si, sec in enumerate(secs):
        cur = D["sectors"][sec.label]
        keys = [(tuple(k[0]), tuple(k[1])) for k in cur["keys"]]
        assert keys == list(sec.keys), "column keys differ between search model and this model"
        logs = cur.get("closed", cur["logicals"])
        best, rho = build_cores(sec, logs, a.tmin, a.tmax, a.wmax, a.cap, wmin=a.wmin)
        res["sectors"].setdefault(sec.label, {})["rho"] = rho
        Ss = list(best)
        cores[si] = (Ss, best)
        step = max(200, len(Ss) // (3 * a.workers) + 1)
        for i in range(0, len(Ss), step):
            if names:
                jobs.append((a.prob, a.model, si, Ss[i:i + step], names))
        print(sec.label, "subsets to decode", len(Ss), flush=True)
    t0 = time.time()
    cpu = 0.0
    outs = {si: [] for si in cores}
    with get_context("spawn").Pool(a.workers) as pool:
        for si, o, c in pool.imap(_work, jobs):
            outs[si].append(o)
            cpu += c
    for si, sec in enumerate(secs):
        Ss, best = cores[si]
        F = np.concatenate(outs[si]) if outs[si] else np.zeros((0, len(names)), bool)
        tmax = a.tmax
        arr = np.full((len(Ss), tmax), -1, np.int32)
        for i, S in enumerate(Ss):
            arr[i, :len(S)] = S
        A = np.array([best[S][0] for S in Ss])
        C = np.array([best[S][1] for S in Ss])
        nc = np.array([best[S][2] for S in Ss])
        size = np.array([len(S) for S in Ss])
        ht = np.array([best[S][3] for S in Ss])
        nonmin = np.array([best[S][4] for S in Ss], bool)
        # ideal at 1e-3 and rescaled to 1e-4 (each column's log-odds shifts by ~log(0.1) per element)
        ideal3 = np.where(C > A + 1e-9, 1.0, np.where(np.abs(C - A) <= 1e-9, 0.5, 0.0))
        A4, C4 = A + size * np.log(0.1), C + nc * np.log(0.1)
        ideal4 = np.where(C4 > A4 + 1e-9, 1.0, np.where(np.abs(C4 - A4) <= 1e-9, 0.5, 0.0))
        np.savez_compressed(OUT / "splits" / f"{a.prob}_{a.model}_{sec.label}{a.tag}.npz", S=arr, size=size, ht=ht,
                            ideal3=ideal3, ideal4=ideal4, dec=F, nonmin=nonmin, names=np.array(names), logodds=A)
        summ = {"n_subsets": len(Ss), "rho": res["sectors"][sec.label]["rho"]}
        for t in sorted(set(size.tolist())):
            m = size == t
            summ[str(t)] = {"n": int(m.sum()), "ideal3_fail": float((ideal3[m] * ht[m]).sum()),
                            "ideal4_fail": float((ideal4[m] * ht[m]).sum()),
                            **{f"{nm}_fail": float((F[m, k] * ht[m]).sum()) for k, nm in enumerate(names)}}
        res["sectors"][sec.label] = summ
        print(a.prob, a.model, sec.label, json.dumps(summ), flush=True)
    res["cpu"] = cpu
    res["wall"] = time.time() - t0
    (OUT / "splits" / f"{a.prob}_{a.model}_summary{a.tag}.json").write_text(json.dumps(res, indent=1))
    print(f"cpu {cpu:.0f}s wall {time.time() - t0:.0f}s")


if __name__ == "__main__":
    (OUT / "splits").mkdir(parents=True, exist_ok=True)
    main()
