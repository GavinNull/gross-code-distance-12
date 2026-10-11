"""E-024b: premises of the any-R argument for a WRAPPING (pipelined) candidate.

Argument (mine; generalises the audited non-wrapping version, research/audits/2026-10-10-E-021.md item 6):
 Slab k = [min over checks of the start of round k, max over checks of the measurement of round k].
 (S') Split lemma: let F be an undetected logical with no fault inside slab k+1, F_< = faults before slab k+1,
      F_> = faults after it.  F_< alone: data frame constant after slab k+1 starts, every round >= k+1 window
      starts inside or after slab k+1 and contains no fault, so it measures H e; detectors comparing rounds
      >= k+1 and the final-readout detectors vanish.  F_> alone: every measurement of rounds <= k+1 happens before
      F_> starts, so detectors comparing rounds <= k+1 (and first-round detectors) vanish.  Every detector compares
      (j, j+1) with j >= k+1 or j+1 <= k+1, so D(F_<) = D(F_>) = 0 everywhere; their observables sum to F's, so one
      is a logical with < |F| faults.  For |F| = 11 this contradicts d_circ >= 11 (Table I + d_ext = 11, any R).
      => the slabs touched by F form a contiguous range in which every slab contains a fault.
 (O)  Only adjacent slabs overlap (checked) => a fault lies in <= 2 slabs => an 11-fault F touches <= 22 slabs.
 (T)  Time periodicity (e021.anyR.periodicity, generic): the (R+1)-round noisy circuit is the R-round one with one
      fixed block inserted, detectors/observables shift accordingly.  Then F can be moved to a circuit with
      <= 22 + 2 = 24 rounds (one fault-free round kept on each interior side; the fault-free round before F is
      unaffected by F except through faults inside its own slab, identically in both circuits).
 (L)  exact lift R = 1..24 both bases, 0 lifting  =>  d_circ >= 12 for every R.

    PYTHONPATH=.:tests uv run python -m search.experiments.e024b.anyR_wrap spec.json
"""
import json
import sys

from evaluators.candidate import parse_schedule, unroll
from search.experiments.e018.common import css
from search.experiments.e021.anyR import periodicity


def slabs(spec, R):
    U = unroll(spec, css(), R)
    D = spec.period
    st, en = {}, {}
    rnd_of = {}
    for q, s in U.start.items():
        for j in range(R):
            st[j] = min(st.get(j, 10 ** 9), s + D * j)
    for t, lst in U.meas.items():
        for q, typ, j in lst:
            en[j] = max(en.get(j, -1), t)
            rnd_of[(q, j)] = t
    # every op of round j inside slab j
    ok_in = True
    for t, lst in U.cnots.items():
        for c, tg in lst:
            anc = c if c in U.start else tg
            j = (t - U.start[anc]) // D
            ok_in &= st[j] <= t <= en[j]
    for t, lst in U.preps.items():
        for q, typ in lst:
            j = (t - U.start[q]) // D
            ok_in &= st[j] <= t <= en[j]
    sl = [(st[j], en[j]) for j in range(R)]
    only_adjacent = all(sl[j][1] < sl[j + 2][0] for j in range(R - 2))
    overlap = max(sl[j][1] - sl[j + 1][0] + 1 for j in range(R - 1))
    return ok_in, only_adjacent, overlap, sl


def main():
    spec = parse_schedule(json.load(open(sys.argv[1]))).canonical()
    res = {}
    for R in (3, 6, 10):
        ok_in, adj, ov, sl = slabs(spec, R)
        print("slabs R", R, "ops-in-slab", ok_in, "only-adjacent-overlap", adj, "max overlap", ov, sl[:3], flush=True)
        res[f"slab_R{R}"] = bool(ok_in and adj)
        res["overlap"] = ov
    for b in "ZX":
        r = periodicity(spec, b, 14)
        print("periodicity", b, r, flush=True)
        res[f"per_{b}"] = r[0]
    res["R_needed"] = 24 if res["overlap"] > 0 else 13
    print(json.dumps(res))


if __name__ == "__main__":
    main()
