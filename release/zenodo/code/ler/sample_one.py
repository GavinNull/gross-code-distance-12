"""Re-sample one logical-error-rate ratio of SM S7 with the package's circuits, noise model and decoders, and compare
it with the recorded value (data/ler/<set>/summary.json).

Default (about 4 CPU minutes): [[90,8,10]], standard SD6 (lambda = 1), p = 4e-3, BP-OSD, R = 10, c11 / IBM's
depth-8 circuit (recorded: 7.65 [5.98, 9.75] per round), with 80 shots per basis for c11 and 400 for IBM.  PASS if
the new 95% interval overlaps the recorded one and lies on the same side of 1.  Sampling is random (sinter), so the
numbers differ from run to run; larger --shots-num / --shots-den give tighter intervals.

    python code/ler/sample_one.py [--set sd6_lambda_bb90] [--noise lam1] [--p 0.004] [--dec bposd] [--num c11]
                                  [--den ibm] [--shots-num 80] [--shots-den 400] [--workers 2]
Needs the optional dependencies of requirements-ler.txt (sinter, stimbposd / ldpc, relay-bp).
"""
import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_cli import Verdict                      # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="sd6_lambda_bb90", choices=["sd6_lambda_bb90", "sd6_lambda_gross"])
    ap.add_argument("--noise", default="lam1")
    ap.add_argument("--p", type=float, default=0.004)
    ap.add_argument("--dec", default="bposd")
    ap.add_argument("--num", default="c11")
    ap.add_argument("--den", default="ibm")
    ap.add_argument("--shots-num", type=int, default=80)
    ap.add_argument("--shots-den", type=int, default=400)
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    import sinter
    from ler import circuits as LC, noise as LN
    from ler.decoders import sinter_decoders
    fam, R = ("bb90", 10) if a.set == "sd6_lambda_bb90" else ("gross", 12)
    root = Path(__file__).resolve().parents[2]
    rows = json.load(open(root / "data" / "ler" / a.set / "summary.json"))["rows"]
    rec = [r for r in rows if (r["noise"], r["circ"], r["p"], r["dec"]) == (a.noise, a.num, a.p, a.dec)][0]
    recr = rec[f"ratio_vs_{a.den}"]
    tasks = []
    for c, n in ((a.num, a.shots_num), (a.den, a.shots_den)):
        for b in "ZX":
            circ = LN.noisy_from(LC.noiseless(fam, c, b, R), a.noise, a.p)
            tasks.append(sinter.Task(circuit=circ, decoder=a.dec, json_metadata=dict(circ=c, basis=b),
                                     collection_options=sinter.CollectionOptions(max_shots=n, max_errors=10 ** 9)))
    stats = sinter.collect(num_workers=a.workers, tasks=tasks, custom_decoders=sinter_decoders(), print_progress=False)
    cnt = {}
    for s in stats:
        k = (s.json_metadata["circ"], s.json_metadata["basis"])
        n0, k0 = cnt.get(k, (0, 0))
        cnt[k] = (n0 + s.shots, k0 + s.errors)
    rng = np.random.default_rng(1)
    draws, pt = {}, {}
    for c in (a.num, a.den):
        d = 0.0
        e = 0.0
        for b in "ZX":
            n, k = cnt[(c, b)]
            d = d + (1 - (1 - rng.beta(k + 0.5, n - k + 0.5, 40000)) ** (1 / R))
            e += 1 - (1 - k / n) ** (1 / R)
        draws[c], pt[c] = d, e
    q = draws[a.num] / draws[a.den]
    lo, hi = np.quantile(q, [0.025, 0.975])
    ratio = pt[a.num] / pt[a.den] if pt[a.den] > 0 else float("inf")
    overlap = lo <= recr[2] and hi >= recr[1]
    side = (recr[1] > 1 and lo > 1) or (recr[2] < 1 and hi < 1) or (recr[1] <= 1 <= recr[2])
    V = Verdict()
    V(overlap and side, f"{a.set} {a.noise} p={a.p:g} {a.dec}: {a.num}/{a.den} per round re-sampled {ratio:.3g} "
                        f"[{lo:.3g}, {hi:.3g}] (failures {a.num} Z {cnt[(a.num, 'Z')][1]}/{cnt[(a.num, 'Z')][0]}, "
                        f"X {cnt[(a.num, 'X')][1]}/{cnt[(a.num, 'X')][0]}; {a.den} Z {cnt[(a.den, 'Z')][1]}/"
                        f"{cnt[(a.den, 'Z')][0]}, X {cnt[(a.den, 'X')][1]}/{cnt[(a.den, 'X')][0]}); recorded "
                        f"{recr[0]:.3g} [{recr[1]:.3g}, {recr[2]:.3g}]: intervals overlap and lie on the same side of 1")
    V.exit()


if __name__ == "__main__":
    main()
