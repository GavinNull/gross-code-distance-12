"""E-040 impossibility audit: stim injection of every pattern that covers at least one schedule in cover.py's
greedy cover (on its first covered row + up to --extra random other covered rows), with model-vs-stim detector-set
comparison, plus negative controls (one fault moved by one instance; one fault removed) on every 5th pattern.
   PYTHONPATH=.:tests uv run python -m search.experiments.e040_audit_imp.inject_cert bb90 8 X <witnesses> [--sig] [--extra 2]
"""
import json
import random
import sys

import numpy as np

from search.experiments.e040_audit_imp.codes_a import code
from search.experiments.e040_audit_imp.enum_a import sig_keys
from search.experiments.e040_audit_imp.inject_a import check


def main():
    name, P, sector, wpath = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
    sig = "--sig" in sys.argv
    extra = int(sys.argv[sys.argv.index("--extra") + 1]) if "--extra" in sys.argv else 2
    rng = random.Random(20261030)
    C = code(name)
    z = np.load(f"results/E-040-audit-imp/canon_P{P}.npz")
    TX, TZ = z["TX"].astype(int), z["TZ"].astype(int)
    if sig:
        _, idx = np.unique(sig_keys(TX, TZ, P), return_index=True)
        TX, TZ = TX[idx], TZ[idx]
    tag = f"{name}_P{P}_{sector}{'_sig' if sig else ''}"
    cov = np.load(f"results/E-040-audit-imp/cover_{tag}.npy")
    pats = [[tuple(x) for x in json.loads(l)["faults"]] for l in open(wpath)]
    by = {}
    for r, k in enumerate(cov):
        by.setdefault(int(k), []).append(r)
    n = bad = mism = neg = negbad = 0
    for k in sorted(by):
        rows = by[k]
        pick = [rows[0]] + rng.sample(rows[1:], min(extra, len(rows) - 1))
        for r in pick:
            nf, ob, same = check(C, sector, TX[r].tolist(), TZ[r].tolist(), P, pats[k])
            n += 1
            if nf or not ob:
                bad += 1
                print("BAD", k, r, nf, ob, flush=True)
            if not same:
                mism += 1
        if k % 5 == 0:
            f = list(pats[k])
            i = rng.randrange(len(f))
            g = f[:i] + f[i + 1:]
            x = f[i]
            mv = (x[0], x[1], x[2], x[3] + 1) if x[0] in "dh" else (x[0], x[1], x[2] + 1)
            for h in (g, f[:i] + [mv] + f[i + 1:]):
                nf, ob, same = check(C, sector, TX[rows[0]].tolist(), TZ[rows[0]].tolist(), P, h)
                neg += 1
                negbad += (nf == 0 and ob)
                mism += not same
    res = {"code": name, "P": P, "sector": sector, "sig": sig, "patterns_injected": len(by), "injections": n,
           "failed": bad, "model_stim_detector_mismatch": mism, "neg_controls": neg, "neg_controls_still_logical": negbad}
    print(json.dumps(res), flush=True)
    with open("results/E-040-audit-imp/inject_cert.jsonl", "a") as fo:
        fo.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
