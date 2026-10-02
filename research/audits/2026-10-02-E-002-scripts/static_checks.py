"""E-002 audit: static checks (no decoding).

1. Schedule vs paper Table 5, built from scratch (own matrices, own Table-5 transcription), compared
   with the published artifact results/E-002-gross-baseline/schedule_ibm_depth8.json AND with
   baselines.schedule.ibm_depth8 output.
2. evaluators.l0.check_l0(basis="both") on the noiseless E-002 circuits (rounds 12 and 3).
3. Noise accounting on the noisy 12-round E-002 circuit vs the IBM spec (noise-models.md §3).
4. Witness circuit_distance_witness_X_r3.json: inject the 10 faults as deterministic Paulis into the
   noiseless circuit, check no detector fires and observables flip; also a "bulk" shifted copy.

Run: PYTHONPATH=. uv run python research/audits/2026-10-02-E-002-scripts/static_checks.py
"""
import collections
import json
import re
import sys
import time

import numpy as np
import stim

RES = "results/E-002-gross-baseline"
out = {}

# ------------------------------------------------------------------ 1. schedule vs Table 5
l, m = 12, 6
S = lambda k: np.roll(np.eye(k, dtype=int), 1, axis=1)  # row i has 1 at column i+1
x = np.kron(S(l), np.eye(m, dtype=int))
y = np.kron(np.eye(l, dtype=int), S(m))
mp = lambda M, k: np.linalg.matrix_power(M, k) % 2
T = {"A1": mp(x, 3), "A2": y, "A3": mp(y, 2), "B1": mp(y, 3), "B2": x, "B3": mp(x, 2)}
n2 = l * m
Xq = lambda i: i
Lq = lambda j: n2 + j
Rq = lambda j: 2 * n2 + j
Zq = lambda i: 3 * n2 + i
fw = lambda M, i: int(np.flatnonzero(M[i, :])[0])      # j = M(i)
tr = lambda M, i: int(np.flatnonzero(M[:, i])[0])      # j = M^T(i)
# Table 5 transcription (paper rounds 1..8), from research/literature/gross-code-baseline.md §3.1
table5 = {
    1: [("Z", "R", "A1", "T")],
    2: [("X", "L", "A2", "F"), ("Z", "R", "A3", "T")],
    3: [("X", "R", "B2", "F"), ("Z", "L", "B1", "T")],
    4: [("X", "R", "B1", "F"), ("Z", "L", "B2", "T")],
    5: [("X", "R", "B3", "F"), ("Z", "L", "B3", "T")],
    6: [("X", "L", "A1", "F"), ("Z", "R", "A2", "T")],
    7: [("X", "L", "A3", "F")],
    8: [],
}
expected = {}
for r, items in table5.items():
    pairs = set()
    for typ, blk, term, mode in items:
        for i in range(n2):
            j = fw(T[term], i) if mode == "F" else tr(T[term], i)
            dq = Lq(j) if blk == "L" else Rq(j)
            pairs.add((Xq(i), dq) if typ == "X" else (dq, Zq(i)))
    expected[r] = pairs

HX = np.hstack([T["A1"] + T["A2"] + T["A3"], T["B1"] + T["B2"] + T["B3"]]) % 2
HZ = np.hstack([(T["B1"] + T["B2"] + T["B3"]).T, (T["A1"] + T["A2"] + T["A3"]).T]) % 2

art = json.load(open(f"{RES}/schedule_ibm_depth8.json"))
from baselines.bb_code import gross_code
from baselines.schedule import ibm_depth8
code = gross_code()
sched = ibm_depth8(code)
sch = {"artifact_json": [set(map(tuple, L["cnots"])) for L in art["layers"]],
       "regenerated": [set(L.cnots) for L in sched.layers]}
res1 = {"HX_equal": bool((HX == code.HX).all()), "HZ_equal": bool((HZ == code.HZ).all())}
for name, layers in sch.items():
    res1[name] = {f"round{r}": (layers[r - 1] == expected[r], len(layers[r - 1])) for r in range(1, 9)}
alay = art["layers"]
res1["prep_meas"] = {
    "round1_prepX_all": sorted(alay[0]["prep_x"]) == list(range(n2)),
    "round7_measZ_all": sorted(alay[6]["meas_z"]) == [Zq(i) for i in range(n2)],
    "round8_measX_all": sorted(alay[7]["meas_x"]) == list(range(n2)),
    "round8_prepZ_all": sorted(alay[7]["prep_z"]) == [Zq(i) for i in range(n2)],
    "no_other_prep_meas": all(not (L["prep_x"] or L["prep_z"] or L["meas_x"] or L["meas_z"])
                              for t, L in enumerate(alay) if t not in (0, 6, 7)),
}
# commutation check per-pair (independent of stim): for each X check a and Z check b sharing data,
# the order condition. We rely on stim determinism + L0 for this.
out["schedule_vs_table5"] = res1
print(json.dumps(res1, indent=1))

