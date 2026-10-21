"""E-030: E-024a's any-R argument for PIPELINED (wrapping) schedules (search/experiments/e024a/anyr.py docstring,
audited in research/audits/2026-10-11-E-024b.md), ported to [[90,8,10]] and to a general target weight w.

Induction used here (d_ext = 8 for the class A1A2A3B2B1B3, E-028):
  weight <= 7: impossible for every R (Prop. 3 / Table I, d_ext = 8).
  weight w in {8, 9}: assume no undetected logical of weight < w at any R.  Split lemma (3): a minimum-weight
  undetected logical F with a fault-free gap b - a >= G splits into two undetected parts, one a logical of weight < w:
  contradiction.  So F's fault layers have consecutive gaps <= G - 1 and span <= (w-1)(G-1).  Block deletion (4)
  moves F to a circuit with at most R'_w rounds.  Exact checks for every R <= R'_w then give "no weight w at any R".
This script only re-uses the audited premise checks of e024a.anyr (starts R-independent, dm <= D-1, detector
structure by parsing, contiguous block-insertion cuts R = 3..12) with the bb90 code, and prints G and R'_w.

    PYTHONPATH=.:tests uv run python -m search.experiments.e030.anyr_wrap SPEC.json
"""
import json
import sys
from pathlib import Path

from evaluators.candidate import parse_schedule
from search.experiments.e024a import anyr as A
from search.experiments.e028.common import css

A.css = css          # the e024a module was written for gross; swap in [[90,8,10]]


def main():
    spec = parse_schedule(json.load(open(sys.argv[1]))).canonical()
    D = spec.period
    starts = None
    res = {"spec": sys.argv[1], "D": D}
    for R in (2, 3, 5, 9):
        U, dm, det_ok = A.structure(spec, R)
        starts = starts or dict(U.start)
        assert U.start == starts, "starts depend on R"
        res[f"det_structure_R{R}"] = det_ok
    S = max(starts.values()) - min(starts.values())
    dmax = max(dm.values())
    G = max(2 * D + dmax - 1, D + S + dmax)
    res.update(S=S, dm_max=dmax, min_start=min(starts.values()), G=G)
    lo_all, chi_all = set(), set()
    for b in "ZX":
        cu = A.cuts(spec, b, 12)
        for R, xs in cu.items():
            assert xs == list(range(xs[0], xs[-1] + 1)), "valid cuts not contiguous"
            lo_all.add(xs[0]); chi_all.add(xs[-1] - D * R)
        res[f"cuts_{b}"] = {R: (xs[0], xs[-1]) for R, xs in cu.items()}
    assert len(chi_all) == 1, chi_all
    lo, c_hi = max(lo_all), chi_all.pop()
    res.update(lo=lo, c_hi=c_hi)
    for w in (8, 9, 10):
        span = (w - 1) * (G - 1)
        flast = lo + D - 1 + span
        Rp = (flast + 2 * D - 2 - c_hi) // D
        assert D * Rp + c_hi < flast + 2 * D - 1 <= D * (Rp + 1) + c_hi
        res[f"span_w{w}"] = span
        res[f"R_prime_w{w}"] = Rp
    print(json.dumps(res, indent=1))
    Path(f"results/E-030-bb90-period-ler/anyr_wrap_{Path(sys.argv[1]).stem}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
