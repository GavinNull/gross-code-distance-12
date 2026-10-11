"""E-025: human-readable description of a colour-symmetric core (list of orbit reps).
For each rep: logical kind, hooks (class of the hook check, pinned labels and their positions in the unit's Fig. 12
order), number of free data qubits, number of readers per check, and in a given model-blocking circuit (optional)
the shortest negative cycle with its intra-check drifts."""
import json, sys
import search.experiments.e021.nwfull as NF
from search.experiments.e021.mono import LAB, fig12_labels
from search.experiments.e025.exact_cp import make_family

core = json.load(open(sys.argv[1]))
F = make_family("1,2;0,3")
recs, _ = NF.prepare_full(F, "XZ")
f12 = fig12_labels()
for k in core["core"]:
    r = recs[k]
    kind = r["kind"]
    hooks = []
    nfree = 0
    for e in r["evs"]:
        if e[0] == "d":
            nfree += 1
        else:
            a = e[1]
            o = f12[kind][a]
            labs = sorted(F.label_of(kind, a, q) for q in e[2])
            pos = sorted(o.index(l) + 1 for l in labs)
            hooks.append(f"{kind}{F.cls[a]}:{'/'.join(LAB[l] for l in labs)}@pos{pos}")
    multi = sum(1 for v in r["rc"].values() if len(v) > 2)
    print(f"rep {k:3d} {kind}-type  hooks {hooks}  free {nfree}  readers-with-4 {multi}")
