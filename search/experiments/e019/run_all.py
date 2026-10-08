"""E-019 driver: construct -> end-cycle distances -> instances (T = 4, both bases) -> solve, for the given keys
(default: the whole 80-circuit family, smallest codes first).
usage: uv run python -m search.experiments.e019.run_all [key ...]
"""
from __future__ import annotations

import os
import subprocess
import sys

from search.experiments.e019.common import variants

RES = "/Users/ephemeral/Desktop/qec-ai-search/results/E-019-morphing-family"
ORDER = {"bb72": 0, "bb108": 1, "bb144": 2, "bb288": 3}


def sh(args, log):
    with open(log, "a") as fo:
        r = subprocess.run(["uv", "run", "python", "-m", *args], stdout=fo, stderr=subprocess.STDOUT,
                           cwd="/Users/ephemeral/Desktop/qec-ai-search")
    return r.returncode


def main():
    keys = sys.argv[1:] or sorted(("_".join(t) for t in variants()), key=lambda k: ORDER[k.split("_")[0]])
    log = f"{RES}/run_all.log"
    if not os.path.exists(f"{RES}/construct.json"):
        sh(["search.experiments.e019.construct"], log)
    for key in keys:
        if not os.path.exists(f"{RES}/ec/dist_{key}.json"):
            sh(["search.experiments.e019.endcycle", key], log)
        for b in "ZX":
            tag = f"{key}_{b}_T4"
            if not os.path.exists(f"{RES}/inst/info_{tag}.json"):
                sh(["search.experiments.e019.instance", key, b, "4"], log)
            if not os.path.exists(f"{RES}/solve_{tag}.json"):
                extra = ["--no_posctl"] if key.startswith("bb288") else []   # upper bound by injection only
                sh(["search.experiments.e019.solve", key, b, *extra], log)


if __name__ == "__main__":
    main()
