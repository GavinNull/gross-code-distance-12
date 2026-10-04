"""Upper-bound attacks on stim circuits: evaluator template circuits (R=2,3,4) and the auditor's own circuits (R=3),
new seeds, bigger budgets, plus stim search_for_undetectable_logical_errors.  Any witness <=9 is injection-verified
by upper_bound itself (verify_faults) and re-verified here by stim on the DEM."""
import sys, json, time
sys.path.insert(0, "research/audits/2026-10-05-E-013-scripts")
import stim
from evaluators.tasks import get_task, build_code
from evaluators.candidate import parse_schedule, build_circuits
from evaluators.noise import add_noise
from evaluators.distance import upper_bound
from aud13 import build, memory
from extcode import Z_EVEN_FIX


def main():
    which, R, basis, seed, trials, lns, workers = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), int(sys.argv[7])
    if which == "eval":
        code, _ = build_code(get_task("bb108-dcirc"), None)
        spec = parse_schedule(json.load(open("results/E-013-audit/spec_auditor.json"))).canonical()
        circ = add_noise(build_circuits(spec, code, R)[basis], "sd6", 1e-3)
    else:
        c, s = build(ze=Z_EVEN_FIX)
        circ = memory(c, s, basis, R)
    t0 = time.time()
    r = upper_bound(circ, seed=seed, methods=("graphlike", "stim_search", "bposd"), stim_search_size=4, stim_search_degree=4,
                    stim_search_timeout_s=900, bposd_trials=trials, bposd_osd_order=4, bposd_max_iter=200,
                    lns_starts=lns, lns_hops=2, lns_det_time=2.0, lns_max_chain=6, lns_max_excess=4, num_workers=workers)
    d = r.to_dict()
    out = dict(which=which, R=R, basis=basis, seed=seed, trials=trials, lns=lns, seconds=round(time.time() - t0),
               summary=r.summary(), weight=d.get("weight"), methods=d.get("methods"))
    print(json.dumps(out, default=str)[:3000])
    json.dump(d | {"meta": out}, open(f"results/E-013-audit/s4_{which}_R{R}_{basis}_s{seed}.json", "w"), default=str)


if __name__ == '__main__':
    main()
