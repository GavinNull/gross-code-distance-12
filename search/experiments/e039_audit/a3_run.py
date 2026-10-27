"""E-039 audit a3_run: solve the 42 Z0-cubes of my own R = 1 CNF (a3_own_r1) with CaDiCaL 3.0.1, one cube file at a
time (written, solved, deleted).  --drat: also write a DRAT proof and check it with drat-trim (proof deleted).
The cubes cover everything: legality forces tau(Z0, 0) != tau(Z0, 1), and the 42 cubes are all ordered pairs.
usage: uv run python -m search.experiments.e039_audit.a3_run results/E-039-audit/own_R1_S7.cnf --shard i/n [--drat]"""
import argparse
import hashlib
import json
import os
import subprocess
import time

ap = argparse.ArgumentParser()
ap.add_argument("cnf")
ap.add_argument("--S", type=int, default=7)
ap.add_argument("--shard", default="0/1")
ap.add_argument("--only", default="")
ap.add_argument("--drat", action="store_true")
a = ap.parse_args()
i0, n = map(int, a.shard.split("/"))
mp = json.load(open(a.cnf.replace(".cnf", "_map.json")))["x"]
base = open(a.cnf).read().split("\n", 1)
h = base[0].split()
pairs = [(x, y) for x in range(1, a.S + 1) for y in range(1, a.S + 1) if x != y]
only = {int(z) for z in a.only.split(",") if z}
for idx, (x, y) in enumerate(pairs):
    if idx % n != i0 or (only and idx not in only):
        continue
    p = f"{a.cnf[:-4]}_zcube{idx}.cnf"
    with open(p, "w") as f:
        f.write(f"p cnf {h[2]} {int(h[3]) + 2}\n")
        f.write(base[1])
        f.write(f"{mp[f'Z0_0_{x}']} 0\n{mp[f'Z0_1_{y}']} 0\n")
    sha = hashlib.sha256(open(p, "rb").read()).hexdigest()
    t0 = time.time()
    cmd = ["tools/cadical/build/cadical", "-q", p] + ([p[:-4] + ".drat"] if a.drat else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    st = [l for l in r.stdout.splitlines() if l.startswith("s ")]
    rec = {"cube": idx, "tau_Z0": [x, y], "cnf_sha256": sha, "result": st[0] if st else None,
           "sec": round(time.time() - t0, 1)}
    if a.drat and st and st[0] == "s UNSATISFIABLE":
        t1 = time.time()
        v = subprocess.run(["tools/drat-trim/drat-trim", p, p[:-4] + ".drat", "-t", "100000"], capture_output=True,
                           text=True)
        rec["verified"] = any(l.strip() == "s VERIFIED" for l in v.stdout.replace("\r", "\n").splitlines())
        rec["check_sec"] = round(time.time() - t1, 1)
    for z in (p, p[:-4] + ".drat"):
        if os.path.exists(z):
            os.remove(z)
    with open("results/E-039-audit/a3_cubes.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec), flush=True)
