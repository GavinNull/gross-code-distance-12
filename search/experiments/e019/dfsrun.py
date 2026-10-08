"""E-019: helpers to write adfs instances and run adfs (exhaustive, orbit case split) in parallel.

adfs (copied verbatim from the E-017 auditor, research/audits/2026-10-08-E-017-scripts/adfs.c, validated there
against brute force): decides whether a set S, |S| <= W, with H(S) = 0 and L(S) != 0 exists.
Instance format: header 'R C NORB'; per column 'orbit lmask nrows rows...'.
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from search.experiments.e019.common import rank

ROOT = "/Users/ephemeral/Desktop/qec-ai-search"
ADFS = f"{ROOT}/results/E-019-morphing-family/adfs"
NPAR = int(os.environ.get("NPAR", "6"))


def write_inst(path, H, L, orb):
    """H: rows x cols (uint8), L: k x cols, orb: list of orbit labels (0..norb-1)."""
    nz = [i for i in range(H.shape[0]) if H[i].any()]
    Hn = H[nz]
    assert len(nz) <= 192
    norb = max(orb) + 1
    with open(path, "w") as fo:
        fo.write(f"{len(nz)} {H.shape[1]} {norb}\n")
        for c in range(H.shape[1]):
            rr = np.nonzero(Hn[:, c])[0].tolist()
            lm = int(sum(1 << int(b) for b in np.nonzero(L[:, c])[0])) if L is not None else 0
            fo.write(f"{orb[c]} {lm} {len(rr)} " + " ".join(map(str, rr)) + "\n")
    return norb


def orbits(ncol, perms):
    parent = list(range(ncol))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for p in perms:
        for c in range(ncol):
            a, b = find(c), find(int(p[c]))
            if a != b:
                parent[max(a, b)] = min(a, b)
    roots = sorted(set(find(c) for c in range(ncol)))
    lab = {r: i for i, r in enumerate(roots)}
    return [lab[find(c)] for c in range(ncol)]


def perm_ok(H, L, p):
    """column permutation p (new column c' = p[c]) preserves {x: Hx=0, Lx!=0}: rowspace conditions."""
    Hp = np.zeros_like(H)
    Hp[:, p] = H
    if L is None:
        return rank(H) == rank(np.vstack([H, Hp]))
    Lp = np.zeros_like(L)
    Lp[:, p] = L
    HL, HLp = np.vstack([H, L]), np.vstack([Hp, Lp])
    return rank(H) == rank(np.vstack([H, Hp])) and rank(HL) == rank(np.vstack([HL, HLp]))


def run_one(inst, W, case, extra=(), outdir=None, timeout=None):
    t0 = time.time()
    try:
        r = subprocess.run([ADFS, inst, str(W), str(case), *extra], capture_output=True, text=True, timeout=timeout)
        out = r.stdout
    except subprocess.TimeoutExpired as e:
        out = (e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")) + "\nTIMEOUT\n"
    if outdir:
        tag = os.path.basename(inst).replace(".txt", "") + f"_W{W}_c{case}"
        open(f"{outdir}/{tag}.txt", "w").write(out)
    found = [list(map(int, ln.split("cols:")[1].split())) for ln in out.splitlines() if ln.startswith("FOUND")]
    m = re.search(r"nodes=(\d+)", out)
    s = re.search(r"sec=([\d.]+)", out)
    return dict(case=case, W=W, found=found, nodes=int(m.group(1)) if m else None,
                sec=float(s.group(1)) if s else time.time() - t0, complete="SUMMARY" in out)


def run_all_cases(inst, W, norb, outdir=None, stop_on_found=False, npar=NPAR, timeout=None):
    """Run every orbit case at weight bound W. Returns list of per-case dicts."""
    res = []
    with ThreadPoolExecutor(npar) as ex:
        futs = [ex.submit(run_one, inst, W, c, (), outdir, timeout) for c in range(norb)]
        for f in futs:
            res.append(f.result())
    return res


def min_weight(inst, norb, Wmax, outdir=None, Wstart=1, npar=NPAR):
    """Smallest W <= Wmax with a solution (exhaustive below it). Returns (W or None, solution, log)."""
    log = []
    for W in range(Wstart, Wmax + 1):
        res = run_all_cases(inst, W, norb, outdir, npar=npar)
        assert all(r["complete"] for r in res)
        log.append(dict(W=W, nodes=sum(r["nodes"] for r in res), sec=sum(r["sec"] for r in res),
                        found=sum(len(r["found"]) for r in res)))
        sols = [s for r in res for s in r["found"]]
        if sols:
            return W, sols[0], log
    return None, None, log
