"""Exact full-E extended-code distance d_ext(E) of a (non-interleaved) schedule, with translation-symmetry case split.
usage: t4_fullE.py WHICH TYPE CAP [WORKERS] [TIME_PER_CASE]
WHICH: gross_fig12 | json:<path to schedule json>:<code>
For each column orbit O_i (in order): min |x| s.t. ext-logical, x[rep_i]=1, x[O_j]=0 for j<i, |x|<=CAP.
All cases infeasible => d_ext > CAP.  Otherwise d_ext = min over cases (if all cases optimal/infeasible)."""
import sys, json, time
sys.path.insert(0, "research/audits/2026-10-03-E-005-scripts")
from multiprocessing import Pool
from audext import *

def load(which):
    if which == "gross_fig12":
        from baselines.bb_code import BBCode
        from baselines.strikis import strikis_fig12
        g = BBCode(12, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"])
        s, _ = strikis_fig12(g)
        return Code("gross"), s
    _, path, code = which.split(":")
    from baselines.schedule import Schedule
    return Code(code), Schedule.from_json(open(path).read())

def setup(which, et):
    code, sched = load(which)
    sched.validate(code.HX, code.HZ)
    orders = orders_from_schedule(sched)[et]     # X-type errors come from X checks
    res = [S for o in orders for S in nontrivial_suffixes(o)]
    H, L = code.det(et)
    M, rH = ext_matrix(H, L, res)
    orbits, syms = column_orbits(code, res)
    return code, res, M, rH, orbits, syms

def case(args):
    which, et, cap, i, tl = args
    code, res, M, rH, orbits, syms = setup(which, et)
    fz = [j for o in orbits[:i] for j in o]
    r = highs_fixed(M, rH, cap, tl, force_one=orbits[i][0], force_zero=fz)
    x = r.pop("x", None)
    if x is not None:
        r["support"] = [int(j) for j in np.nonzero(x)[0]]
    r["case"] = i
    return r

if __name__ == "__main__":
    which, et, cap = sys.argv[1], sys.argv[2], int(sys.argv[3])
    W = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    tl = float(sys.argv[5]) if len(sys.argv) > 5 else 3600
    code, res, M, rH, orbits, syms = setup(which, et)
    print("ext matrix", M.shape, "residuals", len(res), "symmetries", len(syms), "orbits", [len(o) for o in orbits], flush=True)
    t0 = time.time()
    out = []
    with Pool(W) as p:
        for r in p.imap_unordered(case, [(which, et, cap, i, tl) for i in range(len(orbits))]):
            out.append(r); print(json.dumps({k: v for k, v in r.items() if k != "support"}), flush=True)
    out.sort(key=lambda r: r["case"])
    vals = [r["value"] for r in out if r["value"] is not None]
    allproved = all(r["status"] in ("optimal", "infeasible") for r in out)
    summary = {"which": which, "type": et, "cap": cap, "ext_shape": list(M.shape), "n_symmetries": len(syms),
               "orbit_sizes": [len(o) for o in orbits], "min_found": min(vals) if vals else None,
               "all_cases_proved": allproved,
               "conclusion": (f"d_ext = {min(vals)}" if vals and allproved else
                              f"d_ext > {cap}" if allproved else "undecided"),
               "cpu_s": sum(r["seconds"] for r in out), "wall_s": round(time.time() - t0, 1), "cases": out}
    tag = which.replace(":", "_").replace("/", "_")
    json.dump(summary, open(f"results/E-005-audit/fullE_{tag[-60:]}_{et}_cap{cap}.json", "w"), indent=1)
    print("SUMMARY", summary["conclusion"], "cpu", summary["cpu_s"])
