"""E-019: independent check of below-d witnesses (standard variants only) with E-017's morph.py, whose detectors
(X and Z type) and observables are built by its own Pauli propagation: inject the lifted witness faults into
morph.Morph(BB(l,m,A,B), hom, swap23).memory_circuit(basis, 4, first_j=0) and count fired detectors.
usage: uv run python -m search.experiments.e019.crosscheck_morph <key> <basis>"""
import json, sys
import stim
from search.experiments.e017.morph import BB, Morph, check_deterministic
from search.experiments.e019.common import CODES

RES = "/Users/ephemeral/Desktop/qec-ai-search/results/E-019-morphing-family"
key, basis = sys.argv[1], sys.argv[2]
name, hom, v = key.split("_")
assert v in ("repo", "paper")
l, m, A, B = CODES[name]
M = Morph(BB(l, m, A, B), hom, swap23=(v == "paper"))
circ = M.memory_circuit(basis, 4, first_j=0)
assert all(check_deterministic(circ))
s = json.load(open(f"{RES}/solve_{key}_{basis}_T4.json"))
w = s["injections"]["dfs_witness"]
ins = {}
for f in w["faults"]:
    tk = f["layer"] - 1 if f["kind"] == "meas" else f["layer"]
    for q, p in zip(f["qubits"], f["pauli"]):
        if p != "I":
            ins.setdefault(tk, []).append((q, p))
newc = stim.Circuit(); tick = 0
for inst in circ.flattened():
    if inst.name == "TICK":
        for q, p in ins.get(tick, []):
            newc.append(f"{p}_ERROR", [q], 1.0)
        tick += 1
    newc.append(inst)
det, obs = newc.compile_detector_sampler().sample(2, separate_observables=True)
out = dict(key=key, basis=basis, weight=w["weight"], detectors_fired=int(det[0].sum()),
           observables_flipped=int(obs[0].sum()), n_detectors=newc.num_detectors)
print(json.dumps(out))
json.dump(out, open(f"{RES}/crosscheck_{key}_{basis}.json", "w"))
