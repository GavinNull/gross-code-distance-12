"""E-040 impossibility audit: certificate-free re-derivation.  For one claimed impossibility (code, P, sector,
pattern file), test every pattern with the independent bulk test (bulk_a) on every canonical legal schedule of
enum_a (or one representative per signature with --sig), greedily; report uncovered schedules, weights, residual
logical checks, and save for every row the index of a covering pattern (for stim spot checks).
   PYTHONPATH=.:tests uv run python -m search.experiments.e040_audit_imp.cover bb90 8 X <witnesses.jsonl> [--sig]
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

from search.experiments.e040_audit_imp.bulk_a import applies, readers, residual
from search.experiments.e040_audit_imp.codes_a import code, is_nontrivial_logical
from search.experiments.e040_audit_imp.enum_a import sig_keys

OUT = Path("results/E-040-audit-imp")


def main():
    name, P, sector, wpath = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
    sig = "--sig" in sys.argv
    C = code(name)
    z = np.load(OUT / f"canon_P{P}.npz")
    TX, TZ = z["TX"].astype(np.int64), z["TZ"].astype(np.int64)
    if sig:
        _, idx = np.unique(sig_keys(TX, TZ, P), return_index=True)
        TX, TZ = TX[idx], TZ[idx]
    tH, tR = (TX, TZ) if sector == "X" else (TZ, TX)
    pats = [json.loads(l)["faults"] for l in open(wpath)]
    pats = [[tuple(x) for x in f] for f in pats]
    rd = readers(C, sector)
    bad_res = [k for k, f in enumerate(pats) if not is_nontrivial_logical(C, sector, residual(C, sector, f))]
    cov = np.full(len(TX), -1, np.int64)
    t0 = time.time()
    usedset = set()
    CH = 400000
    for lo in range(0, len(TX), CH):
        hi = min(len(TX), lo + CH)
        for k, f in enumerate(pats):
            u = lo + np.flatnonzero(cov[lo:hi] < 0)
            if len(u) == 0:
                break
            m = applies(C, sector, f, tH[u], tR[u], P, rd)
            if m.any():
                cov[u[m]] = k
                usedset.add(k)
    used = len(usedset)
    wmax = max([len(pats[k]) for k in usedset], default=0)
    unc = int((cov < 0).sum())
    tag = f"{name}_P{P}_{sector}{'_sig' if sig else ''}"
    np.save(OUT / f"cover_{tag}.npy", cov)
    res = {"code": name, "P": P, "sector": sector, "rows": len(TX), "sig_reps": sig, "patterns": len(pats),
           "patterns_used": used, "max_weight_used": wmax, "max_weight_all": max(len(f) for f in pats),
           "uncovered": unc, "nontrivial_residual_fail": bad_res, "sec": round(time.time() - t0, 1)}
    print(json.dumps(res), flush=True)
    with open(OUT / "cover.jsonl", "a") as fo:
        fo.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
