"""B7 (arbitrary R): structural facts needed by the auditor's formal argument, checked on the evaluator circuits
for the IBM BB72 schedule.
 (1) separation: in the unrolled circuit, the last CNOT of the k-th cycle (over all ancillas) is strictly before
     the first CNOT of the (k+1)-th cycle (over all ancillas); every ancilla has exactly R cycles.
 (2) periodicity: the noisy circuit for R+1 rounds equals the one for R rounds with one block of 8 layers
     (a copy of the 8 layers just before the insertion point) inserted, at the same insertion point for all R
     (instructions compared as text, layer by layer; detectors / observables excluded, they are checked by (3)).
 (3) detectors: each detector of the R-round circuit compares cycle j and j-1 of one check of the memory basis
     (j = 0: cycle 0 alone), plus final detectors comparing the data readout with the last cycle.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, "tests")
import b_ibm  # noqa: E402

OUT = Path("results/E-014-E-015-audit")


def layers(circ):
    out, cur = [], []
    for inst in circ.flattened():
        if inst.name == "TICK":
            out.append(cur); cur = []
        elif inst.name in ("DETECTOR", "OBSERVABLE_INCLUDE"):
            continue
        else:
            cur.append(str(inst))
    out.append(cur)
    return out


def main(spec_name="ibm"):
    from evaluators.candidate import build_circuits
    from evaluators.noise import add_noise
    from evaluators.tasks import build_code, get_task
    css, _ = build_code(get_task("bb72-dcirc"), None)
    spec = b_ibm.ibm_spec()
    n = 72
    rep = {}
    # (1) separation + (3) detectors, R = 6, both bases
    for basis in "ZX":
        R = 6
        c = build_circuits(spec, css, R)[basis]
        tick = 0
        cyc = {}          # ancilla -> current cycle index
        cnot_ticks = {}   # cycle -> list of ticks
        meas_cycle = []   # measurement index -> (ancilla, cycle) or ('data', q)
        count = {}
        for inst in c.flattened():
            nm = inst.name
            t = [x.value for x in inst.targets_copy()] if nm not in ("DETECTOR", "OBSERVABLE_INCLUDE") else []
            if nm == "TICK":
                tick += 1
            elif nm in ("R", "RX"):
                for q in t:
                    if q >= n:
                        cyc[q] = count.get(q, 0)
            elif nm == "CX":
                for a, b in zip(t[::2], t[1::2]):
                    anc = a if a >= n else b
                    cnot_ticks.setdefault(cyc[anc], []).append(tick)
            elif nm in ("M", "MX"):
                for q in t:
                    if q >= n:
                        meas_cycle.append((q, count.get(q, 0)))
                        count[q] = count.get(q, 0) + 1
                    else:
                        meas_cycle.append(("d", q))
        ks = sorted(cnot_ticks)
        sep = all(max(cnot_ticks[k]) < min(cnot_ticks[k + 1]) for k in ks[:-1])
        # detectors
        det_ok = True
        nmeas = 0
        ndet = 0
        for inst in c.flattened():
            if inst.name in ("M", "MX"):
                nmeas += len(inst.targets_copy())
            if inst.name == "DETECTOR":
                ndet += 1
                recs = [meas_cycle[nmeas + x.value] for x in inst.targets_copy()]
                anc = [r for r in recs if r[0] != "d"]
                data = [r for r in recs if r[0] == "d"]
                if data:
                    ok = len(anc) == 1 and anc[0][1] == R - 1
                else:
                    js = sorted(r[1] for r in anc)
                    ok = len({r[0] for r in anc}) == 1 and (js == [0] or (len(js) == 2 and js[1] == js[0] + 1))
                    # only memory-basis checks: X ancillas are n..n+35 (X), Z ancillas n+36.. (Z)
                    q = anc[0][0]
                    ok &= (q >= n + 36) == (basis == "Z")
                det_ok &= ok
        rep[basis] = dict(cycles_per_ancilla=sorted(set(count.values())), separation=sep,
                          cnot_tick_ranges=[(min(cnot_ticks[k]), max(cnot_ticks[k])) for k in ks], detectors=ndet,
                          detectors_consecutive=det_ok)
    # (2) periodicity
    per = {}
    for basis in "ZX":
        Ls = {R: layers(add_noise(build_circuits(spec, css, R)[basis], "sd6", 1e-3)) for R in range(1, 12)}
        pts = []
        for R in range(1, 11):
            a, b = Ls[R], Ls[R + 1]
            assert len(b) == len(a) + 8
            cand = [i for i in range(8, len(a) + 1) if b == a[:i] + a[i - 8:i] + a[i:]]
            pts.append(cand)
        common = set(pts[1])
        for p in pts[1:]:
            common &= set(p)
        per[basis] = dict(R1_to_2_insertion_points=pts[0], insertion_points_R2_to_11_common=sorted(common)[:5],
                          all_R_ok=all(len(p) > 0 for p in pts))
    rep["periodicity"] = per
    print(json.dumps(rep, indent=None)[:3000])
    (OUT / "b7_periodic.json").write_text(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
