"""Upper bounds of Table I for g9, b9, b10 and IBM's depth-8 circuits (End Matter "Persistence of upper bounds";
SM S8 "Upper bounds"): replay the R = 1 undetected logicals of witnesses/persistence_R1.json in the noiseless memory
circuit with R rounds, at the start and shifted by whole rounds, with stim.

A witness is a list of single-qubit Paulis at TICK boundaries of the one-round circuit (one representative physical
fault per DEM mechanism of the SD6 detector error model; the field "gate" names the noise channel it comes from).
For every R and shift k (R >= 1 + k) the Paulis are inserted as probability-1 X/Y/Z_ERROR at boundary b + kP of the
noiseless circuit with R rounds (code/gross12/schedule.py); one sample must fire no detector and flip exactly the
recorded observables (rows of L of data/code/*_code.json), and removing any single fault must fire a detector.

    python code/tclass/persist.py [NAME ...] [--R 1,2,3,5,8,12,20,30] [--shifts 0,2]
NAME: ibm_gross_depth8, bb90_ibm_depth8, g9, bb90_b9, bb90_b10 (default: all, both bases).
"""
import json
import sys
from pathlib import Path

import numpy as np
import stim

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
from gross12 import schedule as PS          # noqa: E402
from p11 import common as C                 # noqa: E402
from bb90 import bbcode                     # noqa: E402

FAM = {"ibm_gross_depth8": "gross", "g9": "gross", "bb90_ibm_depth8": "bb90", "bb90_b9": "bb90", "bb90_b10": "bb90"}


def clean_circuit(name, basis, R):
    spec = PS.load_schedule(ROOT / "data" / "circuits" / f"{name}.json")
    code = C.load_gross() if FAM[name] == "gross" else bbcode.load_code()
    return PS.build_circuits(spec.canonical(), code, R)[basis].flattened(), spec.period


def inject(clean, faults, shift_ticks, drop=None):
    layers, cur = [], stim.Circuit()
    for op in clean:
        if op.name == "TICK":
            layers.append(cur)
            cur = stim.Circuit()
        else:
            cur.append(op)
    layers.append(cur)
    at = {}
    for i, (b, paulis, _) in enumerate(faults):
        if i != drop:
            at.setdefault(b + shift_ticks, []).append(paulis)
    assert max(at) <= len(layers) - 1, "boundary beyond the circuit"
    c = stim.Circuit()
    for li, lay in enumerate(layers):
        for paulis in at.get(li, []):
            for q, p in paulis.items():
                c.append(f"{p}_ERROR", [int(q)], 1.0)
        c += lay
        if li < len(layers) - 1:
            c.append("TICK")
    s = c.compile_detector_sampler().sample(1, append_observables=True)[0]
    nd = c.num_detectors
    return int(s[:nd].sum()), np.flatnonzero(s[nd:]).tolist()


def main(argv):
    Rs = [1, 2, 3, 5, 8, 12, 20, 30]
    shifts = [0, 2]
    if "--R" in argv:
        Rs = [int(x) for x in argv[argv.index("--R") + 1].split(",")]
    if "--shifts" in argv:
        shifts = [int(x) for x in argv[argv.index("--shifts") + 1].split(",")]
    names = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or not argv[i - 1].startswith("--"))]
    W = json.load(open(ROOT / "witnesses" / "persistence_R1.json"))["witnesses"]
    ok_all = True
    for w in W:
        if names and w["circuit"] not in names:
            continue
        faults = [(b, pa, g) for b, pa, g in w["faults"]]
        runs = []
        for k in shifts:
            for R in Rs:
                if R < 1 + k:
                    continue
                clean, P = clean_circuit(w["circuit"], w["basis"], R)
                nf, obs = inject(clean, faults, k * P)
                ctl = min(inject(clean, faults, k * P, drop=i)[0] for i in range(len(faults)))
                runs.append(nf == 0 and obs == w["observables"] and ctl > 0)
        ok = all(runs)
        ok_all &= ok
        print("PASS" if ok else "FAIL", w["circuit"], w["basis"], f"weight {len(faults)}:",
              f"{sum(runs)}/{len(runs)} (R, shift) cases undetected with the recorded logical effect, "
              "every single-fault removal detected")
    return ok_all


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1:]) else 1)
