"""Audit E-020 b2: independent injection of lift hits on the evaluator's own circuits for the 4 P=8 candidates.

Only the hits' 11 detector masks are taken from the experimenter's lift JSON.  Circuit = evaluator pipeline
(circuits_for -> canonical spec) + add_noise(sd6, 1e-3), flattened.  For each mask I look up the plain (un-augmented)
DEM terms with exactly that detector set, choose one per mask so that the observable XOR is non-zero (exhaustive
over the product), locate one circuit fault per term with stim explain, and verify with the evaluator's
distance.verify_faults (noise stripped, faults inserted with probability 1).  Also requires 11 pairwise distinct
DEM columns (the evaluator's weight unit).
"""
import itertools, json, sys
import stim
from evaluators.tasks import build_code, get_task
from evaluators.noise import add_noise
from evaluators.pipeline import circuits_for
from evaluators import distance

code, _ = build_code(get_task("gross-dcirc"), None)
RES = "results/E-020-gross-perchk-pipeline"
out = []
Rs = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [1, 3, 6]
nh = int(sys.argv[2]) if len(sys.argv) > 2 else 2
for n in range(4):
    spec = json.load(open(f"{RES}/p8_cand{n}.json"))
    lift = json.load(open(f"{RES}/lift_p8_cand{n}.json"))
    for rec in lift["per"]:
        if rec["R"] not in Rs:
            continue
        R, basis = rec["R"], rec["basis"]
        noisy = add_noise(circuits_for(spec, code, R)[basis], "sd6", 1e-3).flattened()
        dem = noisy.detector_error_model(decompose_errors=False, allow_gauge_detectors=False)
        bym = {}
        for inst in dem.flattened():
            if inst.type != "error":
                continue
            m, o = 0, 0
            for t in inst.targets_copy():
                if t.is_relative_detector_id():
                    m ^= 1 << t.val
                elif t.is_logical_observable_id():
                    o ^= 1 << t.val
            bym.setdefault(m, set()).add(o)
        for h in rec["hits"][:nh]:
            masks = [int(v) for v in h["masks"].values()]
            x = 0
            for m in masks:
                x ^= m
            opts = [sorted(bym.get(m, ())) for m in masks]
            choice = None
            if x == 0 and all(opts):
                for combo in itertools.product(*opts):
                    oo = 0
                    for c in combo:
                        oo ^= c
                    if oo:
                        choice = combo; break
            ok, msg = False, "no choice"
            if choice is not None:
                txt = []
                for m, o in zip(masks, choice):
                    txt.append("error(0.1) " + " ".join([f"D{i}" for i in range(m.bit_length()) if m >> i & 1] +
                                                        [f"L{i}" for i in range(o.bit_length()) if o >> i & 1]))
                ex = noisy.explain_detector_error_model_errors(dem_filter=stim.DetectorErrorModel("\n".join(txt)),
                                                               reduce_to_one_representative_error=True)
                faults = [distance._fault_from_location(e.circuit_error_locations[0]) for e in ex]
                distinct = len({(m, o) for m, o in zip(masks, choice)})
                ok, msg, fl = distance.verify_faults(noisy, faults)
                ok = ok and len(faults) == 11 and distinct == 11
                msg += f" nfaults={len(faults)} distinct_cols={distinct}"
            print(n, R, basis, ok, msg, flush=True)
            out.append({"cand": n, "R": R, "basis": basis, "ok": bool(ok), "msg": msg})
json.dump(out, open(f"results/E-020-audit/b2_inject_{'_'.join(map(str, Rs))}.json", "w"), indent=1)
print("confirmed", sum(o["ok"] for o in out), "/", len(out))
