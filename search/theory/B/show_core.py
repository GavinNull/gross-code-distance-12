"""Print certificates: for logical i of a list, the core readers and, for each core reader, the two columns hitting it
with their option offsets (hooks: fixed; data: the set over cut options).
  uv run python -m search.theory.B.show_core --code gross --spec search/experiments/e032/u11_spec.json --basis Z \
     --list results/E-032-gross-short-period/w10_X_all_A1A2A3B3B1B2.pkl --analysis results/theoryB/analyze_u11_w10_Z.json --size 2 --count 2
"""
import argparse, json, pickle
from search.theory.B.bulk import ROOT, Sched, code_mats, load_spec
from search.theory.B.check_lists import colopts_for
from search.theory.B.analyze import describe_cols
ap = argparse.ArgumentParser()
for k in ("code", "spec", "basis", "list", "analysis"):
    ap.add_argument("--" + k)
ap.add_argument("--size", type=int, default=2); ap.add_argument("--count", type=int, default=2)
a = ap.parse_args()
sch = Sched(load_spec(a.spec), code_mats(a.code), a.basis)
cols, _ = sch.ext()
L = pickle.load(open(ROOT / a.list, "rb"))["keys"]
rows = json.load(open(ROOT / a.analysis))["rows"]
shown = 0
for r in rows:
    if r.get("core") is None or len(r["core"]) != a.size:
        continue
    S = L[r["i"]]; co = colopts_for(S, cols, sch); desc = describe_cols(S, cols, sch)
    print(f"logical {r['i']}: columns {desc}")
    for z in r["core"]:
        parts = []
        for j, opts in enumerate(co):
            vals = sorted({o[z] for o in opts if z in o})
            if vals:
                parts.append(f"{desc[j]}:{vals}")
        print(f"   reader Z{z}: " + "  ".join(parts))
    shown += 1
    if shown >= a.count:
        break
