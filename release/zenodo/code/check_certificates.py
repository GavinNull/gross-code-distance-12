"""Re-solve the clause sets in certificates/ (SM S9, S16) and compare with the recorded results.

Each certificate is a DIMACS CNF (gzip) with a log (*.log.json: what it encodes, sha256 of the uncompressed CNF,
clause counts, results of three solvers at generation time).  This script checks the hash and solves every CNF from
scratch with CaDiCaL 1.5.3 (PySAT); expected: UNSAT for every file.  With --family it also checks that the family
encoding alone (the first 'family_clauses' clauses) is satisfiable, i.e. the family is not empty.

    python code/check_certificates.py                      # all certificates (about 15 CPU minutes)
    python code/check_certificates.py --max-clauses 100000 # skip the largest ones (quick)
    python code/check_certificates.py certificates/min_period_primary_encoding
"""
import argparse
import gzip
import hashlib
import json
import time
from pathlib import Path

from pysat.solvers import Cadical153, Glucose4

from common_cli import Verdict
from gross12.paths import CERTIFICATES

ap = argparse.ArgumentParser()
ap.add_argument("dirs", nargs="*")
ap.add_argument("--max-clauses", type=int, default=0)
ap.add_argument("--family", action="store_true")
a = ap.parse_args()
V = Verdict()
# certificates/bb90_dext_free/ ([[90,8,10]], SM S4) has no re-solve log; it is checked with its DRAT proof record
# (code/proofs/check_proofs.py --records certificates/proofs/bb90_dext_free.jsonl --regenerate all)
dirs = [Path(d) for d in a.dirs] or sorted(p for p in CERTIFICATES.iterdir() if p.is_dir() and p.name != "bb90_dext_free")
for d in dirs:
    for cnf in sorted(d.glob("*.cnf.gz")):
        log = json.load(open(str(cnf).replace(".cnf.gz", ".log.json")))
        if a.max_clauses and log["clauses"] > a.max_clauses:
            print(f"skip  {d.name}/{cnf.name} ({log['clauses']} clauses)")
            continue
        raw = gzip.open(cnf).read()
        ok_hash = hashlib.sha256(raw).hexdigest() == log["sha256_uncompressed_cnf"]
        clauses, nv, nc = [], None, None
        for line in raw.decode().splitlines():
            if line.startswith("c") or not line.strip():
                continue
            if line.startswith("p cnf"):
                _, _, nv, nc = line.split(); nv, nc = int(nv), int(nc)
                continue
            lits = [int(x) for x in line.split()]
            assert lits[-1] == 0
            clauses.append(lits[:-1])
        t0 = time.process_time()
        with Cadical153(bootstrap_with=clauses) as s:
            r = s.solve()
        sec = time.process_time() - t0
        msg = ""
        okf = True
        if a.family and log.get("family_clauses"):
            with Glucose4(bootstrap_with=clauses[:log["family_clauses"]]) as s2:
                okf = s2.solve()
            msg = f"; family alone {'SAT' if okf else 'UNSAT'}"
        V(ok_hash and nc == len(clauses) and r is False and okf,
          f"{d.name}/{cnf.name}: {len(clauses)} clauses, {nv} variables, sha256 {'ok' if ok_hash else 'MISMATCH'}, "
          f"CaDiCaL {'UNSAT' if r is False else 'SAT'} in {sec:.1f} s (recorded: "
          f"{', '.join(k + ' ' + v['result'] for k, v in log['resolve'].items())}){msg}")
V.exit()
