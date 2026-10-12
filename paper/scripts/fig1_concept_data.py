"""Data for Fig. 1 (concept figure), panel (b): one real "10 data + 1 hook" weight-11 extended logical, its
injection-verified lift under Fig. 12 timing, and why it cannot lift under the period-18 circuit cs_P18_H24.

  uv run python paper/scripts/fig1_concept_data.py [--stats]

Writes paper/figures/fig1_concept_data.json (read by fig1_concept.py). Single process.
Read-only inputs: the E-018 audit's complete weight-11 list (results/E-018-audit/dfs_*), Fig. 12 (E-018 audit's
evaluator-format spec built from baselines.strikis), search/experiments/e024a/cs_P18_H24.json, and the
E-021 audit helper code (research/audits/2026-10-10-E-021-scripts/b_common.py: own extended code, own DEM).
Setting: Z-basis memory (X errors; hooks of X checks), R = 1 round, SD6 noise (as in the audits' lift runs).

Method (all exact, no frame model):
  * the chosen logical S = first entry of the audited 4224 list whose columns are 10 data columns + one
    length-2 residual column of Fig. 12 (asserted: 360 such per basis, claims_map C13);
  * Fig. 12: CP-SAT finds one DEM term per column with zero total detector syndrome (the lift); the 11 terms are
    mapped to circuit locations with stim's explain_detector_error_model_errors and injected with probability 1
    into the noiseless circuit (asserted: 0 detectors, a logical observable flips);
  * cs_P18_H24: CP-SAT proves no zero-syndrome choice exists (asserted INFEASIBLE, as in the audit), then a
    minimal unsatisfiable set of detector constraints is extracted by deletion; for each column we record which
    of those detectors each of its DEM terms flips, plus the read times that explain it.
--stats repeats the infeasibility + core extraction for all 360 such logicals (core sizes / check counts).
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests"), str(ROOT / "research/audits/2026-10-10-E-021-scripts")]
import os  # noqa: E402

os.chdir(ROOT)
from b_common import (A1, HZ, LZ, add_noise, audit018_lists, build_circuits, code, ext_keys, load_spec,  # noqa: E402
                      np, orders, parse_schedule, stim)
from ortools.sat.python import cp_model  # noqa: E402

KIND, BASIS, R = "X", "Z", 1
CS = "search/experiments/e024a/cs_P18_H24.json"
OUT = ROOT / "paper/figures/fig1_concept_data.json"
NOISE = {"DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Y_ERROR", "Z_ERROR", "PAULI_CHANNEL_1", "PAULI_CHANNEL_2"}


def fail(msg):
    raise SystemExit(f"AUDIT MISMATCH: {msg}")


def build(spec):
    c = add_noise(build_circuits(spec.canonical(), code, R)[BASIS], "sd6", 1e-3).flattened()
    n, k0, nH = 144, c.num_observables, HZ.shape[0]
    aug = c.copy()
    for r, row in enumerate(list(HZ) + list(LZ)):
        aug.append("OBSERVABLE_INCLUDE", [stim.target_rec(q - n) for q in np.nonzero(row)[0]], k0 + r)
    dem = aug.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    groups = {}
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        dets, hb, lb = set(), np.zeros(nH, np.uint8), np.zeros(LZ.shape[0], np.uint8)
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                dets ^= {t.val}
            elif t.is_logical_observable_id() and t.val >= k0:
                (hb if t.val < k0 + nH else lb)[(t.val - k0) if t.val < k0 + nH else (t.val - k0 - nH)] ^= 1
        if hb.any() or lb.any():
            groups.setdefault(hb.tobytes() + lb.tobytes(), []).append((frozenset(dets), inst))
    return c, aug, dem, groups


def model(S, groups, active=None):
    M = cp_model.CpModel()
    det_lits, choice = {}, {}
    for key in S:
        vs = []
        for j, (dets, _) in enumerate(groups[key]):
            v = M.NewBoolVar("")
            vs.append(v)
            choice[(key, j)] = v
            for d in dets:
                det_lits.setdefault(d, []).append(v)
        M.AddExactlyOne(vs)
    one = M.NewConstant(1)
    for d, ls in det_lits.items():
        if active is None or d in active:
            M.AddBoolXOr(ls + [one])
    s = cp_model.CpSolver()
    s.parameters.num_workers = 1
    s.parameters.random_seed = 7
    st = s.Solve(M)
    ok = st in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    pick = [(k, j) for (k, j), v in choice.items() if ok and s.Value(v)]
    return ok, pick, sorted(det_lits)


def mus(S, groups):
    ok, _, act = model(S, groups)
    if ok:
        fail("expected no lift")
    i = 0
    while i < len(act):
        trial = act[:i] + act[i + 1:]
        if not model(S, groups, set(trial))[0]:
            act = trial
        else:
            i += 1
    return act


def gate_ticks(c):
    """(Z row, data q) -> ticks of CX(q -> Z ancilla); (X row, data q) -> ticks of CX(X ancilla -> q)."""
    n, mx = 144, 72
    tick, zr, xr = 0, collections.defaultdict(list), collections.defaultdict(list)
    for op in c:
        if op.name == "TICK":
            tick += 1
            continue
        if op.name in ("CX", "CNOT"):
            t = op.targets_copy()
            for a, b in zip(t[::2], t[1::2]):
                a, b = a.value, b.value
                if b >= n + mx:
                    zr[(b - n - mx, a)].append(tick)
                elif n <= a < n + mx:
                    xr[(a - n, b)].append(tick)
    return zr, xr


def locate(aug, terms):
    sub = stim.DetectorErrorModel()
    for _, inst in terms:
        sub.append(inst)
    out = []
    for e in aug.explain_detector_error_model_errors(dem_filter=sub, reduce_to_one_representative_error=True):
        loc = e.circuit_error_locations[0]
        if loc.flipped_measurement is not None and loc.flipped_measurement.measurement_record_index is not None \
                and not loc.flipped_pauli_product:
            fail("witness term is a bare measurement flip; injection not implemented")
        out.append(dict(tick=loc.tick_offset, op=loc.stack_frames[0].instruction_offset,
                        paulis=[(p.gate_target.pauli_type, p.gate_target.value) for p in loc.flipped_pauli_product],
                        gate=loc.instruction_targets.gate))
    return out


def inject(c, locs):
    """Noiseless copy of c with each located Pauli inserted at its noise instruction (probability 1)."""
    by = collections.defaultdict(list)
    for L in locs:
        by[L["op"]].append(L)
    new = stim.Circuit()
    for i, op in enumerate(c):
        if op.name in NOISE:
            for L in by.get(i, []):
                for p, q in L["paulis"]:
                    new.append(f"{p}_ERROR", [q], 1.0)
            continue
        new.append(op)
    smp = new.compile_detector_sampler()
    d, o = smp.sample(1, separate_observables=True)
    return int(d.sum()), [int(x) for x in np.nonzero(o[0])[0]]


def main(stats: bool):
    f12 = parse_schedule(A1.SPEC.to_dict())
    cs = load_spec(CS)
    xo, zo = orders(f12)
    keys = ext_keys(KIND, xo, zo)
    lists, kb = audit018_lists(KIND)
    if len(lists) != 4224:
        fail(f"C13: 4224 weight-11 logicals, got {len(lists)}")
    sup = {k: keys[k] for k in kb}
    r2 = [i for i, S in enumerate(lists) if sorted(len(sup[k]) for k in S) == [1] * 10 + [2]]
    if len(r2) != 360:
        fail(f"C13: 360 '10 data + r2' logicals, got {len(r2)}")
    idx = r2[0]
    S = lists[idx]
    hook = [sup[k] for k in S if len(sup[k]) == 2][0]
    data = sorted(sup[k][0] for k in S if len(sup[k]) == 1)
    hx = [i for i, o in enumerate(xo) if tuple(sorted(o[4:])) == tuple(sorted(hook))]
    if len(hx) != 1:
        fail("hook residual must be the last two of exactly one Fig. 12 X check")
    hx = hx[0]
    res = dict(setting=dict(basis=BASIS, R=R, noise="sd6"), logical_index=idx, n_r2=len(r2), data=data,
               hook=list(hook), hook_xcheck=hx, orders={})

    # ---- Fig. 12: lift + injection
    c, aug, dem, groups = build(f12)
    ok, pick, _ = model(S, groups)
    if not ok:
        fail("Fig. 12 must lift this logical (C13/C34)")
    terms = [groups[k][j] for k, j in pick]
    if any(d for d in set().union(*[t[0] for t in terms]) if sum(d in t[0] for t in terms) % 2):
        fail("witness syndrome not zero")
    locs = locate(aug, terms)
    ndet, flipped = inject(c, locs)
    if ndet != 0 or not flipped:
        fail(f"injection: {ndet} detectors, observables {flipped}")
    anc = [L for L in locs if any(q >= 144 for _, q in L["paulis"])]
    dat = [L for L in locs if all(q < 144 for _, q in L["paulis"])]
    if not (len(anc) == 1 and len(dat) == 10 and anc[0]["paulis"] == [("X", 144 + hx)]):
        fail(f"Fig. 12 witness is not 10 data faults + 1 hook on X check {hx}: {locs}")
    zr, xr = gate_ticks(c)
    res["fig12"] = dict(witness=locs, injected_detectors=ndet, injected_observables_flipped=flipped,
                        hook_cnot_ticks={str(q): xr[(hx, q)] for q in xo[hx]}, xorder=xo[hx])

    # ---- cs_P18_H24: no lift, minimal conflicting detectors
    c2, aug2, dem2, groups2 = build(cs)
    if model(S, groups2)[0]:
        fail("cs_P18_H24 must not lift (E-024b A-a)")
    core = mus(S, groups2)
    coords = dem2.get_detector_coordinates()
    core_info = [dict(det=d, zcheck=int(coords[d][0]), kind="final" if coords[d][1] == R else "round")
                 for d in core]
    core_checks = [ci["zcheck"] for ci in core_info]
    zr2, xr2 = gate_ticks(c2)
    xo2, _ = orders(cs)
    coords1 = dem.get_detector_coordinates()
    by_check1 = {(int(v[0]), v[1]): d for d, v in coords1.items()}
    by_check2 = {(int(v[0]), v[1]): d for d, v in coords.items()}

    def sig(groups_, by_check, key):
        return sorted(collections.Counter(
            tuple(int(by_check[(r, float(R))] in dets) for r in core_checks)
            for dets, _ in groups_[key]).items())

    cols = []
    for key in S:
        s_ = sup[key]
        cols.append(dict(support=list(s_), checks=[r for r in core_checks if any(HZ[r, q] for q in s_)],
                         sig_fig12=sig(groups, by_check1, key), sig_p18=sig(groups2, by_check2, key)))
    # read ticks of the core checks on every data qubit of the logical, and on the hook's physical deposit qubits
    hook_terms2 = groups2[[k for k in S if len(sup[k]) == 2][0]]
    hook_locs2 = locate(aug2, hook_terms2)
    allq = sorted(set(data) | set(hook) | set(xo[hx]))
    reads = {str(r): {str(q): (zr[(r, q)], zr2[(r, q)]) for q in allq if HZ[r, q]} for r in core_checks}
    res["p18"] = dict(core=core_info, columns=cols, reads_fig12_p18=reads, hook_terms=hook_locs2,
                      hook_cnot_ticks={str(q): xr2[(hx, q)] for q in xo2[hx]}, xorder=xo2[hx])
    # witness data-fault ticks in Fig. 12 (for the drawing)
    res["fig12"]["data_fault_ticks"] = {str(q): L["tick"] for L in dat for _, q in L["paulis"]}

    if stats:
        sizes = collections.Counter()
        for i in r2:
            co = mus(lists[i], groups2)
            sizes[len(co)] += 1
        res["stats_core_sizes_all_r2"] = dict(sorted(sizes.items()))
        print("core sizes over 360:", dict(sizes))
    elif OUT.exists():
        old = json.loads(OUT.read_text())
        if "stats_core_sizes_all_r2" in old:
            res["stats_core_sizes_all_r2"] = old["stats_core_sizes_all_r2"]
    OUT.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: v for k, v in res.items() if k in ("logical_index", "data", "hook", "hook_xcheck")}))
    print("fig12 witness ticks:", sorted((L["tick"], L["paulis"]) for L in locs))
    print("p18 core:", core_info)
    for col in cols:
        print(col)
    print("reads (fig12, p18):", reads)
    print("p18 hook terms:", hook_locs2, "cnot ticks", res["p18"]["hook_cnot_ticks"])


if __name__ == "__main__":
    main("--stats" in sys.argv[1:])
