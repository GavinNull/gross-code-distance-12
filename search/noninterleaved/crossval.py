"""Cross-validation of d_ext against the evaluator's circuit-level distance (public entry points only).

For a schedule: (1) baselines.circuit.pipelined_memory_circuit (noiseless) for both bases;
(2) evaluators.l0.check_l0(..., basis="both") legality; (3) evaluators.noise.add_noise(sd6, 1e-3) +
evaluators.distance.upper_bound per basis.
Mapping: Z-basis memory (Z observables) fails on X-type faults <-> d^X_ext (X-check hooks, H_Z);
X-basis memory <-> d^Z_ext.  Theorem 1 (Prop. 3): upper_bound >= d_ext always; Corollary 1: equality for
non-interleaved circuits (so the heuristic upper bound should reach d_ext if it is good enough).

  PYTHONPATH=. uv run python -m search.noninterleaved.crossval --code "[[90,8,10]]" --spec spec.json --rounds 3
  spec.json: {"PX":0,"sX":[...],"PZ":k,"sZ":[...]}   or  --fig12 for the gross Strikis circuit
"""
from __future__ import annotations

import argparse
import json
import resource
import time

from baselines.circuit import pipelined_memory_circuit
from evaluators.distance import upper_bound
from evaluators.l0 import L0Constraints, check_l0
from evaluators.noise import add_noise
from search.noninterleaved.run import OUT, dump, get_code, tag
from search.noninterleaved.schedules import interleaving, uniform_schedule

BUDGETS = {
    "low": dict(methods=("graphlike", "bposd"), bposd_trials=200, lns_starts=8),
    "default": dict(methods=("graphlike", "stim_search", "bposd"), bposd_trials=1500, lns_starts=96),
    "high": dict(methods=("graphlike", "stim_search", "bposd"), bposd_trials=6000, lns_starts=256),
}


def cpu_now():
    a = resource.getrusage(resource.RUSAGE_SELF)
    b = resource.getrusage(resource.RUSAGE_CHILDREN)
    return a.ru_utime + a.ru_stime + b.ru_utime + b.ru_stime


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="[[90,8,10]]")
    ap.add_argument("--spec", default=None)
    ap.add_argument("--fig12", action="store_true")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--budget", default="default", choices=sorted(BUDGETS))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--label", default="")
    ap.add_argument("--skip-l0", action="store_true")
    a = ap.parse_args()
    if a.fig12:
        from baselines.bb_code import gross_code
        from baselines.strikis import strikis_fig12
        from evaluators.codes import CSSCode
        g = gross_code()
        css = CSSCode.from_checks(g.HX, g.HZ)
        sched, _ = strikis_fig12(g)
        name, spec = "[[144,12,12]]", "fig12"
    else:
        code, css = get_code(a.code)
        spec = json.loads(open(a.spec).read()) if a.spec.endswith(".json") else json.loads(a.spec)
        sched = uniform_schedule(code, spec["PX"], spec["sX"], spec["PZ"], spec["sZ"])
        name = a.code
    sched.validate(css.HX, css.HZ)
    rec = {"code": name, "spec": spec, "rounds": a.rounds, "budget": a.budget, "params": BUDGETS[a.budget],
           "seed": a.seed, "interleaving": interleaving(sched), "depth": sched.depth}
    circ = {b: pipelined_memory_circuit(sched, css.HX, css.HZ, css.LZ if b == "Z" else css.LX, a.rounds, b, 0.0)
            for b in "ZX"}
    if not a.skip_l0:
        cons = L0Constraints(data_qubits=sched.data, max_qubits=sched.num_qubits, rounds=a.rounds)
        t0 = time.time()
        rep = check_l0(circ, css, "both", cons)
        rec["l0"] = {"passed": rep.passed, "seconds": round(time.time() - t0, 1), "text": rep.to_text()}
        print("L0 passed:", rep.passed, flush=True)
    rec["upper_bound"] = {}
    for b in "ZX":
        c = add_noise(circ[b], "sd6", 1e-3)
        c0 = cpu_now()
        r = upper_bound(c, seed=a.seed, num_workers=a.workers, **BUDGETS[a.budget])
        rec["upper_bound"][b] = {"weight": r.weight, "seconds": r.seconds, "cpu_s": round(cpu_now() - c0, 1),
                                 "methods": [{"method": m.method, "status": m.status, "weight": m.weight}
                                             for m in r.methods],
                                 "stopped_early": r.stopped_early,
                                 "witness": r.witness.describe() if r.witness else None}
        print(b, "upper bound", r.weight, r.seconds, flush=True)
    lab = a.label or ("fig12" if a.fig12 else f"{spec['PZ']}_{''.join(map(str, spec['sX']))}_{''.join(map(str, spec['sZ']))}")
    dump(OUT / f"crossval_{tag(name)}_{lab}_r{a.rounds}_{a.budget}.json", rec)


if __name__ == "__main__":
    main()
