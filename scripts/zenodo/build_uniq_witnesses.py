"""Export the weight <= 10 extended-logical witnesses behind the 48 order-class-uniqueness CNFs (SM S10) to
release/zenodo/certificates/order_class_uniqueness/witnesses.json.gz, by running the verified replay script
(research/audits/2026-10-11-E-024b-scripts/u1_dext.py, unchanged except for its output path and one line that
records each verified witness).
    PYTHONPATH=.:tests uv run python scripts/zenodo/build_uniq_witnesses.py
"""
import gzip
import json
import os
import runpy
import sys
from pathlib import Path

S = Path(os.environ.get("ZSCRATCH", "/tmp/zenodo_uniq"))
S.mkdir(parents=True, exist_ok=True)
src = open("research/audits/2026-10-11-E-024b-scripts/u1_dext.py").read()
src = src.replace('"results/E-024b-audit/u1_dext.json"', repr(str(S / "u1_dext.json")))
old = '            st["witness_ok"] += 1; st["max_w"] = max(st["max_w"], len(sups))\n'
assert old in src
src = src.replace(old, old + '            WIT.setdefault(f"{name_}_{kind}", []).append({"assignment": [name(TY[t]) for t in '
                              'r["assign"]], "columns": [sorted(int(q) for q in s_) for s_ in sups]})\n')
old2 = '                for p in perms: S.add_clause([-x[p[c]][asg[c]] for c in range(m)])\n'
assert old2 in src
src = src.replace(old2, old2 + '                BLK.setdefault(f"{name_}_{kind}", []).append([name(TY[t]) for t in r["assign"]])\n')
src = "WIT = {}\nBLK = {}\nfrom search.experiments.e024b.common import name\n" + src
(S / "u1_wit.py").write_text(src)
sys.path.insert(0, "tests")
G = runpy.run_path(str(S / "u1_wit.py"), run_name="__main__")
cols = {nm: colv for nm, colv, _ in G["colourings"]()}
out = []
for key in G["info"]["replay"]:
    colouring, kind = key.rsplit("_", 1)
    out.append({"instance": f"{colouring.replace(';', '__').replace(',', '_')}_{kind}errors", "colouring": colouring,
                "colour_of_check": cols[colouring], "residual_type": kind,
                "blocked_fig12_translates": G["BLK"].get(key, []), "witnesses": G["WIT"].get(key, [])})
d = {"description": "Weight <= 10 extended logicals used by the order-class-uniqueness CNFs. For each instance "
                    "(colouring by cosets of a translation subgroup, residuals of X-type (Xerrors: H = HZ, L = LZ) or "
                    "Z-type checks (Zerrors: H = HX, L = LX)): 'assignment' = CNOT order (term labels) used by the "
                    "checks of colour 0, 1, ...; 'columns' = the <= 10 column supports (data qubits; a single qubit or "
                    "a residual set of some check of that assignment) whose H parts sum to zero and whose L parts do "
                    "not. 'blocked_fig12_translates' = assignments whose extended code is a translate of Fig. 12's "
                    "(the only survivors). Checked by code/check_uniqueness_witnesses.py.", "instances": out}
with gzip.open("release/zenodo/certificates/order_class_uniqueness/witnesses.json.gz", "wt") as f:
    json.dump(d, f, separators=(",", ":"))
print(len(out), "instances,", sum(len(o["witnesses"]) for o in out), "witnesses,",
      sum(len(o["blocked_fig12_translates"]) for o in out), "blocked")
