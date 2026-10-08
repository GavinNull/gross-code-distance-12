"""Find a minimum-weight undetected logical in the FULL DEM (both bases' detectors) of my circuit, explain each
column as a physical sd6 fault (stim explain), inject those faults as deterministic Paulis into the noiseless
circuit, and check: 0 detectors fire, >=1 observable flips.
usage: t3_witness.py code hom kind sa sb basis T model window W [orb]"""
import sys, json, subprocess, os
import numpy as np, stim
from inst import make, noisy, dem_columns, write_instance, NOISE_NAMES
R = '/Users/ephemeral/Desktop/qec-ai-search/results/E-019-audit'
code, hom, kind, sa, sb, basis, T, model, window, W = sys.argv[1:11]
sa, sb, T, W = int(sa), int(sb), int(T), int(W)
win = None if window == 'all' else tuple(map(int, window.split('-')))
M = make(code, hom, kind, sa, sb)
c, nc = noisy(M, basis, T, True, model, win)
ndet, nobs, cols = dem_columns(nc)
tag = f'wit_{code}_{hom}_{kind}{sa}{sb}_{basis}_T{T}_{model}_{window}'
path = f'{R}/inst/{tag}.txt'
write_instance(path, ndet, nobs, cols)
res = dict(tag=tag, ndet=ndet, cols=len(cols))
out = ''
for w in range(max(1, W - 1), W + 1):
    out = subprocess.run([f'{R}/mdfs', path, str(w)], capture_output=True, text=True).stdout
    res[f'W{w}'] = [l for l in out.splitlines() if l.startswith('SUMMARY')][0]
    fl = [l for l in out.splitlines() if l.startswith('FOUND')]
    if fl:
        break
if not fl:
    print(json.dumps(res)); sys.exit(0)
sel = [int(x) for x in fl[0].split('cols:')[1].split()]
res['weight'] = len(sel)
# explain each selected column
filt = stim.DetectorErrorModel()
for k in sel:
    D, O = cols[k]
    filt.append('error', 0.1, [stim.target_relative_detector_id(d) for d in D] + [stim.target_logical_observable_id(o) for o in O])
expl = nc.explain_detector_error_model_errors(dem_filter=filt, reduce_to_one_representative_error=True)
flat = nc.flattened()
# noiseless circuit with deterministic injections at the noise instruction positions
inj = {}
faults = []
for e in expl:
    loc = e.circuit_error_locations[0]
    off = loc.stack_frames[-1].instruction_offset
    pp = [(t.gate_target.value, t.gate_target.pauli_type) for t in loc.flipped_pauli_product]
    inj.setdefault(off, []).append(pp)
    nm = flat[off].name
    faults.append(dict(instr=nm, tick=loc.tick_offset,
                       paulis=[(('L' if q < M.N else 'R') + str(q % M.N), p) for q, p in pp]))
out_c = stim.Circuit()
for i, inst in enumerate(flat):
    if i in inj:
        for pp in inj[i]:
            for q, p in pp:
                out_c.append(p, [q])
    if inst.name in NOISE_NAMES:
        continue
    out_c.append(inst)
det, obs = out_c.compile_detector_sampler().sample(1, separate_observables=True)
res['faults'] = faults
res['detectors_fired'] = int(det.sum())
res['observables_flipped'] = int(obs.sum())
res['ok'] = bool(det.sum() == 0 and obs.sum() > 0)
res['kinds'] = sorted({f['instr'] for f in faults})
res['left_reset_or_idle'] = sum(1 for f in faults if f['instr'] in ('DEPOLARIZE1',) or (f['instr'] in ('X_ERROR', 'Z_ERROR') and all(q.startswith('L') for q, _ in f['paulis'])))
print(json.dumps(res))
with open(f'{R}/t3_log.jsonl', 'a') as fh:
    fh.write(json.dumps(res) + '\n')
