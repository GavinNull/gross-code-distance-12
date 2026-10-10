"""E-022: exact distance of the morphing extended code (end view and start view) with adfs; compare with E-019.

usage: uv run python -m search.experiments.e022.solve22 <key> <basis> [--Wmax W] [--view end|start|both] [--pc P C]
"""
from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np

from search.experiments.e019.dfsrun import min_weight, orbits, perm_ok, write_inst
from search.experiments.e022.ext import Ext, dedup

RES = "/Users/ephemeral/Desktop/qec-ai-search/results/E-022-morphing-criterion"


def instance(E, view, keep=None, tag=""):
    H, L = E.end_matrix() if view == "end" else E.start_matrix()
    Hd, Ld, groups = dedup(H, L, keep)
    colof = {}
    for ci, g in enumerate(groups):
        for i in g:
            colof[i] = ci
    perms = []
    for s in E.translations():
        fp = E.fault_perm(s)
        if fp is None:
            continue
        pc = []
        ok = True
        for ci, g in enumerate(groups):
            ims = set(colof.get(fp[i], -1) for i in g)
            if len(ims) != 1 or -1 in ims:
                ok = False
                break
            pc.append(ims.pop())
        if ok and sorted(pc) == list(range(len(groups))) and perm_ok(Hd, Ld, pc):
            perms.append(pc)
    orb = orbits(len(groups), perms)
    os.makedirs(f"{RES}/inst", exist_ok=True)
    path = f"{RES}/inst/{E.key}_{E.basis}_p{E.p}c{E.c}_{view}{tag}.txt"
    norb = write_inst(path, Hd, Ld, orb)
    return path, norb, groups, Hd, Ld, len(perms)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("basis")
    ap.add_argument("--Wmax", type=int, default=None)
    ap.add_argument("--view", default="end")
    ap.add_argument("--pc", type=int, nargs=2, default=[0, 1])
    ap.add_argument("--cnot_only", action="store_true")
    ap.add_argument("--half", default=None, help="exp (faults after layers 0..3) | con (after layers 4..6)")
    a = ap.parse_args()
    t0 = time.time()
    E = Ext(a.key, a.basis, a.pc[0], a.pc[1], cnot_only=a.cnot_only)
    out = dict(key=a.key, basis=a.basis, p=E.p, c=E.c, nfaults=len(E.faults), cnot_only=a.cnot_only)
    views = ["end", "start"] if a.view == "both" else [a.view]
    for view in views:
        keep = None
        if a.half:
            keep = np.array([(k <= 3) == (a.half == "exp") for (kind, k, qs) in E.faults])
        tagv = ("_cx" if a.cnot_only else "") + (f"_{a.half}" if a.half else "")
        path, norb, groups, Hd, Ld, nperm = instance(E, view, keep=keep, tag=tagv)
        Wmax = a.Wmax or 12
        W, sol, log = min_weight(path, norb, Wmax, npar=int(os.environ.get("NPAR", "2")))
        wit = [[list(E.faults[i]) for i in groups[cix]][:1][0] for cix in sol] if sol else None
        out[view] = dict(inst=path, rows=int(Hd.shape[0]), cols=int(Hd.shape[1]), norb=norb, nperm=nperm,
                         d=W, witness=wit, log=log)
    out["sec"] = round(time.time() - t0, 1)
    tag = ("_cx" if a.cnot_only else "") + (f"_{a.half}" if a.half else "")
    out["half"] = a.half
    json.dump(out, open(f"{RES}/ext_{a.key}_{a.basis}_p{E.p}c{E.c}{tag}.json", "w"), indent=1, default=str)
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: v[kk] for kk in ("d", "cols", "norb")})
                      for k, v in out.items()}), flush=True)


if __name__ == "__main__":
    main()
