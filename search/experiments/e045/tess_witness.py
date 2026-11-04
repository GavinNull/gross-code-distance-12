"""E-045 Part A upper bound: a weight-10 undetectable logical of the Tesseract gross circuit, replayed in stim on the
FULL (unprojected) circuit.  experimenter.

1. pbdfs (E-037, no proof) finds a weight-10 solution on the projected DEM (e045/tess_inst.py instance, W = 10).
2. Each projected column is (by hypothesis H, checked in tess.project: projected columns = full mechanisms without
   other-basis detectors) a full DEM mechanism; we check the 10 full mechanisms XOR to no detector at all (both
   bases) and a nonzero observable set.
3. stim explain_detector_error_model_errors (on the flattened circuit) gives one representative circuit fault per
   mechanism; the faults are injected with probability 1 into the noiseless circuit (all noise channels removed,
   noisy measurements made noiseless; a measurement flip is a Pauli just before the measurement).  Pass: no detector
   fires, the same observables flip; controls: nothing injected -> silent; each one fault dropped -> a detector fires.

    uv run python -m search.experiments.e045.tess_witness Z
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import stim

from search.experiments.e045 import tess

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results" / "E-045-crocker" / "witness"
BIN = ROOT / "results/E-037-ibm-cert/bin/pbdfs"


def find(basis, W=10):
    OUT.mkdir(parents=True, exist_ok=True)
    stem = str(OUT / f"tess_{basis}_W{W}_wit")
    subprocess.run([sys.executable, str(ROOT / "search/experiments/e045/tess_inst.py"), f"tess:gross:{basis}", str(W),
                    stem, "--no-symcheck"], check=True, capture_output=True)
    p = subprocess.run([str(BIN), stem + ".inst", "-R", stem + ".triv"], capture_output=True, text=True)
    sol = [l for l in p.stdout.splitlines() if l.startswith("SAT columns:")]
    for ext in (".opb", ".inst"):
        Path(stem + ext).unlink()
    return [int(x) for x in sol[-1].split(":")[1].split()] if sol else None


def noiseless(flat, inserts_after, inserts_before):
    out = stim.Circuit()
    for i, inst in enumerate(flat):
        for t in inserts_before.get(i, []):
            out.append("CORRELATED_ERROR", t, 1.0)
        gd = stim.gate_data(inst.name)
        if gd.is_noisy_gate and not gd.produces_measurements:
            pass
        elif gd.produces_measurements and inst.gate_args_copy():
            out.append(inst.name, inst.targets_copy())        # noiseless measurement
        else:
            out.append(inst)
        for t in inserts_after.get(i, []):
            out.append("CORRELATED_ERROR", t, 1.0)
    return out


def run(c):
    det, obs = c.compile_detector_sampler().sample(2, separate_observables=True)
    assert (det == det[0]).all() and (obs == obs[0]).all()
    return int(det[0].sum()), np.nonzero(obs[0])[0].tolist()


def main():
    basis = sys.argv[1]
    src = tess.source(basis)
    cols = find(basis)
    assert cols is not None
    circ = tess.circuit(basis)
    flat = circ.flattened()
    dm = tess.dem(basis)
    P = tess.project(dm)
    Aidx = P["Aidx"]
    full = P["full"]
    mech = []
    for j in cols:
        a = tuple(sorted(Aidx[x] for x in src["D"][j]))
        o = tuple(src["L"][j])
        assert (a, o) in full, "projected column is not a full mechanism without other-basis detectors"
        mech.append((a, o))
    dd, oo = set(), set()
    for a, o in mech:
        dd ^= set(a); oo ^= set(o)
    dem_ok = (not dd) and bool(oo)
    filt = stim.DetectorErrorModel()
    for a, o in mech:
        filt.append("error", 0.1, [stim.target_relative_detector_id(x) for x in a] +
                    [stim.target_logical_observable_id(x) for x in o])
    expl = flat.explain_detector_error_model_errors(dem_filter=filt, reduce_to_one_representative_error=True)
    assert len(expl) == len(mech)
    after, before, desc = [], [], []
    for e in expl:
        loc = e.circuit_error_locations[0]
        off = loc.stack_frames[0].instruction_offset
        targets = []
        for gt in loc.flipped_pauli_product:
            q = gt.gate_target.value
            p = "x" if gt.gate_target.is_x_target else ("y" if gt.gate_target.is_y_target else "z")
            targets.append(getattr(stim, f"target_{p}")(q))
        mm = loc.flipped_measurement
        kind = "pauli_after"
        if not targets:
            assert mm is not None and mm.observable
            g = mm.observable[0].gate_target
            q = g.value
            # flip a Z-basis measurement with X, an X-basis one with Z, just before the measuring instruction
            targets = [stim.target_x(q) if g.is_z_target else stim.target_z(q)]
            kind = "meas_flip_before"
        (before if kind == "meas_flip_before" else after).append((off, targets))
        desc.append(dict(instruction_offset=off, tick=loc.tick_offset, kind=kind,
                         paulis=str(loc.flipped_pauli_product), meas=str(mm) if mm else None))

    allf = [("a", o, t) for o, t in after] + [("b", o, t) for o, t in before]

    def circuit_with(sub):
        ia, ib = {}, {}
        for kind, o, t in sub:
            (ia if kind == "a" else ib).setdefault(o, []).append(t)
        return noiseless(flat, ia, ib)
    nd, ob = run(circuit_with(allf))
    e0 = run(circuit_with([]))
    drops = [run(circuit_with(allf[:i] + allf[i + 1:]))[0] for i in range(len(allf))]
    rec = dict(basis=basis, W=len(cols), projected_columns=cols, full_mechanisms=[[list(a), list(o)] for a, o in mech],
               dem_check_full=dem_ok, dem_observables=sorted(oo), detectors_fired=nd, observables_flipped=ob,
               control_empty=e0, drop_one_min_detectors=min(drops), faults=desc,
               ok=dem_ok and nd == 0 and ob == sorted(oo) and e0 == (0, []) and min(drops) > 0)
    with open(OUT / "witness.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps({k: v for k, v in rec.items() if k not in ("faults", "full_mechanisms")}))


if __name__ == "__main__":
    main()
