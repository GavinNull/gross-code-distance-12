"""inject the experimenter's recorded witness (results/E-019-morphing-family/solve_<key>_<b>_T4.json) into MY
independently built full-detector circuit (same qubit labelling; gate identity checked in t8_compare.py).
Their round 1 = my half-cycle 2 (they start with the other contraction circuit; checked by locating their CX
pairs): their layer k of round 1 -> my layer 8 + k (8 = reset layer of my half-cycle 2, 9..14 = CX layers).
A 'reset' fault of theirs on a qubit my layer 8 resets -> flip after that reset; on a qubit my layer 8 does not
reset (left/data qubit: in their round 1 it is the initial data reset) -> same Pauli as an idle error in layer 8
(an sd6 DEPOLARIZE1 component; would not exist in a no-idle model).
usage: t9_theirwit.py key basis code hom kind sa sb"""
import sys, json
import stim
from inst import make
key, b, code, hom, kind, sa, sb = sys.argv[1:8]
SHIFT = 8
M = make(code, hom, kind, int(sa), int(sb))
d = json.load(open(f'/Users/ephemeral/Desktop/qec-ai-search/results/E-019-morphing-family/solve_{key}_{b}_T4.json'))
faults = d['injections']['dfs_witness']['faults']
c = M.memory(b, 4, full_detectors=True)
layer = 0
out = stim.Circuit()
placed = []
for inst in c.flattened():
    if inst.name == 'TICK' and layer == SHIFT:
        for f in faults:
            if f['kind'] == 'reset' and '_p' not in f:
                out.append(f['pauli'] + '_ERROR', [f['qubits'][0]], 1.0)
                f['_p'] = 'idle(L%d)' % f['qubits'][0] if f['qubits'][0] < M.N else 'idle(R)'
    out.append(inst)
    if inst.name == 'TICK':
        layer += 1
        continue
    tq = [t.value for t in inst.targets_copy() if t.is_qubit_target]
    for f in faults:
        if f['round'] != 1 or f['layer'] + SHIFT != layer or '_p' in f:
            continue
        if f['kind'] == 'reset' and inst.name in ('R', 'RX') and f['qubits'][0] in tq:
            out.append(f['pauli'] + '_ERROR', [f['qubits'][0]], 1.0)
            f['_p'] = inst.name + '-flip'
        if f['kind'] == 'cx' and inst.name == 'CX':
            if tuple(f['qubits']) in set(zip(tq[::2], tq[1::2])):
                for q, p in zip(f['qubits'], f['pauli']):
                    if p != 'I':
                        out.append(p + '_ERROR', [q], 1.0)
                f['_p'] = 'cx'
det, obs = out.compile_detector_sampler().sample(1, separate_observables=True)
print(json.dumps(dict(key=key, basis=b, placed=[f.get('_p') for f in faults], n_det=out.num_detectors,
                      detectors_fired=int(det.sum()), observables_flipped=int(obs.sum()))))
