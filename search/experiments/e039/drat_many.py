"""E-039: for each CNF: CaDiCaL 3.0.1 (tools/cadical) with a DRAT proof (binary), then drat-trim (tools/drat-trim);
records result, 's VERIFIED', sha256 of CNF and proof, times; deletes the proof afterwards (re-creatable: CaDiCaL is
deterministic for a fixed CNF and options).  usage: uv run python -m search.experiments.e039.drat_many out.jsonl a.cnf b.cnf ..."""
import hashlib
import json
import os
import subprocess
import sys
import time


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


out = sys.argv[1]
for cnf in sys.argv[2:]:
    proof = cnf[:-4] + ".drat"
    t0 = time.time()
    r = subprocess.run(["tools/cadical/build/cadical", "-q", cnf, proof], capture_output=True, text=True)
    st = [l for l in r.stdout.splitlines() if l.startswith("s ")]
    t1 = time.time()
    rec = {"cnf": cnf, "cnf_sha256": sha(cnf), "cadical": st[0] if st else None, "solve_sec": round(t1 - t0, 1)}
    if st and st[0] == "s UNSATISFIABLE":
        v = subprocess.run(["tools/drat-trim/drat-trim", cnf, proof, "-t", "100000"], capture_output=True, text=True)
        txt = v.stdout.replace("\r", "\n")
        rec["verified"] = any(l.strip() == "s VERIFIED" for l in txt.splitlines())
        rec["proof_sha256"] = sha(proof)
        rec["proof_bytes"] = os.path.getsize(proof)
        rec["check_sec"] = round(time.time() - t1, 1)
    if os.path.exists(proof):
        os.remove(proof)
    with open(out, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec), flush=True)
