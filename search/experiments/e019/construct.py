"""E-019 stage 1: construct every family member, check the contraction property, end-cycle code k, degree;
cross-check repo/paper variants of [[288]] gate-by-gate against E-017's morph.py.
usage: uv run python -m search.experiments.e019.construct
"""
from __future__ import annotations

import json

import numpy as np

from search.experiments.e019.common import analyse, get_code, memory, spec, variants

OUT = "results/E-019-morphing-family"


def main():
    res = {}
    for name, hom, v in variants():
        code = get_code(name)
        key = f"{name}_{hom}_{v}"
        try:
            gates, meas, a, b = spec(code, hom, v)
            info, ec = analyse(code, gates, meas)
            info["a"], info["b"] = a, b
            info["ok"] = bool(info["each_stab_contracted_once"] and info["ec0"]["k"] == info["k_mid"]
                              and info["ec1"]["k"] == info["k_mid"])
            for c in range(2):
                np.savez(f"{OUT}/ec/{key}_c{c}.npz", HX=ec[c]["X"], HZ=ec[c]["Z"])
        except AssertionError as e:
            info = {"ok": False, "error": repr(e)}
        res[key] = info
        print(key, json.dumps(info, default=str), flush=True)
    # gate-by-gate vs E-017 morph.py for bb288
    from search.experiments.e017.morph import TWO_GROSS, Morph
    cmp = {}
    for hom in ("x", "y", "xy"):
        for v, sw in (("repo", False), ("paper", True)):
            code = get_code("bb288")
            gates, meas, _, _ = spec(code, hom, v)
            M = Morph(TWO_GROSS, hom, swap23=sw)
            same = True
            for c in range(2):
                for k in range(3):
                    if set(map(tuple, M.layers[c][k])) != set(map(tuple, gates[c][k])):
                        same = False
                for P in "XZ":
                    if sorted(M.meas[c][P]) != sorted(meas[c][P]):
                        same = False
            cmp[f"{hom}_{v}"] = same
    print("vs e017 morph.py:", cmp)
    res["_vs_e017"] = cmp
    json.dump(res, open(f"{OUT}/construct.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    import os
    os.makedirs(f"{OUT}/ec", exist_ok=True)
    main()
