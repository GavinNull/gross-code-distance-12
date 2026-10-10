"""E-022: run the unmodified E-019 exact pipeline (construct -> end-cycle distance -> T=4 instance with derived
detectors, stim DEM cross-check, locality, round equivalence, Prop. 1 fold condition, symmetry -> exhaustive
single-round adfs -> witness injection) on held-out circuits. E-019 modules are imported, only their output
directories are redirected (module constants) and the extra codes registered in the code table at runtime.

usage: uv run python -m search.experiments.e022.pipe019 <key> [<key> ...]
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

from search.experiments.e019 import common, endcycle, instance, solve
from search.experiments.e019.common import analyse, spec
from search.experiments.e022.newcodes import load_random, register

OUT = "/Users/ephemeral/Desktop/qec-ai-search/results/E-022-morphing-criterion/e019pipe"


def run(key):
    name, hom, v = key.split("_")
    code = common.get_code(name)
    os.makedirs(f"{OUT}/ec/dfs", exist_ok=True)
    os.makedirs(f"{OUT}/inst", exist_ok=True)
    gates, meas, _, _ = spec(code, hom, v)
    info, ec = analyse(code, gates, meas)
    assert info["each_stab_contracted_once"] and info["ec0"]["k"] == info["k_mid"] == info["ec1"]["k"]
    for c in range(2):
        np.savez(f"{OUT}/ec/{key}_c{c}.npz", HX=ec[c]["X"], HZ=ec[c]["Z"])
    if not os.path.exists(f"{OUT}/ec/dist_{key}.json"):
        endcycle.ec_distance(key)
    for b in "ZX":
        tag = f"{key}_{b}_T4"
        if not os.path.exists(f"{OUT}/inst/info_{tag}.json"):
            instance.build(key, b, 4)
        if not os.path.exists(f"{OUT}/solve_{tag}.json"):
            sys.argv = ["solve", key, b, "--npar", "1"]
            solve.main()


if __name__ == "__main__":
    register(load_random())
    endcycle.OUT = OUT
    instance.OUT = f"{OUT}/inst"
    solve.RES = OUT
    for k in sys.argv[1:]:
        try:
            run(k)
        except Exception as e:      # record and continue
            print("PIPE_ERROR", k, repr(e), flush=True)
            with open(f"{OUT}/errors.log", "a") as fo:
                fo.write(f"{k} {e!r}\n")
