"""Instance-level comparison: the package's lift CNF (code/proofs/lift_cnf.py, single instance) vs the auditor's
(indep_lift.py), same logical, solved with CaDiCaL.  For SAT instances both models are decoded to detector patterns
per group and each lift is checked on the *auditor's* DEM; with --enum N the full set of lifts (projected on the
chosen detector pattern per group) is enumerated in both encodings and compared.

    python run_compare.py CIRCUIT BASIS R [--idx i,j,...] [--sample K --seed S] [--len2 K] [--enum N]
"""
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import indep_lift as IL                                           # noqa: E402
sys.path.insert(0, str(IL.PKG / "code" / "proofs"))
import lift_cnf as LC                                             # noqa: E402


def their_instance(S, groups, block=()):
    b = LC.Builder()
    b.instance(S, groups, [])
    # variable layout (read from lift_cnf.Builder.instance/exactly_one): per group the mechanism variables in
    # order, then (group size > 6) size-1 ladder variables; XOR auxiliaries afterwards.
    var, v = [], 0
    for key in S:
        vs = []
        for dets in groups[key]:
            v += 1
            vs.append((v, frozenset(dets)))
        if len(groups[key]) > 6:
            v += len(groups[key]) - 1
        var.append(vs)
    for sol in block:
        b.clauses.append([-x for vs, dp in zip(var, sol) for x, p in vs if p == dp])
    text = f"p cnf {b.n} {len(b.clauses)}\n" + "".join(" ".join(map(str, c)) + " 0\n" for c in b.clauses)
    return text, var


def their_decode(var, model):
    sol = []
    for vs in var:
        ch = [p for x, p in vs if x in model]
        if len(ch) != 1:
            return None
        sol.append(ch[0])
    return tuple(sol)


def enum_theirs(S, groups, cap):
    sols = []
    while len(sols) < cap:
        text, var = their_instance(S, groups, sols)
        ans, model = IL.solve(text)
        if ans != "SAT":
            return sols, ans
        sols.append(their_decode(var, model))
    return sols, "CAP"


def main(a):
    circ, basis, R = a[0], a[1], int(a[2])
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d          # noqa: E731
    lists = json.load(open(IL.PKG / "data/logicals" / f"weight11_logicals_{basis}_memory.json"))["logicals"]
    idx = [int(x) for x in opt("--idx", "").split(",") if x]
    rng = random.Random(int(opt("--seed", "20261015")))
    idx += rng.sample(range(4224), int(opt("--sample", "0")))
    l2 = [i for i, e in enumerate(lists) if e["ten_data_plus_one_length2_residual"]]
    idx += rng.sample(l2, int(opt("--len2", "0")))
    if "--all" in a:
        idx = list(range(4224))
    enum = int(opt("--enum", "0"))
    t0 = time.time()
    eff = IL.faults_and_effects(circ, R, basis)
    cols, mine, st = IL.my_groups(eff, basis)
    _, theirs, _ = LC.setup(circ, basis, R)
    nobs = eff["O"].shape[0]
    agree = 0
    recs = []
    for i in idx:
        S = [cols[j] for j in lists[i]["columns"]]
        text, tvar = their_instance(S, theirs)
        ta, tm = IL.solve(text)
        cnf, mvar = IL.my_instance(S, mine, eff["ndet"], nobs)
        ma, mm = IL.solve(cnf.dimacs())
        rec = dict(i=i, len2=lists[i]["ten_data_plus_one_length2_residual"], theirs=ta, mine=ma)
        if ta == "SAT":
            rec["their_model_valid_on_my_dem"] = IL.check_lift(their_decode(tvar, tm), S, mine)
        if ma == "SAT":
            rec["my_model_valid"] = IL.check_lift(IL.decode(mvar, mm), S, mine)
        if enum and (ta == "SAT" or ma == "SAT"):
            ts, tend = enum_theirs(S, theirs, enum)
            ms, mend = IL.enumerate_mine(S, mine, eff["ndet"], nobs, enum)
            rec.update(n_lifts_theirs=len(ts), n_lifts_mine=len(ms), enum_end=[tend, mend],
                       same_lift_sets=set(ts) == set(ms),
                       all_valid=all(IL.check_lift(s, S, mine) for s in ts))
        agree += ta == ma
        recs.append(rec)
    out = dict(circuit=circ, basis=basis, R=R, n=len(idx), agree=agree, answers={k: sum(r["mine"] == k for r in recs)
               for k in ("SAT", "UNSAT")}, secs=round(time.time() - t0, 1), records=recs)
    print(json.dumps(out))


if __name__ == "__main__":
    main(sys.argv[1:])
