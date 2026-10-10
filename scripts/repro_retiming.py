"""reproduce_theorems.sh --with-gross-retiming, step 2 (E-020 P=8): turn the auditor's p8search solutions into
evaluator schedules, check them, and lift one weight-11 extended-code logical per (circuit, basis) at the given R.

Run through scripts/repro_redirect.py with results/E-014-gross-dcirc11-proof redirected to the freshly built
extended codes (search/experiments/e014/gross_ext.py), so that nothing is read from earlier result directories.

    uv run python scripts/repro_redirect.py scripts/repro_retiming.py OUTDIR P8SEARCH_OUT CTL_X CTL_Z R

- P8SEARCH_OUT: output of research/audits/2026-10-09-E-020-scripts/p8search.c with X check 0 fixed to 4 (Fig. 12's
  value); every SOL line is a start vector s (prep of check c at s_c, CNOT k at s_c + k, meas at s_c + 7, mod 8).
- CTL_X / CTL_Z: dfs128 outputs (W = 11) on the extended codes inst_X / inst_Z; their FOUND lines are weight-11
  extended logicals (verified here), expanded by the 24-element translation group as spares.
- Writes OUTDIR/p8_cand<n>.json (evaluator schedule) and OUTDIR/lift_p8_cand<n>.json (lift hits, format of
  search/experiments/e020/liftrun.py) for the auditor's injection script b2_inject.py.
Lift checker: E-018 lift.build_groups / solve via e020 liftrun.run (complete and sound, audit 2026-10-08 B).
"""
import json
import sys

import numpy as np

sys.path.insert(0, "research/audits/2026-10-09-E-020-scripts")
from b1_p8_instance import checks, spec_of, code  # noqa: E402  (auditor's independent P=8 instance)
from evaluators.candidate import parse_schedule, validate_schedule  # noqa: E402
from search.experiments.e018.common import ext  # noqa: E402
from search.experiments.e020.liftrun import run  # noqa: E402

out, p8out, ctl = sys.argv[1], sys.argv[2], {"X": sys.argv[3], "Z": sys.argv[4]}
R = int(sys.argv[5])
txt = open(p8out).read()
sols = [list(map(int, l.split()[1:])) for l in txt.splitlines() if l.startswith("SOL")]
done = [l for l in txt.splitlines() if l.startswith("DONE")]
assert len(done) == 1, "p8search did not finish"
s0 = [p for _, p, _ in checks]
fail = []
canon = set()
for s in sols:
    sp = spec_of(s)
    if validate_schedule(parse_schedule(sp.to_dict()), code):
        fail.append("solution not legal for the evaluator")
    canon.add(json.dumps(parse_schedule(sp.to_dict()).canonical().to_dict(), sort_keys=True))
print(f"P=8 legal start assignments with X0 fixed: {len(sols)} ({done[0]}); distinct canonical circuits: "
      f"{len(canon)}; Fig. 12 among them: {s0 in sols}")
if len(sols) != 4 or len(canon) != 4 or s0 not in sols:
    fail.append("expected 4 distinct circuits including Fig. 12")

# weight-11 extended logicals from the W = 11 DFS controls
logicals = {}
for kind in "XZ":
    E = ext(kind)
    He, Le, perms = E["He"].astype(np.int64), E["Le"].astype(np.int64), E["perms"]
    found = [tuple(int(x) for x in l.split("cols:")[1].split()) for l in open(ctl[kind]) if l.startswith("FOUND")]
    sets = []
    for S in found:
        for P in perms:
            T = tuple(sorted(int(P[j]) for j in S))
            if T not in sets:
                sets.append(T)
    for S in sets:
        x = np.zeros(He.shape[1], np.int64)
        x[list(S)] = 1
        assert len(set(S)) == 11 and not (He @ x % 2).any() and (Le @ x % 2).any(), (kind, S)
    logicals[kind] = sets
    print(f"kind {kind}: {len(found)} DFS solution(s) -> {len(sets)} weight-11 extended logicals (translations)")
    if not sets:
        fail.append(f"no weight-11 extended logical of kind {kind}")

for n, s in enumerate(sols):
    sp = parse_schedule(spec_of(s).to_dict())
    open(f"{out}/p8_cand{n}.json", "w").write(json.dumps(sp.to_dict()))
    per = run(sp, [R], "ZX", max_hits=1, logicals=logicals)
    for rec in per:
        print(f"cand {n} (fig12={s == s0}) R={rec['R']} {rec['basis']}: lifting hit {rec['lifting'] > 0}")
        if not rec["lifting"]:
            fail.append(f"cand {n} {rec['basis']}: no weight-11 lift")
    open(f"{out}/lift_p8_cand{n}.json", "w").write(json.dumps({"cand": n, "per": per}, indent=1))
print("RETIMING_LIFT", "OK" if not fail else "FAIL " + "; ".join(fail))
