"""E-022: second, independent check of held-out predictions with the E-019 AUDITOR's construction and solver
(research/audits/2026-10-08-E-019-scripts: mycirc.Morph built from the paper's Tables IV/VIII, explicit Pauli-
propagation detectors, stim DEM of the whole T = 4 memory circuit with sd6 noise -- no single-round reduction, no
fold -- and the auditor's mdfs). The auditor's (kind, sa, sb) circuit is matched to the E-019 label by comparing
gate sets layer by layer. Scripts are imported read-only; the extra code is added to their PARENT table at runtime.

usage: uv run python -m search.experiments.e022.audit_check <key> <basis> <Wmax>
"""
from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
import time

AUD = "/Users/ephemeral/Desktop/qec-ai-search/research/audits/2026-10-08-E-019-scripts"
sys.path.insert(0, AUD)
import mycirc  # noqa: E402
from inst import dem_columns, make, noisy, orbits, write_instance  # noqa: E402

from search.experiments.e019 import common  # noqa: E402
from search.experiments.e022.newcodes import load_random, register  # noqa: E402

RES = "/Users/ephemeral/Desktop/qec-ai-search/results/E-022-morphing-criterion"
MDFS = f"{RES}/mdfs"


def match(key):
    name, hom, v = key.split("_")
    c = common.get_code(name)
    gates, meas, _, _ = common.spec(c, hom, v)
    theirs = [(tuple(frozenset(l) for l in gates[r]), frozenset(meas[r]["X"]), frozenset(meas[r]["Z"])) for r in range(2)]
    for kind in ("IV", "VIII"):
        for sa, sb in itertools.product((0, 1), (0, 1)):
            M = make(name, hom, kind, sa, sb)
            mine = []
            for i in (1, 2):
                layers, ms = M.F(i)
                mine.append((tuple(frozenset(l) for l in layers), frozenset(ms["X"]), frozenset(ms["Z"])))
            if mine == theirs:
                return M, (kind, sa, sb)
    return None, None


def main(key, basis, Wmax):
    t0 = time.time()
    M, lab = match(key)
    out = dict(key=key, basis=basis, auditor_label=lab)
    if M is None:
        out["error"] = "no auditor circuit matches"
        print(json.dumps(out), flush=True)
        return out
    M.check_contraction()
    c, nc = noisy(M, basis, 4, True, "sd6", None)
    ndet, nobs, cols = dem_columns(nc)
    orb, norb = orbits(M, M.memory(basis, 4, full_detectors=True), cols, None)
    if orb is None:
        orb, norb = None, 0
    os.makedirs(f"{RES}/audinst", exist_ok=True)
    path = f"{RES}/audinst/{key}_{basis}.txt"
    write_instance(path, ndet, nobs, cols, orb, norb)
    out.update(ndet=ndet, nobs=nobs, cols=len(cols), norb=norb)
    d = None
    for W in range(1, Wmax + 1):
        res = subprocess.run([MDFS, path, str(W)], capture_output=True, text=True).stdout
        if any(l.startswith("FOUND") for l in res.splitlines()):
            d = W
            break
    out["d_circ_T4"] = d
    out["sec"] = round(time.time() - t0, 1)
    json.dump(out, open(f"{RES}/aud_{key}_{basis}.json", "w"), default=str)
    print(json.dumps(out, default=str), flush=True)
    return out


if __name__ == "__main__":
    extra = load_random()
    register(extra)
    mycirc.PARENT.update(common.CODES)
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]))
