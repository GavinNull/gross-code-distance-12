"""Build the class-T(P) part of release/zenodo/ (version 3.0): fault patterns, the five CNF certificates of the
impossibility results (gzip), their records (sha256 of CNF and DRAT proof, verdicts).

    uv run python scripts/zenodo/build_v3_tclass.py
Sources (internal; nothing of this is written into the package):
  patterns  results/E-040-min-period/sweep_{...}_witnesses.jsonl   (the files the audited CNFs were built from)
  records   results/E-040-min-period/drat_E040.jsonl               (the five audited rows)
The CNFs are regenerated with the package encoder code/tclass/cnf.py: with the original comment line the sha256 must
equal the audited record (asserted); the package copy carries a neutral comment line (CaDiCaL ignores comments, so the
recorded DRAT proof applies unchanged); both hashes are recorded.
"""
import gzip
import hashlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, "release/zenodo/code/tclass")
import cnf as PC        # noqa: E402

REL = Path("release/zenodo")
SRC = Path("results/E-040-min-period")
JOBS = [  # code, P, sector, source pattern file, bound
    ("bb90", 8, "X", "sweep_bb90_P8_X_W9", 8),
    ("bb90", 9, "X", "sweep_bb90_P9_X_W9", 9),
    ("bb90", 10, "X", "sweep_bb90_P10_X_W9b", 9),
    ("gross", 8, "X", "sweep_gross_P8_X_W11b", 11),
    ("gross", 9, "Z", "sweep_gross_P9_Z_W11d", 11),
]
recs = {}
for l in open(SRC / "drat_E040.jsonl"):
    r = json.loads(l)
    if r.get("verified"):
        recs[r["cnf_sha256"]] = r


def gz_write(path, data: bytes):
    with open(path, "wb") as f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=f, mtime=0, compresslevel=9) as g:
            g.write(data)


def cnf_bytes(E, comment):
    s = io.StringIO()
    s.write(f"c {comment}\n")
    s.write(f"p cnf {E.nv} {len(E.cl)}\n")
    for c in E.cl:
        s.write(" ".join(map(str, c)) + " 0\n")
    return s.getvalue().encode()


out = []
for code, P, sector, src, bound in JOBS:
    name = f"{code}_P{P}_{sector}"
    pats = [json.loads(l) for l in open(SRC / f"{src}_witnesses.jsonl")]
    lines = [json.dumps({"k": i, "sector": sector, "weight": len(p["faults"]), "faults": p["faults"]},
                        separators=(",", ":")) for i, p in enumerate(pats)]
    pf = REL / "data" / "period_class" / f"{name}_patterns.jsonl.gz"
    gz_write(pf, ("\n".join(lines) + "\n").encode())
    E, npat, nleg = PC.build(code, P, [f"{pf}:{sector}"])
    orig = cnf_bytes(E, "E-0" + "40 " + PC.comment(code, P, npat, nleg))
    h0 = hashlib.sha256(orig).hexdigest()
    assert h0 in recs, (name, "regenerated CNF differs from the audited record")
    r = recs[h0]
    pkg = cnf_bytes(E, PC.comment(code, P, npat, nleg))
    h1 = hashlib.sha256(pkg).hexdigest()
    assert orig.split(b"\n", 1)[1] == pkg.split(b"\n", 1)[1]
    gz_write(REL / "certificates" / "period_class" / f"{name}.cnf.gz", pkg)
    rec = {"name": name, "code": code, "P": P, "sector": sector,
           "memory_basis": "Z" if sector == "X" else "X",
           "statement": f"every circuit of T({P}) for the {'gross code' if code == 'gross' else '[[90,8,10]] code'} "
                        f"has, for sufficiently many rounds, an undetected logical of weight <= {bound} "
                        f"in the {'Z' if sector == 'X' else 'X'}-basis memory",
           "patterns": npat, "max_pattern_weight": max(len(p["faults"]) for p in pats),
           "patterns_file": str(pf.relative_to(REL)), "cnf_file": f"certificates/period_class/{name}.cnf.gz",
           "vars": E.nv, "clauses": len(E.cl), "legality_clauses": nleg,
           "cnf_sha256": h1, "cnf_sha256_original_comment": h0,
           "solver": "CaDiCaL 3.0.1", "answer": "UNSAT", "solve_s": r["solve_sec"],
           "drat_bytes": r["proof_bytes"], "drat_sha256": r["proof_sha256"],
           "drat_trim": "s VERIFIED", "check_s": r["check_sec"]}
    out.append(rec)
    print(name, npat, E.nv, len(E.cl), "sha(original) == record", h0[:12], "package", h1[:12])
# keep the results of package re-runs (code/tclass/check_certs.py drat; logs in certificates/period_class/logs/)
old = REL / "certificates" / "period_class" / "records.jsonl"
if old.exists():
    prev = {json.loads(l)["name"]: json.loads(l) for l in open(old)}
    for r in out:
        p = prev.get(r["name"], {})
        if p.get("cnf_sha256") == r["cnf_sha256"]:
            for k in ("rerun", "cake_lpr"):
                if k in p:
                    r[k] = p[k]
with open(REL / "certificates" / "period_class" / "records.jsonl", "w") as f:
    for r in out:
        f.write(json.dumps(r) + "\n")
print("OK")
