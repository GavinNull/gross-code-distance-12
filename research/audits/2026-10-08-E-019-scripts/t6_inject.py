"""Witness check: min-weight solution of the CSS instance (mdfs, orbit split) -> explain each column as a physical
sd6/no-idle fault -> keep its pure same-basis part (X part for Z memory, Z part for X memory; this is itself a
component of the same channel) -> inject deterministically into the noiseless circuit that carries ALL detectors
of both bases -> require 0 detectors fired and >= 1 observable flipped.
usage: t6_inject.py code hom kind sa sb basis T model window W"""
import sys, json, subprocess
import numpy as np, stim
from inst import make, noisy, dem_columns, orbits, write_instance, NOISE_NAMES
R = '/Users/ephemeral/Desktop/qec-ai-search/results/E-019-audit'
code, hom, kind, sa, sb, basis, T, model, window, W = sys.argv[1:11]
CASE = sys.argv[11:12]  # optional single orbit case for mdfs
sa, sb, T, W = int(sa), int(sb), int(T), int(W)
win = None if window == 'all' else tuple(map(int, window.split('-')))
M = make(code, hom, kind, sa, sb)
c0, nc = noisy(M, basis, T, False, model, win)
ndet, nobs, cols = dem_columns(nc)
orb, norb = orbits(M, M.memory(basis, T, full_detectors=False), cols, None)
tag = f'inj_{code}_{hom}_{kind}{sa}{sb}_{basis}_T{T}_{model}_{window}'
path = f'{R}/inst/{tag}.txt'
write_instance(path, ndet, nobs, cols, orb, norb)
fl = []
for w in (range(W - 1, W + 1) if not CASE else [W]):
    out = subprocess.run([f'{R}/mdfs', path, str(w)] + CASE, capture_output=True, text=True).stdout
    fl = [l for l in out.splitlines() if l.startswith('FOUND')]
    if fl:
        break
res = dict(tag=tag, weight=None)
if not fl:
    print(json.dumps(res)); sys.exit()
sel = [int(x) for x in fl[0].split('cols:')[1].split()]
res['weight'] = len(sel)
filt = stim.DetectorErrorModel()
for k in sel:
    D, O = cols[k]
    filt.append('error', 0.1, [stim.target_relative_detector_id(d) for d in D] + [stim.target_logical_observable_id(o) for o in O])
expl = nc.explain_detector_error_model_errors(dem_filter=filt, reduce_to_one_representative_error=True)
flat = nc.flattened()
keep = 'X' if basis == 'Z' else 'Z'
inj = {}
faults = []
for e in expl:
    loc = e.circuit_error_locations[0]
    off = loc.stack_frames[-1].instruction_offset
    pp = []
    for t in loc.flipped_pauli_product:
        p = t.gate_target.pauli_type
        if p == 'Y' or p == keep:
            pp.append((t.gate_target.value, keep))
    inj.setdefault(off, []).append(pp)
    side = ''.join('L' if q < M.N else 'R' for q, _ in pp)
    faults.append(dict(instr=flat[off].name, tick=loc.tick_offset, pure=''.join(p for _, p in pp), sides=side))
# full-detector circuit with identical noise-instruction offsets
c1, nc_full = noisy(M, basis, T, True, model, win)
flat_full = nc_full.flattened()
assert all(flat_full[o].name == flat[o].name and flat_full[o].targets_copy() == flat[o].targets_copy() for o in inj)
out_c = stim.Circuit()
for i, inst in enumerate(flat_full):
    if i in inj:
        for pp in inj[i]:
            for q, p in pp:
                out_c.append(p + "_ERROR", [q], 1.0)
    if inst.name in NOISE_NAMES:
        continue
    out_c.append(inst)
det, obs = out_c.compile_detector_sampler().sample(1, separate_observables=True)
res.update(n_full_detectors=out_c.num_detectors, detectors_fired=int(det.sum()), observables_flipped=int(obs.sum()),
           ok=bool(det.sum() == 0 and obs.sum() > 0), faults=faults)
cnt = {}
for f in faults:
    k = f['instr'] + ':' + f['sides']
    cnt[k] = cnt.get(k, 0) + 1
res['fault_types'] = cnt
print(json.dumps(res))
with open(f'{R}/t6_log.jsonl', 'a') as fh:
    fh.write(json.dumps(res) + '\n')
