"""E-036: exact SD6 circuit distance on the full DEM by meet-in-the-middle (weights 1..4).

usage: dcirc.py VARIANT CIRCUIT R1 R2 ...      CIRCUIT = kunlun | ibm | path/to/spec.json
Prints per (basis, R): number of distinct mechanisms, minimal weight found (exhaustive for w <= wmax), witness check.
"""
import argparse
import json
import time

from search.experiments.e036.common import (OUT, code, dem_mechs, ibm_spec, kunlun_spec, load_spec, min_weight, sd6,
                                            verify_witness)
from evaluators import candidate as cand


def get_spec(variant, name):
    if name == "kunlun":
        return kunlun_spec(variant)
    if name == "ibm":
        return ibm_spec(variant)
    return load_spec(name)


def run(variant, name, Rs, wmax=4, bases=("Z", "X")):
    spec = get_spec(variant, name)
    probs = cand.validate_schedule(spec, code(variant))
    assert not probs, probs
    res = []
    for basis in bases:
        for R in Rs:
            t0 = time.time()
            mechs, nd = dem_mechs(sd6(spec, variant, basis, R))
            w, wit = min_weight(mechs, wmax)
            ok = verify_witness(mechs, wit) if wit else None
            r = {"variant": variant, "circuit": name, "basis": basis, "R": R, "mechs": len(mechs), "dets": nd,
                 "min_w": w, "exhaustive_upto": (w - 1) if w else wmax, "witness_ok": ok, "sec": round(time.time() - t0, 2)}
            print(json.dumps(r), flush=True)
            res.append(r)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("variant")
    ap.add_argument("circuit")
    ap.add_argument("R", nargs="+", type=int)
    ap.add_argument("--wmax", type=int, default=4)
    ap.add_argument("--bases", default="ZX")
    a = ap.parse_args()
    res = run(a.variant, a.circuit, a.R, a.wmax, tuple(a.bases))
    with open(OUT / "dcirc.jsonl", "a") as f:
        for r in res:
            f.write(json.dumps(r) + "\n")
