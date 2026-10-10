"""E-022: classify the faults of one half-cycle by flags (r_f = reset-side flag, rho_f = measurement-side flag) and
compute the one-sided 'unflagged hook' extended codes
    Ext_c^0 = C~_c with columns b_f for all faults with rho_f = 0   (end-clean faults; includes the data qubits)
    Ext_p^0 = C~_p with columns a_f for all faults with r_f = 0     (start-clean faults)
usage: uv run python -m search.experiments.e022.classify <key> <basis> [p c]
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

from search.experiments.e019.dfsrun import min_weight, orbits, perm_ok, write_inst
from search.experiments.e022.ext import Ext, dedup

RES = "/Users/ephemeral/Desktop/qec-ai-search/results/E-022-morphing-criterion"


def onesided(E, side, Wmax):
    if side == "c":
        H = E.sb.T.astype(np.uint8)
        L = E.lb.T.astype(np.uint8)
        keep = ~E.rho.any(1)
    else:
        H = E.sa.T.astype(np.uint8)
        L = E.la.T.astype(np.uint8)
        keep = ~E.r.any(1)
    Hd, Ld, groups = dedup(H, L, keep)
    colof = {i: ci for ci, g in enumerate(groups) for i in g}
    perms = []
    for s in E.translations():
        fp = E.fault_perm(s)
        pc = []
        ok = fp is not None
        for g in (groups if ok else []):
            ims = set(colof.get(fp[i], -1) for i in g)
            if len(ims) != 1 or -1 in ims:
                ok = False
                break
            pc.append(ims.pop())
        if ok and sorted(pc) == list(range(len(groups))) and perm_ok(Hd, Ld, pc):
            perms.append(pc)
    orb = orbits(len(groups), perms)
    path = f"{RES}/inst/{E.key}_{E.basis}_p{E.p}c{E.c}_one{side}.txt"
    norb = write_inst(path, Hd, Ld, orb)
    W, sol, log = min_weight(path, norb, Wmax, npar=1)
    wit = [E.faults[groups[ci][0]] for ci in sol] if sol else None
    return W, wit, int(Hd.shape[1])


def main(key, basis, p=0, c=1, Wmax=12):
    E = Ext(key, basis, p, c)
    rf = E.r.any(1)
    mf = E.rho.any(1)
    cls = {}
    for i, (kind, k, qs) in enumerate(E.faults):
        t = ("r" if rf[i] else "-") + ("m" if mf[i] else "-")
        cls.setdefault(t, {}).setdefault(f"{kind}@{k}", 0)
        cls[t][f"{kind}@{k}"] += 1
    both = [E.faults[i] for i in range(len(E.faults)) if rf[i] and mf[i]]
    dc, witc, nc = onesided(E, "c", Wmax)
    dp, witp, np_ = onesided(E, "p", Wmax)
    # hook weights: minimal weight of b_f modulo C~_c stabilisers is expensive; report raw weights
    hw = {}
    for i, (kind, k, qs) in enumerate(E.faults):
        if not mf[i]:
            hw.setdefault("b|rho=0", {}).setdefault(int(E.b[i].sum()), 0)
            hw["b|rho=0"][int(E.b[i].sum())] += 1
        if not rf[i]:
            hw.setdefault("a|r=0", {}).setdefault(int(E.a[i].sum()), 0)
            hw["a|r=0"][int(E.a[i].sum())] += 1
    out = dict(key=key, basis=basis, p=p, c=c, classes=cls, n_doubly_flagged=len(both),
               d_onesided_c=dc, d_onesided_p=dp, cols_c=nc, cols_p=np_, wit_c=witc, wit_p=witp, hook_weights=hw)
    json.dump(out, open(f"{RES}/classify_{key}_{basis}_p{p}c{c}.json", "w"), indent=1, default=str)
    print(json.dumps(dict(key=key, basis=basis, pc=(p, c), doubly=len(both), d1c=dc, d1p=dp,
                          classes={t: sum(v.values()) for t, v in cls.items()})), flush=True)
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], *(int(x) for x in a[2:4])) if len(a) > 2 else main(a[0], a[1])
