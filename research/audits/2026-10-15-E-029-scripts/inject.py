"""Auditor (E-029): confirm ccsearch witnesses by injecting physical faults into the noiseless circuit.

    PYTHONPATH=.:tests uv run python research/audits/2026-10-15-E-029-scripts/inject.py CIRCUIT_JSON BASIS R INST RUNFILE

For each SOL line: map column ids -> (detector set, observable set) via the experimenter's instance file; ask stim
to explain each DEM mechanism as a concrete circuit fault (one representative Pauli at one noise instruction);
build a circuit with ALL noise channels removed and exactly those Paulis inserted with probability 1; sample once
(deterministic) and check that every detector is 0 and the observable flips equal the claimed ones.  Also: each
single fault on its own reproduces its DEM column, and dropping any one fault makes detectors fire.
"""
import json
import sys

import numpy as np
import stim

sys.path[:0] = [".", "tests"]
from evaluators.candidate import build_circuits, parse_schedule  # noqa: E402
from evaluators.noise import add_noise  # noqa: E402
from evaluators.tasks import build_code, get_task  # noqa: E402

NOISE = {"DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Y_ERROR", "Z_ERROR", "PAULI_CHANNEL_1", "PAULI_CHANNEL_2",
         "E", "ELSE_CORRELATED_ERROR", "HERALDED_ERASE", "HERALDED_PAULI_CHANNEL_1"}


def load_inst(path):
    lines = open(path).read().split("\n")
    nr, nc, no, norb = map(int, lines[0].split())
    cols = []
    for ln in lines[1:1 + nc]:
        v = list(map(int, ln.split()))
        k = v[0]
        cols.append((tuple(v[1:1 + k]), tuple(v[2 + k:2 + k + v[1 + k]])))
    return cols


def build(noisy_flat, locs):
    """noiseless copy with given fault locations inserted (Paulis applied right after the noise instruction)."""
    ins_at = {}
    for loc in locs:
        assert loc.flipped_measurement is None or loc.flipped_measurement.record_index < 0 or True
        off = loc.stack_frames[-1].instruction_offset
        ins_at.setdefault(off, []).append(loc)
    out = stim.Circuit()
    for i, inst in enumerate(noisy_flat):
        if inst.name in NOISE:
            for loc in ins_at.get(i, []):
                for t in loc.flipped_pauli_product:
                    gt = t.gate_target
                    p = "X" if gt.is_x_target else "Y" if gt.is_y_target else "Z"
                    out.append(f"{p}_ERROR", [gt.value], 1.0)
            continue
        if inst.name in ("M", "MX", "MY", "MR", "MRX", "MZ") and inst.gate_args_copy():
            # measurement with built-in flip probability
            flips = [loc for loc in ins_at.get(i, []) if loc.flipped_measurement is not None]
            assert not flips, "measurement-flip faults not handled"
            out.append(inst.name, inst.targets_copy())
            continue
        assert i not in ins_at, (i, inst)
        out.append(inst)
    return out


def sample(c):
    det, obs = c.compile_detector_sampler().sample(1, separate_observables=True)
    return set(np.nonzero(det[0])[0].tolist()), set(np.nonzero(obs[0])[0].tolist())


def main():
    path, basis, R, inst, run = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5]
    import os
    code, _ = build_code(get_task(os.environ.get("TASK", "gross-dcirc")), None)
    spec = parse_schedule(json.load(open(path)))
    noisy = add_noise(build_circuits(spec.canonical(), code, R)[basis], "sd6", 1e-3).flattened()
    assert all(not i.gate_args_copy() for i in noisy if i.name in ("M", "MX", "MR")), "noisy measurements present"
    cols = load_inst(inst)
    # sanity: a noiseless run gives no detectors / observables
    assert sample(build(noisy, [])) == (set(), set())
    for ln in open(run):
        if not ln.startswith("SOL"):
            continue
        ids = [int(x) for x in ln.split(":")[1].split()]
        claimed_obs = int(ln.split("obs=")[1].split()[0], 16)
        locs = []
        for j in ids:
            d, o = cols[j]
            dem = stim.DetectorErrorModel()
            dem.append("error", 0.001, [stim.target_relative_detector_id(x) for x in d]
                       + [stim.target_logical_observable_id(x) for x in o])
            ex = noisy.explain_detector_error_model_errors(dem_filter=dem, reduce_to_one_representative_error=True)
            assert len(ex) == 1 and ex[0].circuit_error_locations, ("no circuit fault for column", j)
            loc = ex[0].circuit_error_locations[0]
            got = sample(build(noisy, [loc]))
            assert got == (set(d), set(o)), ("single fault does not reproduce column", j, got, d, o)
            locs.append(loc)
        dets, obs = sample(build(noisy, locs))
        obsmask = sum(1 << x for x in obs)
        drop_ok = all(sample(build(noisy, locs[:k] + locs[k + 1:]))[0] for k in range(len(locs)))
        print(json.dumps(dict(weight=len(ids), distinct=len(set(ids)) == len(ids), detectors_fired=len(dets),
                              observables=sorted(obs), matches_claimed_obs=obsmask == claimed_obs,
                              every_proper_drop_fires_detectors=drop_ok,
                              faults=[f"{l.stack_frames[-1].instruction_offset}:{l.flipped_pauli_product}" for l in locs])))


if __name__ == "__main__":
    main()
