"""E-022 audit: full-T memory circuit d_circ for an E-022 key, independent of the extended code / E-019 pipeline.
circuit = E-019 auditor's mycirc (gate sets matched to spec), detector-complete (noiseless sampling), stim DEM with
evaluators/noise.py sd6 (read only), CSS projection + K-orbit split, mdfs exhaustive at W = Wlo..Whi (stop at first hit),
then the first witness is injected (pure same-basis parts, prob-1 channels) into the circuit with ALL detectors of
both bases: require 0 detectors, >=1 observable.
usage: a3_dcirc.py key basis T Wlo Whi [window lo-hi]"""
import sys, json, subprocess, time
import stim
sys.path.insert(0, '/Users/ephemeral/Desktop/qec-ai-search/research/audits/2026-10-11-E-022-scripts')
from a1_build import build, OUT
from inst import noisy, NOISE_NAMES

def inject(M, basis, T, win, nc, cols, sel):
    filt = stim.DetectorErrorModel()
    for k in sel:
        D, O = cols[k]
        filt.append('error', 0.1, [stim.target_relative_detector_id(d) for d in D] + [stim.target_logical_observable_id(o) for o in O])
    expl = nc.explain_detector_error_model_errors(dem_filter=filt, reduce_to_one_representative_error=True)
    flat = nc.flattened()
    keep = 'X' if basis == 'Z' else 'Z'
    inj = {}; faults = []
    for e in expl:
        loc = e.circuit_error_locations[0]
        off = loc.stack_frames[-1].instruction_offset
        pp = [(t.gate_target.value, keep) for t in loc.flipped_pauli_product if t.gate_target.pauli_type in ('Y', keep)]
        inj.setdefault(off, []).append(pp)
        faults.append(dict(instr=flat[off].name, tick=loc.tick_offset, q=[q for q, _ in pp],
                           sides=''.join('L' if q < M.N else 'R' for q, _ in pp)))
    _, ncf = noisy(M, basis, T, True, 'sd6', win)
    ff = ncf.flattened()
    assert all(ff[o].name == flat[o].name and ff[o].targets_copy() == flat[o].targets_copy() for o in inj)
    oc = stim.Circuit()
    for i, inst in enumerate(ff):
        if i in inj:
            for pp in inj[i]:
                for q, p in pp:
                    oc.append(p + '_ERROR', [q], 1.0)
        if inst.name in NOISE_NAMES:
            continue
        oc.append(inst)
    det, obs = oc.compile_detector_sampler().sample(1, separate_observables=True)
    return dict(n_full_det=oc.num_detectors, det_fired=int(det.sum()), obs_flipped=int(obs.sum()),
                ok=bool(det.sum() == 0 and obs.sum() > 0), n_faults=len(expl), faults=faults)

if __name__ == '__main__':
    key, basis, T, Wlo, Whi = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
    win = tuple(map(int, sys.argv[6].split('-'))) if len(sys.argv) > 6 else None
    t0 = time.time()
    info, M, nc, cols = build(key, basis, T, False, win)
    runs = []; sel = None
    for W in range(Wlo, Whi + 1):
        t1 = time.time()
        out = subprocess.run([f'{OUT}/mdfs', info['path'], str(W)], capture_output=True, text=True).stdout
        fl = [l for l in out.splitlines() if l.startswith('FOUND')]
        nodes = sum(int(l.split()[5]) for l in out.splitlines() if l.startswith('CASE'))
        runs.append(dict(W=W, found=len(fl), nodes=nodes, sec=round(time.time() - t1, 1)))
        if fl:
            sel = [int(x) for x in fl[0].split('cols:')[1].split()]
            break
    info['runs'] = runs
    info['d_circ'] = len(sel) if sel else None
    info['lower_bound_exhaustive'] = (runs[-1]['W'] if sel is None else len(sel) - 1)
    if sel:
        info['inject'] = inject(M, basis, T, win, nc, cols, sel)
    info['sec'] = round(time.time() - t0, 1)
    print(json.dumps(info, default=str))
    with open(f'{OUT}/a3_log.jsonl', 'a') as fh:
        fh.write(json.dumps(info, default=str) + '\n')
