"""Evaluator cross-check (public entry points only): schedule -> evaluator spec (qec-schedule/v1) ->
evaluators.pipeline.circuits_for (evaluator's own template) -> evaluators.noise.add_noise(sd6) ->
evaluators.distance.upper_bound with a REDUCED budget (CPU cap of this audit).
usage: t10_crossval.py WHICH TASK ROUNDS TRIALS LNS WORKERS MAXSEC [BASES]"""
import sys, json, time, resource
sys.path.insert(0, "research/audits/2026-10-03-E-005-scripts")
from t4_fullE import load
from evaluators.tasks import get_task, build_code
from evaluators.pipeline import circuits_for
from evaluators.noise import add_noise
from evaluators.distance import upper_bound

def to_spec(sched):
    D = sched.depth
    col = {q: j for j, q in enumerate(sched.data)}
    def chk(q, is_x):
        tp = next(t for t, L in enumerate(sched.layers) if q in (L.prep_x if is_x else L.prep_z))
        tm = next(t for t, L in enumerate(sched.layers) if q in (L.meas_x if is_x else L.meas_z))
        cn = [[col[b if is_x else a], t] for t, L in enumerate(sched.layers) for a, b in L.cnots if q in (a, b)]
        return {"prep": tp, "meas": tm, "cnots": sorted(cn)}
    return {"format": "qec-schedule/v1", "period": D,
            "x_checks": [chk(q, True) for q in sched.x_checks], "z_checks": [chk(q, False) for q in sched.z_checks]}

def cpu():
    a = resource.getrusage(resource.RUSAGE_SELF); b = resource.getrusage(resource.RUSAGE_CHILDREN)
    return a.ru_utime + a.ru_stime + b.ru_utime + b.ru_stime

if __name__ == "__main__":
    which, task_id, R, trials, lns, W, maxsec = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), float(sys.argv[7])
    bases = sys.argv[8] if len(sys.argv) > 8 else "ZX"
    _, sched = load(which)
    task = get_task(task_id)
    code, _ = build_code(task, None)
    spec = to_spec(sched)
    circ = circuits_for(spec, code, R)
    out = {"which": which, "task": task_id, "rounds": R, "trials": trials, "lns_starts": lns, "max_seconds": maxsec, "bases": {}}
    for b in bases:
        c = add_noise(circ[b], task.noise_model, task.p)
        c0 = cpu(); t0 = time.time()
        r = upper_bound(c, seed=0, methods=("graphlike", "bposd"), bposd_trials=trials, lns_starts=lns,
                        num_workers=W, max_seconds=maxsec)
        out["bases"][b] = {"weight": r.weight, "wall_s": round(time.time() - t0, 1), "cpu_s": round(cpu() - c0, 1),
                           "stopped_early": r.stopped_early,
                           "methods": [{"method": m.method, "status": m.status, "weight": m.weight} for m in r.methods],
                           "witness_verified": (r.witness.verified if r.witness else None)}
        print(b, json.dumps(out["bases"][b]), flush=True)
    tag = which.replace(":", "_").replace("/", "_")[-40:]
    json.dump(out, open(f"results/E-005-audit/crossval_{tag}_{task_id}_r{R}.json", "w"), indent=1)
