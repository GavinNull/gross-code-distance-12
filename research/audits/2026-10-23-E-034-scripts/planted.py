"""Auditor (E-034): planted test of the u11 blocking, with orbits chosen by the auditor (not #200 as in E-034).

    uv run python planted.py KIND W DROP_INDEX NODELIMIT LIST1 [LIST2]

1. build.py u11 KIND W --blocks LISTS --drop-block DROP_INDEX  (E-031 encoder; the orbit of block DROP_INDEX is removed)
2. the auditor's compiled pbdfs, count only, node limit NODELIMIT; it must stop with "SAT columns: ...";
3. the answer is checked with the auditor's own extended code (alib.py, no search/ import): Hc v = 0, L v != 0,
   |v| = W, v is in the lists, v is in the dropped orbit (own translation group), v contains no kept block.
Appends to results/E-034-audit/planted/planted.jsonl
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from alib import ROOT, col_vec, ext_code  # noqa: E402

kind, W, drop, lim = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
lists = sys.argv[5:]
OUT = ROOT / "results/E-034-audit/planted"
OUT.mkdir(parents=True, exist_ok=True)
stem = OUT / f"u11_{kind}_W{W}_drop{drop}"
b = subprocess.run(["uv", "run", "python", str(ROOT / "search/experiments/e031/build.py"), "u11", kind, str(W), str(stem),
                    "--blocks", *lists, "--drop-block", str(drop)], capture_output=True, text=True, cwd=ROOT)
assert b.returncode == 0, b.stderr
t0 = time.time()
p = subprocess.run([str(ROOT / "results/E-034-audit/bin/pbdfs"), str(stem) + ".inst", "-n", lim],
                   capture_output=True, text=True)
Path(str(stem) + ".log").write_text(p.stdout + p.stderr)
rec = {"kind": kind, "W": W, "drop": drop, "build": [l for l in b.stdout.splitlines() if l.startswith("dropped")],
       "rc": p.returncode, "wall_s": round(time.time() - t0, 1),
       "result": [l for l in p.stdout.splitlines() if l.startswith("RESULT")][-1:]}
sol = [l for l in p.stdout.splitlines() if l.startswith("SAT columns:")]
basis = {"X": "Z", "Z": "X"}[kind]          # E-031/E-032 naming: kind X = Z-basis memory
E = ext_code("gross", ROOT / "search/experiments/e032/u11_spec.json", basis, None)
N, Hc = E["N"], E["Hc"]
Lm = np.array([col_vec(E, r) for r in E["L"]], dtype=np.uint8)
blocks = []
for f in lists:
    blocks += [tuple(sorted(e["columns"])) for e in json.load(open(f))["logicals"]]
orbit = {tuple(sorted(int(P[j]) for j in blocks[drop])) for P in E["perms"]}
kept = [set(x) for x in blocks if x not in orbit]
rec["dropped_orbit_size_own"] = len(orbit)
if sol:
    cols = sorted(int(x) for x in sol[-1].split(":")[1].split())
    v = np.zeros(N, dtype=np.uint8); v[cols] = 1
    rec.update(solution=cols, weight=len(cols),
               own_H_zero=not (Hc.astype(int) @ v % 2).any(), own_L_nonzero=bool((Lm.astype(int) @ v % 2).any()),
               in_lists=tuple(cols) in set(blocks), in_dropped_orbit=tuple(cols) in orbit,
               contains_kept_block=any(k <= set(cols) for k in kept))
    rec["ok"] = (p.returncode == 2 and rec["own_H_zero"] and rec["own_L_nonzero"] and rec["weight"] <= W
                 and rec["in_dropped_orbit"] and not rec["contains_kept_block"])
else:
    rec["ok"] = False
print(json.dumps(rec))
with open(OUT / "planted.jsonl", "a") as f:
    f.write(json.dumps(rec) + "\n")
