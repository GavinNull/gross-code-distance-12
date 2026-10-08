"""upper bound: weight-d~ end-cycle logical of C~1 (from mdfs on the code) injected as single-qubit errors on
left qubits in the reset layer of half-cycle 3 (data in C~1 there; = sd6 idle components), full-detector T=5."""
import sys, subprocess, json
import stim
from inst import make, half_cycle_layers
R = '/Users/ephemeral/Desktop/qec-ai-search/results/E-019-audit'
hom, kind, sa, sb, basis, d = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], int(sys.argv[6])
M = make('bb288', hom, kind, sa, sb)
err = 'X' if basis == 'Z' else 'Z'
out = subprocess.run([f'{R}/mdfs', f'{R}/ec/bb288_{hom}_{kind}{sa}{sb}_c1_{err}err.txt', str(d)], capture_output=True, text=True).stdout
qs = [int(x) for x in [l for l in out.splitlines() if l.startswith('FOUND')][0].split('cols:')[1].split()]
c = M.memory(basis, 5, full_detectors=True)
L3 = half_cycle_layers(5)[3][0]
layer = 0
oc = stim.Circuit()
for inst in c.flattened():
    if inst.name == 'TICK' and layer == L3:
        oc.append(err + '_ERROR', qs, 1.0)
    oc.append(inst)
    if inst.name == 'TICK':
        layer += 1
det, obs = oc.compile_detector_sampler().sample(1, separate_observables=True)
print(json.dumps(dict(circ=f'bb288_{hom}_{kind}{sa}{sb}', basis=basis, weight=len(qs), layer=L3, n_det=oc.num_detectors,
                      detectors_fired=int(det.sum()), observables_flipped=int(obs.sum()))))
