"""E-038: per-cube DRAT certificates.  For cube i: CNF_i = final CNF + the cube's unit clauses; CaDiCaL 3.0.1 must say
UNSATISFIABLE and drat-trim must print 's VERIFIED' for its proof.  The cubes are all S!/(S-6)! injective layer
assignments of the first check (exhaustive: legality forces one of them).  Records sha256 of each CNF_i and proof_i,
then deletes the proof file (re-creatable).  usage: uv run python -m search.experiments.e038.cube_drat PREFIX --shard 0/2"""
import argparse
import hashlib
import json
import os
import subprocess
import time

ap = argparse.ArgumentParser()
ap.add_argument("prefix")
ap.add_argument("--shard", default="0/1")
a = ap.parse_args()
sh, n = map(int, a.shard.split("/"))
base = open(a.prefix + ".cnf").read().split("\n", 1)
hdr = base[0].split()
nv, nc = int(hdr[2]), int(hdr[3])
body = base[1]
cubes = json.load(open(a.prefix + "_cubes.json"))
tmp = f"{a.prefix}_tmp{sh}"
out = open(f"{a.prefix}_cube_drat_{sh}of{n}.jsonl", "a")
for i, cb in enumerate(cubes):
    if i % n != sh:
        continue
    t0 = time.time()
    with open(tmp + ".cnf", "w") as f:
        f.write(f"p cnf {nv} {nc + len(cb)}\n")
        f.write(body)
        for l in cb:
            f.write(f"{l} 0\n")
    r = subprocess.run(["tools/cadical/build/cadical", "-q", tmp + ".cnf", tmp + ".drat"], capture_output=True, text=True)
    st = [l for l in r.stdout.splitlines() if l.startswith("s ")]
    v = subprocess.run(["tools/drat-trim/drat-trim", tmp + ".cnf", tmp + ".drat", "-t", "20000"], capture_output=True, text=True)
    ver = "s VERIFIED" in v.stdout
    h = hashlib.sha256(open(tmp + ".drat", "rb").read()).hexdigest()
    rec = {"cube": i, "lits": cb, "cadical": st[0] if st else None, "verified": ver, "proof_sha256": h,
           "sec": round(time.time() - t0, 1)}
    out.write(json.dumps(rec) + "\n")
    out.flush()
    os.remove(tmp + ".drat")
os.remove(tmp + ".cnf")
print("done", sh)
