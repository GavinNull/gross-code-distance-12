"""C10: turn a DFS solution on MY round-1 instance (sp_x_repo_<B>_T4_r1.txt, same column order as
inst_x_repo_<B>_T4_r1.pkl) into concrete sd6 faults (pure X for Z memory / pure Z for X memory) and inject
them with probability 1 into the lead's gate-identical memory circuit (which has *all* X- and Z-type
detectors), R = 4 and also into my own circuits. Checks: 0 detectors, observable flipped.
usage: c10_posctl.py <basis> <adfs output file>
"""
import json, pickle, sys
sys.path.insert(0, "/Users/ephemeral/Desktop/qec-ai-search")
import numpy as np, stim
from search.experiments.e017.morph import TWO_GROSS, Morph

OUT = "/Users/ephemeral/Desktop/qec-ai-search/results/E-017-audit"
basis, fn = sys.argv[1], sys.argv[2]
P = pickle.load(open(f"{OUT}/c2_x_repo_{basis}_T4.pkl", "rb"))
I = pickle.load(open(f"{OUT}/inst_x_repo_{basis}_T4_r1.pkl", "rb"))
faults = P["faults"]
sets = [list(map(int, ln.split("cols:")[1].split())) for ln in open(fn) if ln.startswith("FOUND")]
want = "X" if basis == "Z" else "Z"
out = []
for S in sets[:5]:
    chosen = []
    for col in S:
        cand = [i for i in I["cols"][I["keys"][col]] if set(faults[i][4]) <= {want, "I"}]
        assert cand, (col, [faults[i][4] for i in I["cols"][I["keys"][col]]])
        chosen.append(faults[cand[0]])
    # inject into lead's memory circuit (first_j = 0 == my first round), all detectors present
    Mo = Morph(TWO_GROSS, "x", swap23=False)
    circ = Mo.memory_circuit(basis, 4, first_j=0)
    ins = {}
    for (r, li, kind, qs, pp, comp) in chosen:
        layer = li - 1 if kind == "meas" else li       # pre-measurement flip == end of previous layer
        for q, p in zip(qs, pp):
            if p != "I":
                ins.setdefault(layer, []).append((q, p))
    newc = stim.Circuit(); tick = 0
    for inst in circ.flattened():
        if inst.name == "TICK":
            for q, p in ins.get(tick, []):
                newc.append(f"{p}_ERROR", [q], 1.0)
            tick += 1
        newc.append(inst)
    det, obs = newc.compile_detector_sampler().sample(2, separate_observables=True)
    out.append(dict(cols=S, n_faults=len(chosen), distinct=len(set(map(tuple, [c[:5] for c in chosen]))),
                    faults=[list(map(str, c[:5])) for c in chosen],
                    detectors_fired=int(det[0].sum()), observables_flipped=int(obs[0].sum()),
                    total_detectors=newc.num_detectors))
print(json.dumps(out, indent=1))
json.dump(out, open(f"{OUT}/c10_{basis}.json", "w"), indent=1)
