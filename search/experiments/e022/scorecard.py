"""E-022: prediction scorecard for the held-out circuits (tier A from the yaml, tier B rules) against the E-019
pipeline (e019pipe/solve_*.json) and the auditor-construction check (aud_*.json)."""
import glob
import json
import math
from collections import Counter, defaultdict

import yaml

R = "/Users/ephemeral/Desktop/qec-ai-search/results/E-022-morphing-criterion"
Y = yaml.safe_load(open("/Users/ephemeral/Desktop/qec-ai-search/experiments/E-022-morphing-criterion.yaml"))
pred = Y["heldout_predictions_tierA"]["d_circ"]
T = json.load(open(f"{R}/table.json"))
pipe = defaultdict(dict)
for f in glob.glob(f"{R}/e019pipe/solve_*_T4.json"):
    o = json.load(open(f))
    pipe[o["key"]][o["basis"]] = o
aud = defaultdict(dict)
for f in glob.glob(f"{R}/aud_*.json"):
    o = json.load(open(f))
    aud[o["key"]][o["basis"]] = o

out = dict(n_pred=len(pred))
# tier A
cA = Counter()
bad = []
checks_bad = []
for k, d in pred.items():
    if k not in pipe or len(pipe[k]) < 2:
        cA["pending"] += 1
        continue
    for b in "ZX":
        o = pipe[k][b]
        ok_checks = all(o["checks"].get(x) in (True, 0) for x in ("stim_eq_mine", "all_rounds_equivalent", "fold_ok")) \
            and o["checks"].get("locality_violations") == 0
        if not ok_checks:
            checks_bad.append((k, b, o["checks"]))
        if o.get("d_circ") == d:
            cA["hit"] += 1
        else:
            cA["miss"] += 1
            bad.append((k, b, d, o.get("d_circ"), o.get("status")))
out["tierA_vs_e019pipe"] = dict(cA)
out["tierA_misses"] = bad
out["e019_checks_failed"] = checks_bad
cAu = Counter()
abad = []
for k in aud:
    for b, o in aud[k].items():
        if o.get("d_circ_T4") == pred.get(k):
            cAu["hit"] += 1
        else:
            cAu["miss"] += 1
            abad.append((k, b, pred.get(k), o.get("d_circ_T4"), o.get("auditor_label")))
out["tierA_vs_auditor_T4"] = dict(cAu)
out["auditor_misses"] = abad


# tier B (truth = E-019 pipeline Z value where available)
def truth(k):
    return pipe[k]["Z"]["d_circ"] if k in pipe and "Z" in pipe[k] else None


B = Counter()
for k in pred:
    t = truth(k)
    if t is None:
        continue
    de = T[k]["d_end"]
    B["B1_n"] += 1
    B["B1_ok"] += t >= math.ceil(2 * de / 3)
    if de <= 5:
        B["B2_n"] += 1
        B["B2_ok"] += t == de
    if "X" in pipe[k]:
        B["B4_n"] += 1
        B["B4_ok"] += pipe[k]["X"]["d_circ"] == t
    if de >= 3:
        B["B5_n"] += 1
        B["B5_loss"] += t < de
groups = defaultdict(list)
for k in pred:
    t = truth(k)
    if t is None:
        continue
    nm, hom, v = k.split("_")
    if v in ("repo", "paper", "std01", "std10"):
        groups[(nm, hom)].append(t < T[k]["d_end"])
for g, ls in groups.items():
    if len(ls) == 4 and any(ls):
        B["B3_n"] += 1
        B["B3_ok"] += all(ls)
out["tierB"] = dict(B)
json.dump(out, open(f"{R}/scorecard.json", "w"), indent=1, default=str)
print(json.dumps({k: v for k, v in out.items() if not k.endswith("misses")}, default=str))
print("tierA misses", bad[:20])
print("auditor misses", abad[:20])
