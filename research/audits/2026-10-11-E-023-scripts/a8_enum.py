"""Audit E-023 (b): enumeration saturation / capture-recapture.  A fresh search round (experimenter's search(), new seed,
writes ONLY to results/E-023-audit), translation closure (experimenter's close()), and overlap with the experimenter's
closed sets per weight.  Lincoln-Petersen N ~ n1 n2 / m (a lower-bias-but-still-underestimate under heterogeneity).
args: prob trials seed"""
import sys, json, time
import numpy as np
sys.path.insert(0, '.')
from search.experiments.e023.common import sectors, P_DEC
from search.experiments.e023.lowweight import search, morph_perms, close
from multiprocessing import get_context
if __name__ == "__main__":
    prob, trials, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    secs = sectors(prob, "sd6", P_DEC)
    jobs = [(prob, si, trials // 2, seed * 1000 + 100 * si + c, 8) for si in range(len(secs)) for c in range(2)]
    with get_context("spawn").Pool(2) as pool:
        res = pool.map(search, jobs)
    old = json.load(open(f"results/E-023-ler-benefit/lowweight/{prob}.json"))
    _, permsets = morph_perms(prob)
    out = {}
    for si, sec in enumerate(secs):
        mine = set()
        for pr, s_, sd, r in res:
            if s_ == si: mine |= set(tuple(x) for x in r["sols"])
        cl = close(sec, list(mine), permsets[si])
        theirs = set(tuple(x) for x in old["sectors"][sec.label]["closed"])
        o = {}
        for W in (6, 7, 8):
            a = {x for x in cl if len(x) == W}; b = {x for x in theirs if len(x) == W}
            m = len(a & b)
            o[W] = dict(mine=len(a), theirs=len(b), both=m, new_vs_theirs=len(a - b),
                        LP=(len(a) * len(b) / m) if m else None)
        out[sec.label] = o
        print(prob, sec.label, o, flush=True)
    json.dump(out, open(f"results/E-023-audit/a8_{prob}_s{seed}.json", "w"), indent=1)
