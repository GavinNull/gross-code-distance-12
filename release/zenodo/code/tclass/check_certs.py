"""Checks of the five impossibility certificates of the class T(P) (SM S7, S9; records in
certificates/period_class/records.jsonl).

    python code/tclass/check_certs.py cnf [NAME ...]          # regenerate each CNF from its pattern file with cnf.py:
                                                              # sha256 = record = shipped certificates/period_class/NAME.cnf.gz
    python code/tclass/check_certs.py drat OUT [NAME ...]     # CaDiCaL + drat-trim (+ cake_lpr) on the shipped CNF
                                                              # (code/proofs/certify.py); DRAT proof sha256 compared with the record
NAME: bb90_P8_X, bb90_P9_X, bb90_P10_X, gross_P8_X, gross_P9_Z (default: all).  Tools: $CADICAL, $DRAT_TRIM, $CAKE_LPR.
The DRAT proofs (25-470 MB) are not shipped; CaDiCaL is deterministic, so a regenerated proof has the recorded hash
(same CaDiCaL version, code/proofs/build_tools.sh).  A proof whose hash differs is still a valid certificate if
drat-trim verifies it; the script then prints the verdict and "hash differs".
"""
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "proofs"))
REC = ROOT / "certificates" / "period_class" / "records.jsonl"


def records(names):
    rs = [json.loads(l) for l in open(REC)]
    return [r for r in rs if not names or r["name"] in names]


def main(argv):
    mode = argv[0]
    ok = True
    if mode == "cnf":
        import io
        import cnf as PC
        for r in records(argv[1:]):
            E, npat, nleg = PC.build(r["code"], r["P"], [str(ROOT / r["patterns_file"]) + ":" + r["sector"]])
            s = io.StringIO()
            s.write(f"c {PC.comment(r['code'], r['P'], npat, nleg)}\n")
            s.write(f"p cnf {E.nv} {len(E.cl)}\n")
            for c in E.cl:
                s.write(" ".join(map(str, c)) + " 0\n")
            h = hashlib.sha256(s.getvalue().encode()).hexdigest()
            hs = hashlib.sha256(gzip.open(ROOT / r["cnf_file"]).read()).hexdigest()
            good = h == r["cnf_sha256"] == hs and npat == r["patterns"]
            ok &= good
            print("PASS" if good else "FAIL", r["name"], f"patterns {npat}, vars {E.nv}, clauses {len(E.cl)}",
                  "regenerated sha256 = record = shipped" if good else f"sha {h} record {r['cnf_sha256']} shipped {hs}")
    elif mode == "drat":
        import certify as CE
        out = Path(argv[1]); out.mkdir(parents=True, exist_ok=True)
        for r in records(argv[2:]):
            x = CE.certify(ROOT / r["cnf_file"], out, r["name"], timeout=20000)
            same = x.get("drat_sha256") == r["drat_sha256"]
            good = x["solver"]["answer"] == "UNSAT" and x.get("drat_trim", {}).get("verdict") == "VERIFIED"
            ok &= good
            print("PASS" if good else "FAIL", r["name"], x["solver"]["answer"], "drat-trim",
                  x.get("drat_trim", {}).get("verdict"), "cake_lpr", x.get("cake_lpr", {}).get("verdict"),
                  "DRAT sha256 = record" if same else "hash differs from the record")
    else:
        sys.exit(__doc__)
    return ok


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1:]) else 1)
