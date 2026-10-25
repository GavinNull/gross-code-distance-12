"""E-036: independent cross-check of exact d_circ with ccsearch (E-029, syndrome-driven branch and bound, separate
implementation from common.min_weight).  For each (circuit, basis, R): ccsearch decide d-1 must say NONE when we
claim d_circ >= d, and decide w must say FOUND at the claimed value w."""
import json, subprocess, sys, tempfile
from pathlib import Path
from search.experiments.e036.common import OUT, ROOT, sd6
from search.experiments.e036.dcirc import get_spec

CC = ROOT / "results" / "E-030-bb90-period-ler" / "ccsearch"
variant, name, Rs, wlo, whi = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3].split(",")], int(sys.argv[4]), int(sys.argv[5])
spec = get_spec(variant, name)
tmp = Path(tempfile.mkdtemp(dir=OUT))
res = []
for R in Rs:
    for b in ("Z", "X"):
        f = tmp / f"c_{b}_{R}.stim"
        f.write_text(str(sd6(spec, variant, b, R)))
        inst = tmp / f"c_{b}_{R}.inst"
        subprocess.run(["uv", "run", "python", str(ROOT / "search/experiments/e029/export.py"), "stim", str(f), str(inst)], check=True, capture_output=True)
        out = {}
        for W in (wlo, whi):
            r = subprocess.run([str(CC), str(inst), "decide", str(W)], capture_output=True, text=True)
            last = [l for l in r.stdout.splitlines() if l.startswith("DONE")][-1]
            out[W] = last.split()[1]
        rec = {"variant": variant, "circuit": name, "R": R, "basis": b, f"decide{wlo}": out[wlo], f"decide{whi}": out[whi]}
        print(json.dumps(rec), flush=True)
        res.append(rec)
with open(OUT / "cc_cross.jsonl", "a") as fh:
    for r in res: fh.write(json.dumps(r) + "\n")
