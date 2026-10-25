"""E-037 task 3: upper bounds.  Find an undetectable logical of weight W on the DEM (pbdfs, no proof) and verify it
by injecting one representative physical fault per column into the NOISELESS circuit and simulating it with stim:
every detector must be 0 and at least one observable must flip.  experimenter.

    uv run python search/experiments/e037/witness.py SOURCE W OUTDIR

SOURCE ibm:...: the fault for a column is the first member of the merged class (ibm_model fault descriptor), injected
as a deterministic X / Z / XX / ZZ in ibm_model.stim_circuit at the exact gate position.
SOURCE sd6:...: the fault is stim's representative circuit error for that DEM error
(explain_detector_error_model_errors, reduce_to_one_representative_error), injected as CORRELATED_ERROR(1) right after
the noise instruction it comes from, all other noise removed.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import stim

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import dem_inst  # noqa: E402
import ibm_model as im  # noqa: E402

BIN = ROOT / "results/E-037-ibm-cert/bin/pbdfs"


def find(source, W, out):
    stem = str(Path(out) / (source.replace(":", "_") + f"_W{W}_wit"))
    subprocess.run([sys.executable, str(HERE / "dem_inst.py"), source, str(W), stem, "--no-symcheck"],
                   check=True, capture_output=True)
    p = subprocess.run([str(BIN), stem + ".inst", "-R", stem + ".triv"], capture_output=True, text=True)
    sol = [l for l in p.stdout.splitlines() if l.startswith("SAT columns:")]
    for ext in (".opb", ".inst"):
        Path(stem + ext).unlink()
    return [int(x) for x in sol[-1].split(":")[1].split()] if sol else None


def strip_noise(c):
    out = stim.Circuit()
    for inst in c:
        if isinstance(inst, stim.CircuitRepeatBlock):
            out.append(stim.CircuitRepeatBlock(inst.repeat_count, strip_noise(inst.body_copy())))
        elif stim.gate_data(inst.name).is_noisy_gate and not stim.gate_data(inst.name).produces_measurements:
            continue
        else:
            out.append(inst)
    return out


def run_det(c):
    s = c.compile_detector_sampler()
    det, obs = s.sample(4, separate_observables=True)
    assert (det == det[0]).all() and (obs == obs[0]).all(), "not deterministic"
    return det[0], obs[0]


def verify_ibm(source, cols):
    _, code_name, typ, R = source.split(":")
    R = int(R)
    code = im.Code(code_name)
    raw = im.build_dem(code, typ, R, ibm_faithful=True, return_raw=True)
    m = im.merge(raw["det"], raw["logi"], raw["final"], raw["fdesc"], code, R, typ)
    faults = [raw["fdesc"][m["members"][j][0]] for j in cols]
    # deterministic injection into the noiseless stim circuit
    c = stim_inject(code, typ, R, faults)
    det, obs = run_det(c)
    return dict(n_faults=len(faults), detectors_fired=int(det.sum()), observables_flipped=np.nonzero(obs)[0].tolist(),
                faults=[(f[0], f[1], list(f[2]), list(f[3])) for f in faults])


def stim_inject(code, typ, R, faults):
    """ibm_model.stim_circuit with no noise and the listed faults (cycle, round, gate, qubits) injected."""
    want = {}
    for (cc, r, gt, qs) in faults:
        want.setdefault((cc, r, gt), []).append(qs)
    cyc = im.cycle(code)
    c = stim.Circuit()
    data = code.Lq + code.Rq
    c.append("R" if typ == "X" else "RX", data)
    c.append("R", code.Zq)
    c.append("RX", code.Xq)
    E = "X" if typ == "X" else "Z"
    nm = 0; rec = {}
    tgt = (lambda q: stim.target_x(q)) if E == "X" else (lambda q: stim.target_z(q))
    for cc in range(R + 2):
        for r, g in enumerate(cyc):
            for gt in g:
                k = gt[0]
                inj = want.get((cc, r, gt), [])
                before, _ = im.faults_for(gt, typ)
                if before:
                    for qs in inj:
                        c.append("CORRELATED_ERROR", [tgt(q) for q in qs], 1.0)
                if k == "CNOT":
                    c.append("CX", [gt[1], gt[2]])
                elif k == "PrepX":
                    c.append("RX", [gt[1]])
                elif k == "PrepZ":
                    c.append("R", [gt[1]])
                elif k == "MeasZ":
                    c.append("M", [gt[1]]); rec[(gt[1], cc)] = nm; nm += 1
                elif k == "MeasX":
                    c.append("MX", [gt[1]]); rec[(gt[1], cc)] = nm; nm += 1
                if not before:
                    for qs in inj:
                        c.append("CORRELATED_ERROR", [tgt(q) for q in qs], 1.0)
    checks = code.Zq if typ == "X" else code.Xq
    c.append("M" if typ == "X" else "MX", data)
    drec = {q: nm + j for j, q in enumerate(data)}
    nm += len(data)
    for cc in range(R + 2):
        for i, q in enumerate(checks):
            t = [stim.target_rec(rec[(q, cc)] - nm)]
            if cc:
                t.append(stim.target_rec(rec[(q, cc - 1)] - nm))
            c.append("DETECTOR", t, [i, cc])
    Lop = code.lz if typ == "X" else code.lx
    for kk, row in enumerate(Lop):
        c.append("OBSERVABLE_INCLUDE", [stim.target_rec(drec[data[j]] - nm) for j in np.nonzero(row)[0]], kk)
    # sanity: noiseless circuit is deterministic with all-zero detectors (checked by the caller via an empty list)
    return c


def verify_sd6(source, cols):
    _, code_name, basis, R = source.split(":")
    circ, _ = dem_inst.sd6_circuit(code_name, basis, int(R))
    src = dem_inst.load_source(source)
    # stim DEM error for each column, then its representative circuit error
    filt = stim.DetectorErrorModel()
    for j in cols:
        t = [stim.target_relative_detector_id(x) for x in src["D"][j]] + \
            [stim.target_logical_observable_id(x) for x in src["L"][j]]
        filt.append("error", 0.1, t)
    expl = circ.explain_detector_error_model_errors(dem_filter=filt, reduce_to_one_representative_error=True)
    assert len(expl) == len(cols)
    if not cols:
        expl = []
    flat = circ.flattened()
    inserts = {}
    desc = []
    for e in expl:
        loc = e.circuit_error_locations[0]
        off = loc.stack_frames[0].instruction_offset
        targets = []
        for gt in loc.flipped_pauli_product:
            q = gt.gate_target.value
            p = "X" if gt.gate_target.is_x_target else ("Y" if gt.gate_target.is_y_target else "Z")
            targets.append(getattr(stim, f"target_{p.lower()}")(q))
        mm = loc.flipped_measurement
        if mm is not None and mm.measurement_record_index is not None and not targets:
            # a measurement flip: realise as a Pauli just before the measuring instruction
            q = mm.observable[0].gate_target.value if mm.observable else None
            p = "X" if (mm.observable and mm.observable[0].gate_target.is_x_target) else "Z"
            # the noise instruction preceding a measurement in sd6 is X_ERROR / Z_ERROR on the measured qubit
            targets.append(stim.target_x(q) if p == "Z" else stim.target_z(q))
        assert targets, ("no Pauli for", e)
        inserts.setdefault(off, []).append(targets)
        desc.append(dict(instruction_offset=off, tick=loc.tick_offset, paulis=str(loc.flipped_pauli_product)))
    out = stim.Circuit()
    for i, inst in enumerate(flat):
        gd = stim.gate_data(inst.name)
        if not (gd.is_noisy_gate and not gd.produces_measurements):
            out.append(inst)
        for t in inserts.get(i, []):
            out.append("CORRELATED_ERROR", t, 1.0)
    det, obs = run_det(out)
    return dict(n_faults=len(cols), detectors_fired=int(det.sum()), observables_flipped=np.nonzero(obs)[0].tolist(),
                faults=desc)


def main():
    source, W, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    Path(out).mkdir(parents=True, exist_ok=True)
    cols = find(source, W, out)
    rec = dict(source=source, W=W, found=cols is not None)
    if cols is not None:
        rec["columns"] = cols
        v = verify_ibm(source, cols) if source.startswith("ibm") else verify_sd6(source, cols)
        rec.update(v)
        # controls: no injected fault -> silent and no flip; dropping one fault -> some detector fires
        f = verify_ibm if source.startswith("ibm") else verify_sd6
        c0 = f(source, [])
        c1 = f(source, cols[:-1])
        rec["control_empty"] = dict(detectors_fired=c0["detectors_fired"], observables_flipped=c0["observables_flipped"])
        rec["control_drop_one"] = dict(detectors_fired=c1["detectors_fired"])
        rec["ok"] = (v["detectors_fired"] == 0 and len(v["observables_flipped"]) > 0 and v["n_faults"] == W
                     and c0["detectors_fired"] == 0 and not c0["observables_flipped"] and c1["detectors_fired"] > 0)
    with open(Path(out) / "witness.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps({k: rec[k] for k in rec if k != "faults"}))


if __name__ == "__main__":
    main()