# ------------------------------------------------------------------ 2. L0
from baselines.gross import circuits
from evaluators.codes import CSSCode
from evaluators.l0 import L0Constraints, check_l0

cc = CSSCode.from_checks(code.HX, code.HZ)
res2 = {}
for rounds in (3, 12):
    t0 = time.time()
    circs = {b: circuits(code, sched, rounds, b, 0.0) for b in "ZX"}
    cons = L0Constraints(data_qubits=sched.data, max_qubits=288, rounds=rounds,
                         allowed_gates={"R", "RX", "M", "MX", "CX"},
                         require_opposite_type_detectors=False,
                         min_circuit_distance=None, compute_distance=(rounds == 3),
                         distance_timeout_s=300.0)
    rep = check_l0(circs, cc, "both", cons)
    res2[f"r{rounds}"] = {"passed": rep.passed, "d_circ": rep.d_circ,
                          "checks": [(c.name, c.status) for c in rep.checks], "wall_s": round(time.time() - t0, 1)}
    print(rep.to_text()[:3000])
    # with opposite-type detectors as well
    circs2 = {b: circuits(code, sched, rounds, b, 0.0, detectors="both") for b in "ZX"}
    cons.require_opposite_type_detectors = True
    cons.compute_distance = False
    rep2 = check_l0(circs2, cc, "both", cons)
    res2[f"r{rounds}_both_detectors"] = {"passed": rep2.passed,
                                         "fails": [(c.name, c.message[:200]) for c in rep2.failures]}
out["l0"] = res2
print(json.dumps(res2, indent=1, default=str))

# ------------------------------------------------------------------ 3. noise accounting
c = stim.Circuit(open(f"{RES}/circuit_Z_r12_p0.003.stim").read())
data = set(range(n2, 3 * n2))
seg = 0
counts = collections.defaultdict(lambda: collections.Counter())
idle_who = collections.defaultdict(collections.Counter)
for inst in c.flattened():
    nm = inst.name
    if nm == "TICK":
        seg += 1
        continue
    tg = [t.value for t in inst.targets_copy() if t.is_qubit_target]
    if nm in ("DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Z_ERROR", "M", "MX", "R", "RX", "CX"):
        counts[seg][nm] += len(tg) if nm not in ("DEPOLARIZE2", "CX") else len(tg) // 2
        args = inst.gate_args_copy()
        counts[seg][nm + "_args"] = tuple(args)
    if nm == "DEPOLARIZE1":
        for q in tg:
            kind = "X" if q < n2 else ("data" if q < 3 * n2 else "Z")
            idle_who[seg][kind] += 1
nseg = seg
print("segments (TICK count):", nseg)
per_cycle = []
for cyc in range(12):
    segs = range(1 + 8 * cyc, 1 + 8 * cyc + 8)
    tot = collections.Counter()
    who = collections.Counter()
    for s_ in segs:
        for k, v in counts[s_].items():
            if not k.endswith("_args"):
                tot[k] += v
        who.update(idle_who[s_])
    per_cycle.append({"cyc": cyc, **dict(tot), "idle_on": dict(who)})
init = {k: v for k, v in counts[0].items()}
final = {k: v for k, v in counts[nseg].items()}
args_seen = collections.defaultdict(set)
for s_ in counts:
    for k, v in counts[s_].items():
        if k.endswith("_args"):
            args_seen[k].add(v)
res3 = {"init_segment": init, "init_idle_on": dict(idle_who[0]), "final_segment": final,
        "per_cycle_first": per_cycle[0], "per_cycle_middle": per_cycle[5], "per_cycle_last": per_cycle[11],
        "all_cycles_same_except_last": all(per_cycle[i] == per_cycle[1] for i in range(1, 11)),
        "noise_args": {k: sorted(v) for k, v in args_seen.items()},
        "per_layer_idle_cycle5": [dict(idle_who[1 + 8 * 5 + t]) for t in range(8)]}
out["noise"] = res3
print(json.dumps(res3, indent=1, default=str))

