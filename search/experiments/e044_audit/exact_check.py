"""E-044 audit (item 1): independent enumeration of minimum-weight undetected logicals on the SD6 DEM with own C DFS
(dfsenum.c), own columns (signature-merged DEM from e044.common.noisy) and own priors; compared as sets of
(detectors, observables) signatures with the E-044 lists, and U / A recomputed.
  PYTHONPATH=.:tests uv run python -m search.experiments.e044_audit.exact_check ibm90 Z 1 8 [procs]"""
import json
import subprocess
import sys
import time
from math import prod

import numpy as np

from search.experiments.e044.common import ROOT, noisy

OUT = ROOT / "results" / "E-044-audit"
EXE = OUT / "dfsenum"


def columns(circ, basis, R, p, model):
    dem = noisy(circ, basis, p, model, rounds=R).detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    pr = {}
    for e in dem.flattened():
        if e.type != "error":
            continue
        d, o = set(), set()
        for t in e.targets_copy():
            if t.is_relative_detector_id():
                d ^= {t.val}
            elif t.is_logical_observable_id():
                o ^= {t.val}
        k = (tuple(sorted(d)), tuple(sorted(o)))
        x, y = pr.get(k, 0.0), e.args_copy()[0]
        pr[k] = x * (1 - y) + y * (1 - x)
    return pr, dem.num_detectors


def esym(q, t):
    e = np.zeros(t + 1); e[0] = 1
    for x in q:
        e[1:] = e[1:] + x * e[:-1]
    return e[t]


def run(circ, basis, R, W, procs=1):
    pr1, nd = columns(circ, basis, R, 1e-4, "lam1")
    keys = sorted(pr1)
    lines = [f"{len(keys)} {nd}"] + [f"{len(d)} {' '.join(map(str, d))} {sum(1 << x for x in o)}" for d, o in keys]
    inp = OUT / f"cols_{circ}_{basis}_R{R}.txt"
    inp.write_text("\n".join(lines) + "\n")
    t0 = time.time()
    M = len(keys)
    # split seeds into chunks of roughly equal work (low seeds are the expensive ones)
    bounds = np.unique(np.round(M * (1 - np.sqrt(1 - np.linspace(0, 1, 4 * procs + 1)))).astype(int))
    chunks = [(bounds[i], bounds[i + 1] - 1) for i in range(len(bounds) - 1)]
    sols, lower, nodes = [], 0, 0
    running = []
    while chunks or running:
        while chunks and len(running) < procs:
            lo, hi = chunks.pop(0)
            running.append(subprocess.Popen([str(EXE), str(W), str(lo), str(hi)], stdin=open(inp), stdout=subprocess.PIPE, text=True))
        time.sleep(0.5)
        for p in list(running):
            if p.poll() is not None:
                out = p.stdout.read().splitlines()
                for ln in out:
                    if ln.startswith("SOL"):
                        sols.append(tuple(sorted(map(int, ln.split()[1:]))))
                    elif ln.startswith("COUNT"):
                        x = ln.split(); lower += int(x[3]); nodes += int(x[5])
                running.remove(p)
    sigs = set(tuple(keys[j] for j in S) for S in sols)
    assert len(sigs) == len(sols)
    for S in sols:
        d, o = set(), set()
        for j in S:
            d ^= set(keys[j][0]); o ^= set(keys[j][1])
        assert not d and o
    rec = dict(circ=circ, basis=basis, R=R, W=W, N=len(sols), lower=lower, nodes=nodes, sec=round(time.time() - t0))
    for m in ("lam0", "lam1"):
        pr, _ = columns(circ, basis, R, 1e-4, m)
        q = [[pr.get(k, 0.0) for k in S] for S in sigs]
        rec[m] = dict(U=sum(prod(x) for x in q) / 1e-4 ** W, A=sum(esym(x, (W + 1) // 2) for x in q) * (0.5 if W % 2 == 0 else 1) / 1e-4 ** ((W + 1) // 2))
    (OUT / f"enum_{circ}_{basis}_R{R}_W{W}.json").write_text(json.dumps(dict(rec, sols=sorted([[list(map(list, k)) for k in S] for S in sigs]))))
    print(json.dumps(rec), flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    run(a[0], a[1], int(a[2]), int(a[3]), int(a[4]) if len(a) > 4 else 1)
