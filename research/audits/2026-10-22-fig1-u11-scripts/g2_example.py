"""Claim 2: the example weight-10 logical {0,6,80,97,126,127} + suffixes of X3, X45, X48, X59.
Lift in segctl (own DP) with injection-verified witness; no lift in u11; single forced detector Z69 final;
tick mechanism on q123.  R = 1, Z basis, SD6 p = 1e-3."""
import collections, json, sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
from g_common import *

NOISE = {"DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Y_ERROR", "Z_ERROR", "PAULI_CHANNEL_1", "PAULI_CHANNEL_2"}
SEG = segctl()
seg_audit = json.load(open("results/E-032-audit/segctl_spec.json"))
norm = lambda d: (d["period"], [(c["prep"], c["meas"], sorted(map(tuple, c["cnots"]))) for c in d["x_checks"]],
                  [(c["prep"], c["meas"], sorted(map(tuple, c["cnots"]))) for c in d["z_checks"]])
out = {"segctl_equals_E032_audit_file": norm(SEG) == norm(seg_audit)}

colsU, colsS = ext_columns(U11), ext_columns(SEG)
out["ext_columns"] = [len(colsU), len(colsS), set(colsU) == set(colsS)]

data = [0, 6, 80, 97, 126, 127]
hooks = {}
for xi in (3, 45, 48, 59):
    o = order_of(U11["x_checks"][xi], U11["period"])
    hooks[xi] = o
# the figure's hook supports
fig = {3: (72, 81), 45: (47, 114, 123, 129), 48: (50, 123, 126, 132), 59: (128, 137)}
for xi, s in fig.items():
    o = hooks[xi]
    out.setdefault("hook_is_suffix", {})[xi] = [o, any(tuple(sorted(o[k:])) == s for k in range(1, 6))]
S = [(q,) for q in data] + [fig[x] for x in (3, 45, 48, 59)]
v = np.zeros(N, np.uint8)
for s in S:
    for q in s: v[q] ^= 1
out["HZ_sum_zero"] = bool(not ((HZ @ v) % 2).any())
out["LZ_rows_flipped"] = [int(i) for i in np.flatnonzero((LZ @ v) % 2)]
keys = [key_of(s) for s in S]
out["all_keys_are_columns"] = all(k in colsU for k in keys)
cols_list, w10 = load_w10()
out["in_E032_w10_list"] = tuple(sorted(keys)) in {tuple(sorted(T)) for T in w10}

res = {}
for name, sj in (("seg", SEG), ("u11", U11)):
    c = circ(sj, 1)
    aug, dem, G, zero = dem_groups(c)
    cols = [[d for d, _ in G[k]] for k in keys]
    ok, ch = feasible(cols, want=True)
    r = dict(lifts=ok, terms_per_column=[len(x) for x in cols])
    if ok:
        pick = [G[k][j] for k, j in zip(keys, ch)]
        sub = stim.DetectorErrorModel()
        for _, inst in pick: sub.append(inst)
        locs = []
        for e in aug.explain_detector_error_model_errors(dem_filter=sub, reduce_to_one_representative_error=True):
            L = e.circuit_error_locations[0]
            locs.append(dict(tick=L.tick_offset, op=L.stack_frames[0].instruction_offset,
                             paulis=[(p.gate_target.pauli_type, p.gate_target.value) for p in L.flipped_pauli_product]))
        by = collections.defaultdict(list)
        for L in locs: by[L["op"]].append(L)
        new = stim.Circuit()
        for i, op in enumerate(c):
            if op.name in NOISE:
                for L in by.get(i, []):
                    for p, q in L["paulis"]: new.append(f"{p}_ERROR", [q], 1.0)
                continue
            if op.name in ("M", "MX", "MR", "MRX", "R", "RX", "MPP") and op.gate_args_copy():
                new.append(op.name, op.targets_copy()); continue
            new.append(op)
        # also strip measurement-flip noise args: rebuild measurements without probability
        dets, obs = new.compile_detector_sampler().sample(4, separate_observables=True)
        r.update(witness=locs, injected_fired=[int(x.sum()) for x in dets], injected_obs=[list(map(int, np.flatnonzero(o))) for o in obs],
                 expected_obs=out["LZ_rows_flipped"], noisy_meas_ops=sum(1 for op in new if op.name in ("M", "MX", "MR", "MRX") and op.gate_args_copy()))
    else:
        coords = dem.get_detector_coordinates()
        syns = all_syndromes(cols)
        mins = minimal_family(syns)
        univ = set().union(*[d for col in cols for d in col])
        forced = [d for d in univ if all(d in s for s in syns)]
        hs = hitting_sets(mins, univ)
        r.update(n_syndromes=len(syns), n_minimal=len(mins), forced=[(d, coords[d]) for d in forced],
                 irreducible_sets=[[(d, coords[d][:2]) for d in A] for A in hs][:20], n_irreducible=len(hs),
                 irreducible_sizes=dict(collections.Counter(len(A) for A in hs)),
                 deletion_asc=iis_deletion(cols, sorted(univ)), deletion_desc=iis_deletion(cols, sorted(univ, reverse=True)))
        # per column: which terms flip det141
        r["col_flip_Z69final"] = [sorted(collections.Counter(int(141 in d) for d in col).items()) for col in cols]
        r["Z69_round0_det"] = [d for d, cc in coords.items() if cc[0] == 69 and cc[1] == 0]
        # hook term realisations in u11
        hk = []
        for k, s in zip(keys[6:], S[6:]):
            for d, inst in G[k]:
                sub = stim.DetectorErrorModel(); sub.append(inst)
                e = aug.explain_detector_error_model_errors(dem_filter=sub, reduce_to_one_representative_error=False)[0]
                hk.append(dict(support=s, dets=sorted(d), n_realisations=len(e.circuit_error_locations),
                               realisations=sorted({(L.tick_offset, tuple((p.gate_target.pauli_type, p.gate_target.value) for p in L.flipped_pauli_product))
                                                    for L in e.circuit_error_locations})[:12]))
        r["hook_terms"] = hk
    cx, meas, reset = tick_tables(c)
    r["q123"] = dict(Z69_read=cx.get((123, N + NC + 69)), Z69_meas=meas.get(N + NC + 69),
                     X45_dep=cx.get((N + 45, 123)), X48_dep=cx.get((N + 48, 123)),
                     X45_all=sorted((cx[(N + 45, q)][0], q) for q in hooks[45]),
                     X48_all=sorted((cx[(N + 48, q)][0], q) for q in hooks[48]))
    r["Z69_support"] = [int(q) for q in np.flatnonzero(HZ[69])]
    r["Z69_support_in_logical"] = sorted({q for s in S for q in s if HZ[69, q]})
    r["Z69_support_multiplicity"] = {int(q): sum(q in s for s in S) for q in np.flatnonzero(HZ[69]) if any(q in s for s in S)}
    res[name] = r
out["res"] = res
print(json.dumps(out, indent=1, default=str))
json.dump(out, open(OUT + "/g2_example.json", "w"), indent=1, default=str)