# DEPOLARIZE2 decomposition sanity: stim DEPOLARIZE2(p) = 15 Paulis each p/15 (documented). Check numerically.
t = stim.Circuit("DEPOLARIZE2(0.15) 0 1")
ts = stim.TableauSimulator()
# use explain via DEM on a tiny circuit: measure X/Z of both qubits with detectors
tiny = stim.Circuit("""
R 0 1 2 3
H 0 1
DEPOLARIZE2(0.15) 0 1
H 0 1
M 0 1
DETECTOR rec[-2]
DETECTOR rec[-1]
""")
out["depolarize2_tiny_dem"] = str(tiny.detector_error_model())

# ------------------------------------------------------------------ 4. witness
W = json.load(open(f"{RES}/circuit_distance_witness_X_r3.json"))
faults = []
for f in W["result"]["faults"]:
    pp = re.search(r"flipped_pauli_product: (\S+)", f).group(1)
    ticks = int(re.search(r"after (\d+) TICKs", f).group(1))
    paulis = [(m_.group(1), int(m_.group(2))) for m_ in re.finditer(r"([XYZ])(\d+)", pp)]
    faults.append((ticks, paulis, re.search(r"resolving to (.*)", f).group(1).strip()))
print("faults:", faults)


def inject(base: stim.Circuit, faults, shift_ticks=0):
    """Insert Pauli gates at the END of the segment that follows `ticks` TICKs (i.e. just before
    TICK number ticks+1), which is where the fault sits (after the noisy op of that layer)."""
    by_tick = collections.defaultdict(list)
    for tk, ps, _ in faults:
        by_tick[tk + shift_ticks].extend(ps)
    newc = stim.Circuit()
    seg = 0
    for inst in base.flattened():
        if inst.name == "TICK":
            for P, q in by_tick.get(seg, []):
                newc.append(P + "_ERROR", [q], 1.0)  # as noise, so the reference sample ignores it
            seg += 1
        newc.append(inst)
    return newc


base = circuits(code, sched, 3, "X", 0.0)
res4 = {}
for label, shift in (("as_found", 0), ):
    ci = inject(base, faults, shift)
    det, obs = ci.compile_detector_sampler().sample(4, separate_observables=True)
    res4[label] = {"detectors_fired": int(det[0].sum()), "obs_flipped": np.flatnonzero(obs[0]).tolist(),
                   "deterministic_over_shots": bool((det == det[0]).all() and (obs == obs[0]).all())}
# bulk version: move the 8 initial-prep Z errors to the data-idle slot of round 8 of cycle 0
# (segment after 8 TICKs) and the 2 CNOT faults by one full cycle (+8 TICKs).
bulk = [(8 if tk == 0 else tk + 8, ps, s) for tk, ps, s in faults]
ci = inject(base, bulk, 0)
det, obs = ci.compile_detector_sampler().sample(4, separate_observables=True)
res4["bulk_shifted_one_cycle"] = {"detectors_fired": int(det[0].sum()), "obs_flipped": np.flatnonzero(obs[0]).tolist()}
# are the bulk locations genuine single-fault locations of the noisy circuit? check in noisy circuit layer 7 cycle 0
noisy = circuits(code, sched, 3, "X", 0.001)
seg = 0
idle_at8 = set()
for inst in noisy.flattened():
    if inst.name == "TICK":
        seg += 1
        continue
    if seg == 8 and inst.name == "DEPOLARIZE1":
        idle_at8 |= {t.value for t in inst.targets_copy()}
res4["bulk_init_qubits_are_idle_in_round8_cycle0"] = all(q in idle_at8 for tk, ps, _ in faults if tk == 0 for _, q in ps)
# also: check that the bulk fault set is a genuine 10-fault set via the DEM (each error a single mechanism)
dem = noisy.detector_error_model()
from stimbposd.dem_to_matrices import detector_error_model_to_check_matrices
mm = detector_error_model_to_check_matrices(dem, allow_undecomposed_hyperedges=True)
D = mm.check_matrix.tocsr()
Lm = mm.observables_matrix.tocsr()
xi = np.zeros(D.shape[1], dtype=np.int64)
xi[W["result"]["columns"]] = 1
res4["dem_columns_check"] = {"D_xi_zero": not (D @ xi % 2).any(), "L_xi": np.flatnonzero(Lm @ xi % 2).tolist(),
                             "weight": int(xi.sum())}
out["witness"] = res4
print(json.dumps(res4, indent=1))
json.dump(out, open("research/audits/2026-10-02-E-002-scripts/static_checks_out.json", "w"), indent=1, default=str)
