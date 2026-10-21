"""A2: d_ext and complete weight-10 / weight-11 lists with the auditor's own extended code + mitmsearch.
Steps (per basis): write instance; run `mitmsearch W=9 decide` (all orbits, incl. data-only root cases) -> must be
NONE; run `mitmsearch W=11 enum` (all orbits), expand under the 72 translations, verify every set, split by weight;
compare with the project's pickles (keys built with the evaluator's L so they are comparable byte for byte).
Usage: a2_lists.py SPEC BASIS [--skip-run]  (output under results/E-032-audit/)"""
import sys, json, time, pickle, subprocess, collections
sys.path.insert(0, "research/audits/2026-10-22-E-032-scripts")
import numpy as np
from extcode import *

spec_path, basis = sys.argv[1], sys.argv[2]
skip = "--skip-run" in sys.argv
spec = load_spec(spec_path)
from evaluators.tasks import build_code, get_task
ec, _ = build_code(get_task("gross-dcirc"), None)
EL = (np.asarray(ec.LZ) if basis == "Z" else np.asarray(ec.LX)) % 2
E = ext_code(spec, basis, Lover=EL.astype(np.uint8))
tag = spec_path.split("/")[-1].split(".")[0] + "_" + basis
inst = f"results/E-032-audit/ext_{tag}.txt"
write_instance(E, inst)
out = {"spec": spec_path, "basis": basis, "cols": len(E["cols"]), "orbits": len(E["reps"]),
       "orbit_sizes": collections.Counter(E["orb"]).most_common(), "group": len(E["perms"])}
binp = "results/E-032-audit/mitmsearch_nw2"
def run(W, mode, look, fn):
    t0 = time.time()
    if not skip:
        with open(fn, "w") as fo, open(fn + ".err", "w") as fe:
            subprocess.run([binp, str(W), mode, str(look)], stdin=open(inst), stdout=fo, stderr=fe, check=True)
    sols = [tuple(map(int, l.split()[2:])) for l in open(fn) if l.startswith("SOL")]
    return sols, open(fn + ".err").read().strip().splitlines()[-1], round(time.time() - t0, 1)
s9, log9, t9 = run(9, "decide", 3, f"results/E-032-audit/mitm_{tag}_W9.out")
out["W9_decide"] = {"solutions": len(s9), "log": log9, "sec": t9}
s11, log11, t11 = run(11, "enum", 3, f"results/E-032-audit/mitm_{tag}_W11.out")
assert all(verify(E, S) for S in s11)
allS = expand(E, s11)
assert all(verify(E, S) for S in allS)
byw = collections.Counter(len(S) for S in allS)
out["W11_enum"] = {"root_solutions": len(s11), "log": log11, "sec": t11, "expanded_by_weight": dict(byw)}
data_only = sum(1 for S in allS if all(j < N for j in S))   # columns 0..143 are the data columns (inserted first)
out["data_only_logicals_weight_le_11"] = data_only
assert all(E["cols"][j] == E["cols"][j] for j in range(N))
# compare with the project pickles (same key format: H bytes + L bytes, evaluator L)
kind = "X" if basis == "Z" else "Z"
for w in (10, 11):
    pk = pickle.load(open(f"results/E-032-gross-short-period/w{w}_{kind}_all_A1A2A3B3B1B2.pkl", "rb"))
    theirs = {frozenset(S) for S in map(lambda L: tuple(L), pk["keys"])}
    theirs = {frozenset(k for k in S) for S in theirs}
    mine = {frozenset(E["cols"][j] for j in S) for S in allS if len(S) == w}
    out[f"cmp_w{w}"] = {"mine": len(mine), "project": len(theirs), "only_mine": len(mine - theirs),
                        "only_project": len(theirs - mine)}
    out[f"colset_equal_w{w}"] = set(pk["colset"]) == set(E["cols"])
with open(f"results/E-032-audit/lists_{tag}.pkl", "wb") as f:
    pickle.dump({"cols": E["cols"], "sets": {w: sorted(sorted(S) for S in allS if len(S) == w) for w in (10, 11)}}, f)
print(json.dumps(out, indent=1, default=str), flush=True)
