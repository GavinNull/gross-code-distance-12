"""Check the DRAT proofs of the unsatisfiable SAT instances in certificates/ (SM S10) with drat-trim.

certificates/proofs/certificates_proofs.jsonl has one record per CNF of certificates/ (sha256 of the uncompressed CNF,
of the binary DRAT proof written by CaDiCaL and of the LRAT core written by drat-trim, sizes, verdicts and times on
the reference machine).  Proofs up to the size limit are shipped as certificates/proofs/drat/<name>.drat.xz.

    python code/proofs/check_proofs.py                    # check every shipped proof with drat-trim
    python code/proofs/check_proofs.py --max-bytes 20e6   # only shipped proofs below 20 MB (quick)
    python code/proofs/check_proofs.py --regenerate NAME… # proofs not shipped: re-solve with CaDiCaL, check the new
                                                          # proof with drat-trim (and cake_lpr), compare its sha256
    python code/proofs/check_proofs.py --regenerate unshipped   # the 14 proofs over 100 MB (about 2.9 CPU hours)
    python code/proofs/check_proofs.py --regenerate all         # every certificate (about 3.2 CPU hours)
Tools: $CADICAL, $DRAT_TRIM, $CAKE_LPR (see code/proofs/build_tools.sh).
"""
import argparse
import gzip
import hashlib
import json
import lzma
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import certify as C                  # noqa: E402
from common_cli import Verdict      # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CERT = ROOT / "certificates"
PROOFS = CERT / "proofs"

ap = argparse.ArgumentParser()
ap.add_argument("--max-bytes", type=float, default=0)
ap.add_argument("--regenerate", nargs="*", default=None)
ap.add_argument("--timeout", type=int, default=7200)
a = ap.parse_args()
V = Verdict()
recs = [json.loads(l) for l in open(PROOFS / "certificates_proofs.jsonl")]
tmp = Path(tempfile.mkdtemp(prefix="proofcheck"))
try:
    for r in recs:
        name = r["name"]
        cnf_gz = ROOT / r["cnf"]
        shipped = PROOFS / "drat" / f"{name}.drat.xz"
        if a.regenerate is not None:
            if not (a.regenerate == ["all"] or name in a.regenerate
                    or (a.regenerate == ["unshipped"] and not shipped.exists())):
                continue
            rec = C.certify(cnf_gz, tmp, name, a.timeout, keep=False)
            same = rec.get("drat_sha256") == r["drat_sha256"]
            V(rec["ok"] and rec["cnf_sha256"] == r["cnf_sha256"],
              f"{name}: re-solved {rec['solver']['answer']}, drat-trim {rec.get('drat_trim', {}).get('verdict')}, "
              f"cake_lpr {'SKIP (not run)' if rec.get('cake_lpr', {}).get('verdict') == 'not run' else rec.get('cake_lpr', {}).get('verdict')}; proof "
              f"{'identical to' if same else 'differs from'} the recorded one ({rec.get('drat_bytes')} bytes)")
            continue
        if not shipped.exists():
            print(f"skip  {name}: proof not shipped ({r['drat_bytes']} bytes, sha256 {r['drat_sha256'][:16]}…)")
            continue
        if a.max_bytes and r["drat_bytes"] > a.max_bytes:
            print(f"skip  {name}: {r['drat_bytes']} bytes > --max-bytes")
            continue
        cnf, drat = tmp / f"{name}.cnf", tmp / f"{name}.drat"
        with gzip.open(cnf_gz, "rb") as fi, open(cnf, "wb") as fo:
            shutil.copyfileobj(fi, fo)
        with lzma.open(shipped, "rb") as fi, open(drat, "wb") as fo:
            shutil.copyfileobj(fi, fo)
        ok_h = C.sha256(cnf) == r["cnf_sha256"] and C.sha256(drat) == r["drat_sha256"]
        code, text, wall, cpu = C.run([C.DRAT_TRIM, str(cnf), str(drat), "-t", str(a.timeout), "-w"], a.timeout + 60)
        ok = any(l.strip() == "s VERIFIED" for l in text.splitlines())
        V(ok_h and ok, f"{name}: sha256 {'ok' if ok_h else 'MISMATCH'}, drat-trim {'VERIFIED' if ok else 'NOT VERIFIED'} "
                       f"({r['drat_bytes']} bytes, {cpu:.1f} s)")
        cnf.unlink(); drat.unlink()
finally:
    shutil.rmtree(tmp)
V.exit()
