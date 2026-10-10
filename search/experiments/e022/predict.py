"""E-022: end-cycle distances and morphing-extended-code distances for any (registered) family member.

  enddist <key ...>          exact d~ of both end-cycle codes, both error types (adfs + K-translation orbits)
  ext <key> <basis> <half>   exact distance of the morphing extended code (start view), half = full|exp|con;
                             exhaustive search at W <= d~ - 1, descending; if nothing below d~, d = d~ (a minimum
                             logical of C~_p made of start data errors is undetectable, Lemma 1 in the journal)
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

from search.experiments.e019 import common
from search.experiments.e019.dfsrun import min_weight, orbits, perm_ok, run_all_cases, write_inst
from search.experiments.e022.ext import Ext
from search.experiments.e022.newcodes import load_random, register
from search.experiments.e022.solve22 import instance

RES = "/Users/ephemeral/Desktop/qec-ai-search/results/E-022-morphing-criterion"
NPAR = int(os.environ.get("NPAR", "1"))


def enddist(key):
    out = {}
    for basis in "ZX":
        for c in (0, 1):
            E = Ext(key, basis, 1 - c, c)
            H, L = E.Hc.astype(np.uint8), E.Lc.astype(np.uint8)
            code = E.code
            perms = []
            for s in E.translations():
                p = np.array([code.translate_q(q, s) for q in range(code.N)])
                if perm_ok(H, L, p):
                    perms.append(p)
            orb = orbits(code.N, perms)
            path = f"{RES}/inst/end_{key}_{basis}_c{c}.txt"
            norb = write_inst(path, H, L, orb)
            W, sol, log = min_weight(path, norb, 20, Wstart=1, npar=NPAR)
            out[f"{basis}_c{c}"] = dict(d=W, witness=sol, sec=round(sum(x["sec"] for x in log), 2))
    ds = [v["d"] for v in out.values()]
    res = dict(key=key, n=common.get_code(key.split("_")[0]).N, k=int(len(Ext(key, "Z").Lc)), d_end=min(ds),
               all_equal=len(set(ds)) == 1, detail=out)
    json.dump(res, open(f"{RES}/enddist_{key}.json", "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("key", "n", "k", "d_end", "all_equal")}), flush=True)
    return res


def ext(key, basis, half):
    d_end = json.load(open(f"{RES}/enddist_{key}.json"))["d_end"]
    t0 = time.time()
    E = Ext(key, basis)
    keep = None if half == "full" else np.array([(k <= 3) == (half == "exp") for (kind, k, qs) in E.faults])
    path, norb, groups, Hd, Ld, nperm = instance(E, "start", keep=keep, tag=f"_pred{half}")
    W = d_end - 1
    best = None
    runs = []
    while W >= 1:
        res = run_all_cases(path, W, norb, npar=NPAR)
        assert all(r["complete"] for r in res)
        sols = [s for r in res for s in r["found"]]
        runs.append(dict(W=W, found=len(sols), nodes=sum(r["nodes"] for r in res), sec=round(sum(r["sec"] for r in res), 2)))
        if not sols:
            break
        best = min(sols, key=len)
        W = len(best) - 1
    d = len(best) if best else d_end
    wit = [list(E.faults[groups[c][0]]) for c in best] if best else None
    out = dict(key=key, basis=basis, half=half, d_end=d_end, d_ext=d, cols=int(Hd.shape[1]), norb=norb,
               runs=runs, witness=wit, sec=round(time.time() - t0, 1))
    json.dump(out, open(f"{RES}/pred_{key}_{basis}_{half}.json", "w"), indent=1, default=str)
    print(json.dumps({k: out[k] for k in ("key", "basis", "half", "d_end", "d_ext", "cols", "sec")}), flush=True)
    return out


if __name__ == "__main__":
    register(load_random())
    os.makedirs(f"{RES}/inst", exist_ok=True)
    if sys.argv[1] == "enddist":
        for k in sys.argv[2:]:
            enddist(k)
    elif sys.argv[1] == "ext":
        ext(sys.argv[2], sys.argv[3], sys.argv[4])
