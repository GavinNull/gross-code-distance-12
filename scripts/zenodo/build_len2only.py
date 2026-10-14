"""Write release/zenodo/certificates/fig12_retimings_len2only/: the final clause sets of the 25 Table S3 CEGAR runs with
the frame model restricted to the "ten data + one length-2 residual" logicals (release/zenodo/code/sat/len2only.py),
with a log.json per instance; the CEGAR iteration counts are compared with the independent run of
research/audits/2026-10-14-revg-scripts/g4_len2only*.json.

    uv run python scripts/zenodo/build_len2only.py [NAME ...]
"""
import gzip
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, "release/zenodo/code")
from sat import len2only as L2                    # noqa: E402
from sat.recorder import dimacs_body, write_cnf  # noqa: E402

OUT = Path("release/zenodo/certificates/fig12_retimings_len2only")
OUT.mkdir(parents=True, exist_ok=True)
ref = {}
for f in Path("research/audits/2026-10-14-revg-scripts").glob("g4_len2only*.json"):
    for k, v in json.load(open(f)).items():
        if k.endswith("|len2only"):
            n = k.split("|")[0]
            n = n.replace(",", "_").replace(";", "__")
            ref[n] = v
names = sys.argv[1:] or list(L2.ROWS)
for name in names:
    enc, kw, st, M, info = L2.run(name)
    cl = M.S.clauses
    path = OUT / f"{name}.cnf.gz"
    write_cnf(path, cl, L2.header(name, enc, kw, st, M))
    body = dimacs_body(cl)
    r = ref.get(name)
    log = {"what": L2.header(name, enc, kw, st, M)[0], "name": name, "encoding": enc, "params": kw,
           "cegar": info, "variables": max(abs(x) for c in cl for x in c), "clauses": len(cl),
           "family_clauses": M.S.nfamily, "sha256_uncompressed_cnf": None,
           "regenerate": f"python code/sat/len2only.py {name}",
           "independent_run": None if r is None else {"status": r["status"], "iterations": r["info"]["iterations"],
                                                        "kept": r["kept"]}}
    raw = gzip.open(path, "rb").read()
    log["sha256_uncompressed_cnf"] = hashlib.sha256(raw).hexdigest()
    json.dump(log, open(OUT / f"{name}.log.json", "w"), indent=1)
    agree = r is not None and r["status"] == st and r["info"]["iterations"] == info["iterations"] and r["kept"] == info["records_kept"]
    print(("OK  " if st == "UNSAT" and agree else "CHECK"), name, st, len(cl), "clauses,", info["iterations"], "it,",
          info["records_kept"], "kept; independent run:", None if r is None else (r["status"], r["info"]["iterations"]),
          flush=True)
