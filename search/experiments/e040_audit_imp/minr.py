"""E-040 impossibility audit, bulk vs small R: for a sample of covering patterns of one certificate, the smallest
number of rounds R of the evaluator memory circuit in which SOME placement (global instance shift) of the pattern is
an undetected logical (0 detectors, observable flipped), searched R = 1..Rmax; also confirms it stays one for R..R+3.
   PYTHONPATH=.:tests uv run python -m search.experiments.e040_audit_imp.minr bb90 8 X <witnesses> [--sig] [n]"""
import json
import random
import sys
from collections import Counter

import numpy as np
import stim

from search.experiments.e040_audit_imp.codes_a import code
from search.experiments.e040_audit_imp.enum_a import sig_keys
from search.experiments.e040_audit_imp.inject_a import build


def events(C, sector, tH, tR, P, faults):
    hk, rk = ("X", "Z") if sector == "X" else ("Z", "X")
    T = C["T"]
    ev = []
    for f in faults:
        if f[0] == "d":
            _, q, b, r = f
            c2 = [c for c in range(C["N2"]) if T[rk][c][b] == q][0]
            ev.append((True, q, rk, c2, b, tR[b] + r * P))
        elif f[0] == "h":
            _, c, S, j = f
            p = max([m for m in range(6) if m not in S], key=lambda m: tH[m])
            ev.append((False, None, hk, c, p, tH[p] + j * P))
        else:
            _, c2, r = f
            p = max(range(6), key=lambda m: tR[m])
            ev.append((False, None, rk, c2, p, tR[p] + r * P))
    return ev


def works(C, sector, tX, tZ, P, faults, R):
    basis = "Z" if sector == "X" else "X"
    tH, tR = (tX, tZ) if sector == "X" else (tZ, tX)
    ev = events(C, sector, tH, tR, P, faults)
    circ, anc_of, check_of, off, cxset, meas, nl = build(C, tX, tZ, P, basis, R)
    T = C["T"]
    tmin = min(e[5] for e in ev)
    gate = "X_ERROR" if sector == "X" else "Z_ERROR"
    for K in range(-((tmin + off) // P) - 2, (nl // P) + 2):
        sh = off + K * P
        ins = {}
        ok = True
        for isd, q, ty, c, lab, tb in ev:
            L = tb + sh
            anc = anc_of[ty][c]
            if (anc, int(T[ty][c][lab]), L) not in cxset:
                ok = False
                break
            ins.setdefault(L, []).append(q if isd else anc)
        if not ok:
            continue
        out = stim.Circuit()
        layer = 0
        for inst in circ:
            if inst.name == "TICK":
                qs = ins.get(layer, [])
                odd = sorted(x for x in set(qs) if qs.count(x) % 2)
                if odd:
                    out.append(gate, odd, 1.0)
                layer += 1
            out.append(inst)
        det, obs = out.compile_detector_sampler().sample(1, separate_observables=True)
        if not det.any() and obs.any():
            return True
    return False


def main():
    name, P, sector, wpath = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
    sig = "--sig" in sys.argv
    nums = [a for a in sys.argv[5:] if a.isdigit()]
    n = int(nums[0]) if nums else 40
    C = code(name)
    z = np.load(f"results/E-040-audit-imp/canon_P{P}.npz")
    TX, TZ = z["TX"].astype(int), z["TZ"].astype(int)
    if sig:
        _, idx = np.unique(sig_keys(TX, TZ, P), return_index=True)
        TX, TZ = TX[idx], TZ[idx]
    tag = f"{name}_P{P}_{sector}{'_sig' if sig else ''}"
    cov = np.load(f"results/E-040-audit-imp/cover_{tag}.npy")
    pats = [[tuple(x) for x in json.loads(l)["faults"]] for l in open(wpath)]
    rng = random.Random(5)
    rows = rng.sample(range(len(cov)), min(n, len(cov)))
    hist = Counter()
    stay = 0
    for r in rows:
        f = pats[int(cov[r])]
        Rm = None
        for R in range(1, 9):
            if works(C, sector, TX[r].tolist(), TZ[r].tolist(), P, f, R):
                Rm = R
                break
        hist[Rm] += 1
        if Rm is not None:
            stay += all(works(C, sector, TX[r].tolist(), TZ[r].tolist(), P, f, R2) for R2 in range(Rm + 1, Rm + 4))
    res = {"code": name, "P": P, "sector": sector, "sampled_rows": len(rows), "minR_hist": {str(k): v for k, v in sorted(hist.items(), key=lambda x: (x[0] is None, x[0]))},
           "still_logical_for_next_3_R": stay}
    print(json.dumps(res), flush=True)
    with open("results/E-040-audit-imp/minr.jsonl", "a") as fo:
        fo.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
