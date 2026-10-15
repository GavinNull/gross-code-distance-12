"""Selector/disjunction test with the package's own Builder: a batch of circuit-A instances (Z, R=1) is UNSAT; the same
batch with ONE member replaced by the Fig. 12 instance of the same logical becomes SAT, and in every model found the
only selector that can be true is the substituted one (checked by forcing each selector in turn)."""
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "release/zenodo/code/proofs"))
import lift_cnf as LC
CAD = str(ROOT / "tools/cadical/build/cadical")

def solve(b, extra=()):
    cl = b.clauses + [list(e) for e in extra]
    t = f"p cnf {b.n} {len(cl)}\n" + "".join(" ".join(map(str, c)) + " 0\n" for c in cl)
    p = subprocess.run([CAD, "-q"], input=t.encode(), capture_output=True)
    m = {int(x) for l in p.stdout.decode().splitlines() if l.startswith("v") for x in l.split()[1:]}
    return {10: "SAT", 20: "UNSAT"}[p.returncode], m

lA, gA, _ = LC.setup("A", "Z", 1)
lF, gF, _ = LC.setup("fig12", "Z", 1)
idx = list(range(0, 4224, 211))[:20]
def build(sub):
    b = LC.Builder()
    sel = [b.new() for _ in idx]
    b.clauses.append(list(sel))
    for j, (t, i) in enumerate(zip(sel, idx)):
        b.instance(lA[i] if j != sub else lF[i], gA if j != sub else gF, [-t])
    return b, sel
out = {}
b, sel = build(None)
out["all_A"] = solve(b)[0]
for sub in (0, 7, 19):
    b, sel = build(sub)
    ans, m = solve(b)
    forced = {j: solve(b, [[t]])[0] for j, t in enumerate(sel)}
    out[f"member_{sub}_from_fig12"] = dict(answer=ans, true_selectors=[j for j, t in enumerate(sel) if t in m],
                                           satisfiable_when_forced=[j for j, a in forced.items() if a == "SAT"])
print(json.dumps(out))
