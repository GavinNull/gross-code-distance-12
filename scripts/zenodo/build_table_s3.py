"""Certificates for Table S3 (retimings of Fig. 12 that keep its CNOT orders; bulk frame model), generated with the
package's own encoders (release/zenodo/code/sat) with --pin-fig12; written to
release/zenodo/certificates/fig12_retimings/.

    uv run python scripts/zenodo/build_table_s3.py <job>
jobs:  primary:P:nowrap[:sub]     second:P:sub
"""
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "release/zenodo/code")
from pysat.solvers import Cadical153, Glucose4, Minisat22   # noqa: E402

from sat import enc_primary, enc_second                     # noqa: E402

OUT = Path("release/zenodo/certificates/fig12_retimings")
OUT.mkdir(parents=True, exist_ok=True)
job = sys.argv[1].split(":")
t0 = time.process_time()
if job[0] == "primary":
    P, nowrap = int(job[1]), int(job[2])
    sub = job[3] if len(job) > 3 else None
    st, M, info = enc_primary.run(P, nowrap=nowrap, sub=sub, pin=True, max_sec=4 * 3600)
    fam = ("no symmetry" if sub == "0,0" else "24-translation symmetric") + (", common frame" if nowrap else ", pipelined")
    name = f"primary_P{P:02d}_{'common_frame' if nowrap else 'pipelined'}" + ("_nosym" if sub == "0,0" else "")
    enc = "primary encoding"
else:
    P, sub = int(job[1]), job[2]
    st, M, info = enc_second.run(P, sub=sub, pin=True, max_sec=4 * 3600)
    H = info["subgroup_order"]
    fam = "24-translation symmetric, pipelined" if H == 24 else f"invariant under <{sub}> (order {H}), pipelined"
    name = f"second_P{P:02d}_" + ("sym24" if H == 24 else "subgroup_" + sub.replace(",", "_").replace(";", "__"))
    enc = "second encoding"
gen_cpu = round(time.process_time() - t0, 1)
cl = M.S.clauses
nf = M.S.nfamily
what = f"Fig. 12 CNOT orders pinned; {fam}; period {P}; {enc}; CEGAR status {st}"
nv = max(abs(x) for c in cl for x in c)
body = (f"c {name}: {what}\nc clauses 1..{nf}: family encoding; clauses {nf + 1}..{len(cl)}: CEGAR nogoods\n"
        f"p cnf {nv} {len(cl)}\n" + "\n".join(" ".join(map(str, c)) + " 0" for c in cl) + "\n")
log = {"what": what, "name": name, "P": P, "cegar": info, "cpu_sec_generation": gen_cpu, "variables": nv,
       "clauses": len(cl), "family_clauses": nf, "sha256_uncompressed_cnf": hashlib.sha256(body.encode()).hexdigest(),
       "regenerate": f"python code/sat/regenerate.py {'primary' if job[0] == 'primary' else 'second'} {P}"
                     + (" --common-frame" if job[0] == "primary" and nowrap else "")
                     + (f" --sub '{sub}'" if sub else "") + " --pin-fig12"}
if st != "UNSAT":
    json.dump(log, open(OUT / f"{name}.FAILED.json", "w"), indent=1)
    print("NOT UNSAT", log)
    sys.exit(1)
with gzip.open(OUT / f"{name}.cnf.gz", "wt") as f:
    f.write(body)
res = {}
for (nm, Sv), bud in zip((("cadical153", Cadical153), ("glucose4", Glucose4), ("minisat22", Minisat22)),
                         (None, 300_000, 200_000)):
    t1 = time.process_time()
    with Sv(bootstrap_with=cl) as s:
        if bud is None:
            r = s.solve()
        else:
            s.conf_budget(bud); r = s.solve_limited()
    res[nm] = {"result": {True: "SAT", False: "UNSAT", None: f"UNKNOWN (conflict budget {bud})"}[r],
               "cpu_sec": round(time.process_time() - t1, 2), "conflict_budget": bud}
log["resolve"] = res
with Glucose4(bootstrap_with=cl[:nf]) as s3:
    log["family_only"] = "SAT" if s3.solve() else "UNSAT"
json.dump(log, open(OUT / f"{name}.log.json", "w"), indent=1)
print(json.dumps({k: v for k, v in log.items()}))
