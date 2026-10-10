"""E-022: collect per-circuit quantities (Z basis unless noted) into results/E-022-morphing-criterion/table.json."""
import glob, json, os
R = "/Users/ephemeral/Desktop/qec-ai-search/results/E-022-morphing-criterion"
T = {}
for f in glob.glob(f"{R}/enddist_*.json"):
    o = json.load(open(f)); T.setdefault(o["key"], {})["d_end"] = o["d_end"]
for f in glob.glob(f"{R}/pred_*.json"):
    o = json.load(open(f)); T.setdefault(o["key"], {})[f"{o['half']}_{o['basis']}"] = o["d_ext"]
for f in glob.glob(f"{R}/mid_*.json"):
    o = json.load(open(f)); T.setdefault(o["key"], {})[f"{o['model']}_{o['basis']}"] = o["d"]
train = set(open(f"{R}/train_keys.txt").read().split())
for k in T:
    T[k]["train"] = k in train
json.dump(T, open(f"{R}/table.json", "w"), indent=1, sort_keys=True)
print(len(T))
