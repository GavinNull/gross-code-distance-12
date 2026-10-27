"""E-039 audit a7: re-check E-039's synchronized-subclass certificates.
For each listed subclass CNF (read-only, in results/E-039-bb18-pipe): (1) its body is the base CNF body plus exactly
the unit clauses pi_eq[k][v] for the claimed spec (X=0: every X check at layer 0; Z=d: every Z check at layer d),
taken from the base's _map.json (whose literals a6 reproduces with E-039's encoder, sha-checked); (2) its sha256 equals
E-039's DRAT record; (3) CaDiCaL 3.0.1 + DRAT + drat-trim re-run here (proof written to my results dir, deleted).
usage: uv run python -m search.experiments.e039_audit.a7_subdrat BASE.cnf:SUBFILE.cnf:SPEC ..."""
import hashlib
import json
import os
import subprocess
import sys
import time

D = "results/E-039-bb18-pipe"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


recs = {}
for fn in os.listdir(D):
    if fn.startswith("drat_") and fn.endswith(".jsonl"):
        for line in open(os.path.join(D, fn)):
            r = json.loads(line)
            recs.setdefault(os.path.basename(r["cnf"]), []).append(r)
for item in sys.argv[1:]:
    basef, subf, spec = item.split(":")
    base = open(f"{D}/{basef}").read().split("\n", 1)
    sub = open(f"{D}/{subf}").read().split("\n", 1)
    mp = json.load(open(f"{D}/{basef.replace('.cnf', '_map.json')}"))["pi_eq"]
    lhs, v = spec.split("=")
    want = []
    for name, d in mp.items():
        if name[0] == lhs:
            lit = d[str(int(v))]
            assert lit is not False
            if lit is not True:
                want.append(lit)
    body_ok = sub[1] == base[1] + "".join(f"{u} 0\n" for u in want)
    hb, hs = base[0].split(), sub[0].split()
    head_ok = hb[2] == hs[2] and int(hs[3]) == int(hb[3]) + len(want)
    cs = sha(f"{D}/{subf}")
    their = [r for r in recs.get(subf, []) if r.get("verified")]
    proof = f"results/E-039-audit/{subf[:-4]}.drat"
    t0 = time.time()
    r = subprocess.run(["tools/cadical/build/cadical", "-q", f"{D}/{subf}", proof], capture_output=True, text=True)
    st = [l for l in r.stdout.splitlines() if l.startswith("s ")]
    rec = {"file": subf, "spec": spec, "n_units": len(want), "body_is_base_plus_units": body_ok, "header_ok": head_ok,
           "cnf_sha_matches_E039": any(t["cnf_sha256"] == cs for t in their), "cadical": st[0] if st else None,
           "solve_sec": round(time.time() - t0, 1)}
    if st and st[0] == "s UNSATISFIABLE":
        t1 = time.time()
        vv = subprocess.run(["tools/drat-trim/drat-trim", f"{D}/{subf}", proof, "-t", "100000"], capture_output=True,
                            text=True)
        rec["verified"] = any(l.strip() == "s VERIFIED" for l in vv.stdout.replace("\r", "\n").splitlines())
        ps = sha(proof)
        rec["proof_sha_matches_E039"] = any(t.get("proof_sha256") == ps for t in their)
        rec["check_sec"] = round(time.time() - t1, 1)
    if os.path.exists(proof):
        os.remove(proof)
    with open("results/E-039-audit/a7_subdrat.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec), flush=True)
