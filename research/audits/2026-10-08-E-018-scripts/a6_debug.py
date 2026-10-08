"""Audit E-018 (a6_debug): on an a5 schedule, for a model-blocked single-hook logical, compare own model, the
experimenter's frame_model.feasible_general, and the exact DP witness (which fault types are used)."""
import ast, json, sys, pickle, collections
sys.path.insert(0, "research/audits/2026-10-08-E-018-scripts")
from a1_common import xo, zo, xcol, zcol, code
from a3_model import single_hook_logicals, lifts
from evaluators.candidate import CheckTiming, ScheduleSpec, build_circuits, parse_schedule
from search.experiments.e018.common import ext
from search.experiments.e018.lift import build_groups, solve, augmented
from search.experiments.e018 import frame_model as fm

res = json.load(open(sys.argv[1])); P = res["P"]; R = int(sys.argv[2]) if len(sys.argv) > 2 else 4
sc = {ast.literal_eval(k): v for k, v in res["sched"].items()}
key = (lambda chk: (chk[0], xcol[chk[1]] if chk[0] == "X" else zcol[chk[1]])) if res["mode"] == "sym" else (lambda chk: chk)
sched = {chk: (sc[key(chk)][0], tuple(sc[key(chk)][1])) for chk in [("X", i) for i in range(72)] + [("Z", j) for j in range(72)]}
def mk(chk):
    s, o = sched[chk]; ords = xo[chk[1]] if chk[0] == "X" else zo[chk[1]]
    return CheckTiming(s % P, (s + o[5] + 1) % P, tuple(sorted((int(q), (s + o[k]) % P) for k, q in enumerate(ords))))
spec = parse_schedule(ScheduleSpec(P, tuple(mk(("X", i)) for i in range(72)), tuple(mk(("Z", j)) for j in range(72))).to_dict())
E = ext("X")
idx_of = {}
for S in pickle.load(open("results/E-018-gross-interleaved-12/w11_all_X.pkl", "rb")):
    fr = tuple(sorted(next(s for s in E["col_sups"][j] if len(s) == 1)[0] for j in S if any(len(s) == 1 for s in E["col_sups"][j])))
    hk = [E["col_sups"][j][0] for j in S if not any(len(s) == 1 for s in E["col_sups"][j])]
    if len(fr) == 10 and len(hk) == 1:
        idx_of[(fr, tuple(sorted(hk[0])))] = S
reads, htime, PP = fm.abs_tables(spec, "Z")
groups, stats, circ, aug = build_groups(spec.canonical(), R, "Z")
LOG = single_hook_logicals("X")
cnt = collections.Counter()
shown = 0
for L in LOG:
    S = idx_of[(tuple(sorted(L[0])), tuple(sorted(L[2])))]
    mine = lifts(sched, P, L, "Z")
    theirs = fm.feasible_general(S, "X", reads, htime, PP)
    ch, _ = solve(S, groups)
    cnt[(mine, theirs, ch is not None)] += 1
    if not mine and ch is not None and shown < 1:
        shown += 1
        print("blocked-in-model but exact-lifts:", L)
        # explain the chosen DEM terms
        dem = aug.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
        for j, mask in ch.items():
            dets = [i for i in range(mask.bit_length()) if mask >> i & 1]
            filt = stim_dem = None
            import stim
            t = stim.DetectorErrorModel()
            t.append("error", 0.1, [stim.target_relative_detector_id(d) for d in dets] or [stim.target_logical_observable_id(0)])
            ex = circ.explain_detector_error_model_errors(dem_filter=t, reduce_to_one_representative_error=False) if dets else []
            locs = set()
            for e in ex:
                for loc in e.circuit_error_locations[:6]:
                    locs.add(str([(str(p.gate_target) if hasattr(p,'gate_target') else str(p)) for p in loc.flipped_pauli_product]) + f" tick={loc.tick_offset} instr={loc.instruction_targets.gate}")
            print(" col", j, E["col_sups"][j][:3], "dets", dets, "locs", sorted(locs)[:6])
print({str(k): v for k, v in cnt.items()})
