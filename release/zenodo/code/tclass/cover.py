"""SAT-free check of an impossibility result of the class T(P) (SM S7 "SAT-free check"): test every fault pattern with
the bulk model of bulk.py on every canonical legal timing vector of enumerate.py (or one representative per signature
with --sig), greedily; report uncovered vectors and check that every pattern's residual data error is a nontrivial
logical.  Independent of the CNF encoding and of any SAT solver.

    python code/tclass/cover.py NAME [--sig] [--out DIR]
NAME = bb90_P8_X, bb90_P9_X, bb90_P10_X, gross_P8_X, gross_P9_Z (certificates/period_class/records.jsonl).
Needs DIR/canon_P{P}.npz from enumerate.py (written if missing).  CPU (reference machine): P = 8 a few seconds,
P = 9 about 7 min, P = 10 with --sig about 4 min, P = 10 over all 10,271,304 vectors about 2.6 h.
"""
import gzip
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from bulk import applies, readers, residual                       # noqa: E402
from codes import code, is_nontrivial_logical                     # noqa: E402
import enumerate as EN                                            # noqa: E402


def main(argv):
    name = argv[0]
    sig = "--sig" in argv
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else Path("tclass_run")
    rec = next(json.loads(l) for l in open(ROOT / "certificates/period_class/records.jsonl")
               if json.loads(l)["name"] == name)
    P, sector = rec["P"], rec["sector"]
    C = code(rec["code"])
    f = out / f"canon_P{P}.npz"
    if not f.exists():
        out.mkdir(parents=True, exist_ok=True)
        TX, TZ = EN.run(P)
        np.savez_compressed(f, TX=TX, TZ=TZ)
    z = np.load(f)
    TX, TZ = z["TX"].astype(np.int64), z["TZ"].astype(np.int64)
    nvec = len(TX)
    if sig:
        _, idx = np.unique(EN.sig_keys(TX, TZ, P), return_index=True)
        TX, TZ = TX[idx], TZ[idx]
    tH, tR = (TX, TZ) if sector == "X" else (TZ, TX)
    pats = [[tuple(x) for x in json.loads(l)["faults"]] for l in gzip.open(ROOT / rec["patterns_file"], "rt")]
    rd = readers(C, sector)
    bad = [k for k, fl in enumerate(pats) if not is_nontrivial_logical(C, sector, residual(C, sector, fl))]
    cov = np.full(len(TX), -1, np.int64)
    t0 = time.time()
    used = set()
    CH = 400000
    for lo in range(0, len(TX), CH):
        hi = min(len(TX), lo + CH)
        for k, fl in enumerate(pats):
            u = lo + np.flatnonzero(cov[lo:hi] < 0)
            if len(u) == 0:
                break
            m = applies(C, sector, fl, tH[u], tR[u], P, rd)
            if m.any():
                cov[u[m]] = k
                used.add(k)
    unc = int((cov < 0).sum())
    wmax = max(len(pats[k]) for k in used)
    res = {"name": name, "legal_vectors": nvec, "tested": len(TX), "signature_representatives": sig,
           "patterns": len(pats), "patterns_used": len(used), "max_weight_used": wmax, "uncovered": unc,
           "residual_not_nontrivial_logical": bad, "sec": round(time.time() - t0, 1)}
    good = unc == 0 and not bad and wmax <= rec["max_pattern_weight"]
    print("PASS" if good else "FAIL", json.dumps(res), flush=True)
    return good


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1:]) else 1)
