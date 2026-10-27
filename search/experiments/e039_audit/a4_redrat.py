"""E-039 audit a4: re-run CaDiCaL 3.0.1 (DRAT) + drat-trim on chosen cubes of E-039's finite N7 CNFs.
Cube units are derived by me from the order encoding (event (X0, term a) owns variables 6a+1 .. 6a+6 meaning
tau <= 1 .. 6; no other variables precede them because pi / mu are constants in class N): tau = x  <->
[x <= 6 -> v(x)] and [x >= 2 -> -v(x-1)].  They must equal E-039's *_cubes.json, the cube CNF sha256 must equal the
one E-039 recorded, and the proof sha256 is compared (CaDiCaL deterministic).  Proofs are deleted after checking.
usage: uv run python -m search.experiments.e039_audit.a4_redrat PREFIX i,j,... out.jsonl"""
import hashlib
import json
import os
import subprocess
import sys
import time

prefix, idxs, out = sys.argv[1], [int(x) for x in sys.argv[2].split(",")], sys.argv[3]
S = 7
pairs = [(x, y) for x in range(1, S + 1) for y in range(1, S + 1) if x != y]
theirs = json.load(open(prefix + "_cubes.json"))
recs = {}
base_dir = os.path.dirname(prefix)
for fn in os.listdir(base_dir):
    if fn.startswith("drat_fs_") and fn.endswith(".jsonl"):
        for line in open(os.path.join(base_dir, fn)):
            r = json.loads(line)
            recs.setdefault(os.path.basename(r["cnf"]), []).append(r)


def units(x, y):
    u = []
    for a, t in ((0, x), (1, y)):
        if t <= S - 1:
            u.append(6 * a + t)
        if t >= 2:
            u.append(-(6 * a + t - 1))
    return u


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


base = open(prefix + ".cnf").read().split("\n", 1)
h = base[0].split()
scratch = "results/E-039-audit/cubes"
os.makedirs(scratch, exist_ok=True)
for i in idxs:
    x, y = pairs[i]
    u = units(x, y)
    assert theirs[i]["tau_X0_0"] == x and theirs[i]["tau_X0_1"] == y and sorted(theirs[i]["units"]) == sorted(u), i
    cnf = f"{scratch}/{os.path.basename(prefix)}_cube{i}.cnf"
    with open(cnf, "w") as f:
        f.write(f"p cnf {h[2]} {int(h[3]) + len(theirs[i]['units'])}\n")
        f.write(base[1] if base[1].endswith("\n") else base[1] + "\n")
        for l in theirs[i]["units"]:
            f.write(f"{l} 0\n")
    cs = sha(cnf)
    theirrec = [r for r in recs.get(os.path.basename(cnf), []) if r.get("verified")]
    proof = cnf[:-4] + ".drat"
    t0 = time.time()
    r = subprocess.run(["tools/cadical/build/cadical", "-q", cnf, proof], capture_output=True, text=True)
    st = [l for l in r.stdout.splitlines() if l.startswith("s ")]
    t1 = time.time()
    rec = {"cube": i, "tau_X0": [x, y], "cnf_sha256": cs, "cnf_sha_matches_E039": any(t["cnf_sha256"] == cs for t in theirrec),
           "cadical": st[0] if st else None, "solve_sec": round(t1 - t0, 1)}
    if st and st[0] == "s UNSATISFIABLE":
        v = subprocess.run(["tools/drat-trim/drat-trim", cnf, proof, "-t", "100000"], capture_output=True, text=True)
        txt = v.stdout.replace("\r", "\n")
        rec["verified"] = any(l.strip() == "s VERIFIED" for l in txt.splitlines())
        ps = sha(proof)
        rec["proof_sha256"] = ps
        rec["proof_sha_matches_E039"] = any(t.get("proof_sha256") == ps for t in theirrec)
        rec["check_sec"] = round(time.time() - t1, 1)
    for p in (proof, cnf):
        if os.path.exists(p):
            os.remove(p)
    with open(out, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec), flush=True)
