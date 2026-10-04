"""E-006 (c): archive and injection-verify low-weight decoder-failure examples.

For a sector column set S: pick for each column one joint DEM mechanism mapping to it (preferring mechanisms whose
projection onto the other sector is empty), locate one circuit fault for it (stim explain_detector_error_model_errors),
inject those faults with probability 1 into the noiseless joint circuit and check that the fired detectors /
flipped observables equal H e / L e of the claimed configuration in this sector (and the other sector's pattern
equals the projection of the chosen mechanisms). Then re-decode the injected syndrome with the decoders and MLE.

uv run python -m search.decoders.inject results/E-006-decoder-headroom/wdec/bb72_p0.001.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

import numpy as np
import stim

from evaluators.distance import _faults_from_explained, _is_pure_noise
from search.decoders import decoders as D
from search.decoders.common import build_model


def injected_circuit(flat: stim.Circuit, faults) -> stim.Circuit:
    noiseless_flat = flat
    by_off = defaultdict(list)
    for f in faults:
        by_off[f.instruction_offset].append(f)
    flip_recs = {f.measurement_record for f in faults if f.measurement_record is not None}
    out = stim.Circuit()
    meas = 0
    for i, inst in enumerate(noiseless_flat):
        name = inst.name
        g = stim.gate_data(name)
        if _is_pure_noise(name):
            for f in by_off.get(i, []):
                for p in f.paulis:
                    out.append(f"{p[0]}_ERROR", [int(p[1:])], 1.0)
            continue
        if g.produces_measurements:
            nrec = inst.num_measurements
            if any(meas + k in flip_recs for k in range(nrec)):
                raise NotImplementedError("measurement-record flips (M(p) noise) are not used by sd6")
            out.append(inst)          # keep MPP products etc. intact
            meas += nrec
            for f in by_off.get(i, []):
                for p in f.paulis:
                    out.append(f"{p[0]}_ERROR", [int(p[1:])], 1.0)
            continue
        if g.is_noisy_gate and inst.gate_args_copy():
            out.append(name, inst.targets_copy())
        else:
            out.append(inst)
    assert meas == flat.num_measurements
    return out


def realise(m, s, cols):
    sec = m.sectors[s]
    other = m.sectors["Y" if False else ("X" if s == "Z" else "Z")]
    js = []
    for c in cols:
        cand = np.flatnonzero(sec.j2c == c)
        pure = [j for j in cand if other.j2c[j] < 0 and other.j2free[j] == 0]
        js.append(int(pure[0] if pure else cand[0]))
    return js


def verify(m, s, cols, decs=None, ref=None):
    flat = m.circuit.flattened()
    dem = m.dem.flattened()
    errs = [inst for inst in dem if inst.type == "error"]
    js = realise(m, s, cols)
    sub = stim.DetectorErrorModel()
    for j in js:
        sub.append(errs[j])
    expl = flat.explain_detector_error_model_errors(dem_filter=sub, reduce_to_one_representative_error=True)
    faults = _faults_from_explained(expl)
    assert len(faults) == len(js), (len(faults), len(js))
    circ = injected_circuit(flat, faults)
    det, obs = circ.compile_detector_sampler(seed=1).sample(2, separate_observables=True)
    det, obs = det[0], obs[0]
    sec = m.sectors[s]
    e = np.zeros(sec.H.shape[1], np.uint8)
    e[list(cols)] ^= 1
    syn = (sec.H.tocsr() @ e) % 2
    ob = (sec.L @ e) % 2
    d_s = det[:m.nz] if s == "Z" else det[m.nz:]
    o_s = obs[:m.oz] if s == "Z" else obs[m.oz:]
    ok = bool(np.array_equal(d_s.astype(np.uint8), syn) and np.array_equal(o_s.astype(np.uint8), ob))
    rec = {"sector": s, "columns": [int(c) for c in cols], "joint_mechanisms": js,
           "faults": [f.describe() for f in faults], "injection_matches_sector_syndrome_and_observables": ok,
           "other_sector_detectors_fired": int((det[m.nz:] if s == "Z" else det[:m.nz]).sum())}
    if decs is not None:
        rec["redecode"] = {}
        for nm, dec in decs.items():
            eh = dec.decode(d_s.astype(np.uint8))
            rec["redecode"][nm] = "fail" if ((sec.L @ eh) % 2 != o_s).any() else "ok"
        r = ref.decode(d_s.astype(np.uint8), time_limit=300)
        rec["redecode"]["ref"] = ("fail" if ((sec.L @ r.e) % 2 != o_s).any() else "ok") + f" ({r.status})"
    return rec


def main():
    path = sys.argv[1]
    names = tuple(sys.argv[2].split(",")) if len(sys.argv) > 2 else ("bposd", "relay5", "relay1")
    data = json.loads(open(path).read())
    meta = data["meta"]["args"]
    m = build_model(meta["code"], meta["p"])
    decs = {s: D.make(m.sectors[s], names) for s in "ZX"}
    refs = {s: D.make_ref(m.sectors[s]) for s in "ZX"}
    hits = data["hits"]
    # keep: lowest weight examples where some decoder fails and ref succeeds (all of them up to 50 per weight/decoder)
    out = []
    seen = defaultdict(int)
    for h in sorted(hits, key=lambda h: len(h["cols"])):
        if h["ref_fail"]:
            continue
        key = (len(h["cols"]), tuple(sorted(k for k, v in h["fail"].items() if v)))
        if seen[key] >= 25:
            continue
        seen[key] += 1
        s = h["group"][0]
        rec = verify(m, s, h["cols"], decs[s], refs[s])
        rec.update({"weight": len(h["cols"]), "failing_decoders": [k for k, v in h["fail"].items() if v],
                    "group": h["group"], "W_true": h["W_true"], "W_ref": h["W_ref"]})
        out.append(rec)
    dst = path.replace(".json", "_examples.json")
    open(dst, "w").write(json.dumps(out, indent=1))
    okc = sum(r["injection_matches_sector_syndrome_and_observables"] for r in out)
    print(f"{len(out)} examples archived, injection ok {okc}; -> {dst}")
    for k, v in sorted(seen.items()):
        print(" weight", k[0], "failing", k[1], "archived", v)


if __name__ == "__main__":
    main()
