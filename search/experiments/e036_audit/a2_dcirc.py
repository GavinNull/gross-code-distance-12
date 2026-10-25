"""Audit claims 3 and 5: exact d_circ of the Kunlun reconstruction and the two P8 specs, by two of my own models
(symbolic closed-form fault list; my own stim circuit + SD6 + full DEM incl. other-basis detectors), reset and
no-reset ancillas.  Also: coupler check of the P8 json files (every CNOT on one of the 84 / 72 Tanner edges)."""
import argparse
import json
import time

from search.experiments.e036_audit.core import (Sym, kunlun_schedule, legal, min_weight_le, schedule_from_json,
                                                stim_circuit, stim_mechs)

SPECS = {
    "kunlun": None,
    "q1863_p8": "search/experiments/e036/q1863_p8_spec.json",
    "bb18_p8_d3": "search/experiments/e036/bb18_p8_d3_spec.json",
}


def get(name, variant):
    if name == "kunlun":
        return kunlun_schedule(variant)
    return schedule_from_json(SPECS[name], variant)


def run(name, variant, Rs, wmax, use_stim=True):
    T, S = get(name, variant)
    ok, why = legal(T, variant, S)
    out = {"circuit": name, "variant": variant, "S": S, "legal": ok, "why": why, "rows": []}
    for R in Rs:
        for b in ("Z", "X"):
            for reset in (True, False):
                t0 = time.time()
                sm = Sym(variant, b, T, R, reset=reset).mechs()
                ws, wit = min_weight_le(sm, wmax)
                row = {"R": R, "basis": b, "reset": reset, "w_sym": ws,
                       "sym_wit": [sm[i][2][:2] if sm[i][2][0] != "meas" else ("meas",) for i in wit[0]] if wit else None}
                if use_stim:
                    c = stim_circuit(T, S, variant, b, R, reset=reset)
                    mm = stim_mechs(c)
                    wst, _ = min_weight_le(mm, wmax)
                    row["w_stim"] = wst
                    row["n_stim_mechs"] = len(mm)
                row["sec"] = round(time.time() - t0, 1)
                out["rows"].append(row)
                print(json.dumps(row, default=str), flush=True)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("variant")
    ap.add_argument("--Rmax", type=int, default=5)
    ap.add_argument("--wmax", type=int, default=3)
    ap.add_argument("--no-stim", action="store_true")
    a = ap.parse_args()
    r = run(a.name, a.variant, range(1, a.Rmax + 1), a.wmax, not a.no_stim)
    with open("results/E-036-audit/a2_dcirc.jsonl", "a") as f:
        f.write(json.dumps(r, default=str) + "\n")
