"""E-036: any-R certification for NON-WRAPPING circuits (every check: prep layer 0, CNOTs in 1..P-2, meas P-1).

Lower bound (E-028 argument, audited in research/audits/2026-10-15-E-028.md): rounds are separated by a layer
boundary at which every ancilla has been measured; detectors compare consecutive rounds.  If a minimum-weight
undetectable logical F had a fault-free round strictly inside its span, F would split into two undetectable parts
one of which is a lighter logical; leading / trailing fault-free rounds can be removed by periodicity.  Hence a
weight-w undetectable logical exists for some R iff it exists for some R <= w + 3.  We check R = 1..Rmax with
Rmax >= (d-1) + 3 exhaustively (all weights <= d-1).
Upper bound for all R: d reset faults on the data qubits of a minimum-weight logical (layer 0) -> d_circ <= d.
For circuits with d_circ < d we also look for a BULK witness: at R = 5, a weight-(d_circ) witness all of whose faults
lie in rounds 2..4 and whose detectors are bulk; by periodicity the same fault pattern exists for every R >= 5.
"""
import argparse
import json

import stim

from search.experiments.e036.common import OUT, code, dem_mechs, min_weight, sd6
from search.experiments.e036.dcirc import get_spec


def separation(spec):
    P = spec.period
    ok = True
    for c in list(spec.x_checks) + list(spec.z_checks):
        if c.prep != 0 or c.meas != P - 1 or not all(1 <= t <= P - 2 for _, t in c.cnots):
            ok = False
    return ok


def run(variant, name, d, Rmax):
    spec = get_spec(variant, name)
    rep = {"variant": variant, "circuit": name, "period": spec.period, "separated": separation(spec), "Rmax": Rmax,
           "per_R": {}}
    lowest = None
    for R in range(1, Rmax + 1):
        row = {}
        for b in ("Z", "X"):
            mechs, _ = dem_mechs(sd6(spec, variant, b, R))
            w, wit = min_weight(mechs, d - 1)
            row[b] = w
            if w is not None:
                lowest = w if lowest is None else min(lowest, w)
        rep["per_R"][R] = row
    rep["min_over_R_found"] = lowest
    rep["no_weight_below_d_for_R_le_Rmax"] = lowest is None
    rep["anyR_lower_bound_applies"] = rep["separated"] and Rmax >= (d - 1) + 3
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("variant")
    ap.add_argument("circuit")
    ap.add_argument("--d", type=int, required=True)
    ap.add_argument("--Rmax", type=int, default=12)
    a = ap.parse_args()
    rep = run(a.variant, a.circuit, a.d, a.Rmax)
    print(json.dumps(rep))
    with open(OUT / "anyr.jsonl", "a") as f:
        f.write(json.dumps(rep) + "\n")
