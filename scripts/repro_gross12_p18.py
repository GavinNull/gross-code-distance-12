"""reproduce_theorems.sh --with-gross12-p18 helper (STATE item 13, E-024a cs_P18_H24: period-18 wrapping circuit, d_circ = 12).

Run through scripts/repro_redirect.py with results/E-024b-audit and results/E-018-audit redirected into $OUT, so that
the auditors' scripts (research/audits/2026-10-11-E-024b-scripts = E-021 audit scripts with the output dir changed;
E-018 audit for the 4224 list) read and write only the fresh directory. Nothing from search/experiments/e024a (or
e021/e018) is imported; the only e024a input is the spec file.

    REPRO_MAP=... SPEC=... TAG=cs_P18 PYTHONPATH=.:tests uv run python scripts/repro_redirect.py scripts/repro_gross12_p18.py premises RMAX
        machine checks of the premises of E-024a's gap argument (audit 2026-10-11-E-024b A-a, as hand-checked by the
        auditor), computed here from the evaluator's noiseless circuits (own parser, not e024a/anyr.py):
          - per ancilla: instances reset at s_q + jD with s_q independent of R (R = 2, 3, 5, 9), measured at
            s_q + jD + dm_q with 0 < dm_q <= D-1, CNOTs strictly inside the window; X ancillas are CNOT controls,
            Z ancillas targets (a fresh ancilla never pushes errors onto data); data reset at layer 0, final readout
            at END <= s(c,R-1) + S + dm_max + 1 for every check c;
          - detector set = {(c,0)} + {(c,j),(c,j-1)} + {H_c readout, (c,R-1)} exactly (both bases);
          - G = max(2D + dm_max - 1, D + S + dm_max) (audit: 52) => fault span <= 10(G-1);
          - insertion periodicity from the auditor's s2_period.json (layer-level, R = 6, 12, both bases): valid
            insert positions contiguous [lo, D R + c], 144 measurements per block;
          - R' = (lo + D - 1 + 10(G-1) + 2D - 2 - c_hi) // D (deletion step, conservative 2D - 1 cut; audit: 32),
            required <= RMAX (the largest R of the exact lift).
    REPRO_MAP=... SPEC=... TAG=cs_P18 PYTHONPATH=.:tests uv run python scripts/repro_redirect.py scripts/repro_gross12_p18.py check RMAX
        PASS/FAIL on the auditor's JSON outputs (b1 legality, b2 extended code, b3 lift + Fig. 12 control, b6 injection,
        s1 premise (A) of the slab argument) and on premises.json.

Expected values are the audited ones (research/audits/2026-10-11-E-024b.md A-a; research/STATE.md item 13).
Exit code 1 if any check fails.
"""
import glob
import json
import os
import sys

AUD = "results/E-024b-audit/" + os.environ.get("TAG", "cs_P18")    # redirected by REPRO_MAP


def premises(rmax):
    import numpy as np
    sys.path.insert(0, "tests")
    from evaluators.tasks import build_code, get_task
    from evaluators.candidate import parse_schedule, build_circuits, layout_for
    code, _ = build_code(get_task("gross-dcirc"), None)
    spec = parse_schedule(json.load(open(os.environ["SPEC"]))).canonical()
    D = spec.period
    lay = layout_for(code)
    n = lay.n
    xa, za = set(lay.x_anc), set(lay.z_anc)
    H = {"Z": np.asarray(code.HZ) % 2, "X": np.asarray(code.HX) % 2}
    anc = {"Z": list(lay.z_anc), "X": list(lay.x_anc)}
    bad = []
    starts0 = dm = None
    for R in (2, 3, 5, 9):
        for basis in "ZX":
            c = build_circuits(spec, code, R)[basis]
            ev = {}            # qubit -> [(layer, kind)]
            meas_of, cnt, dets = [], {}, []
            layer = 0
            for op in c.flattened():
                nm = op.name
                if nm == "TICK":
                    layer += 1; continue
                tg = [t.value for t in op.targets_copy()] if nm not in ("DETECTOR", "OBSERVABLE_INCLUDE") else None
                if nm in ("R", "RX"):
                    for q in tg: ev.setdefault(q, []).append((layer, "R"))
                elif nm == "CX":
                    for a, b in zip(tg[::2], tg[1::2]):
                        if not ((a in xa and b < n) or (b in za and a < n)):
                            bad.append(f"R{R}{basis} CX {a},{b} orientation")
                        ev.setdefault(a, []).append((layer, "C")); ev.setdefault(b, []).append((layer, "C"))
                elif nm in ("M", "MX"):
                    for q in tg:
                        k = cnt.get(q, 0); cnt[q] = k + 1
                        meas_of.append((q, k)); ev.setdefault(q, []).append((layer, "M"))
                elif nm == "DETECTOR":
                    dets.append(frozenset(meas_of[len(meas_of) + t.value] for t in op.targets_copy()))
                elif nm != "OBSERVABLE_INCLUDE":
                    bad.append(f"R{R}{basis} unexpected op {nm}")
            END = layer        # final data readout is after the last TICK
            starts, dmq = {}, {}
            for q in list(xa | za):
                e = ev[q]
                if len(e) != 8 * R:
                    bad.append(f"R{R}{basis} anc {q} has {len(e)} ops"); continue
                for j in range(R):
                    blk = e[8 * j: 8 * j + 8]
                    if [k for _, k in blk] != ["R"] + ["C"] * 6 + ["M"]:
                        bad.append(f"R{R}{basis} anc {q} inst {j} pattern"); continue
                    r, m = blk[0][0], blk[7][0]
                    starts.setdefault(q, r - D * j)
                    dmq.setdefault(q, m - r)
                    if r != starts[q] + D * j or m - r != dmq[q] or not (0 < m - r <= D - 1):
                        bad.append(f"R{R}{basis} anc {q} inst {j} timing")
                    if not all(r < t < m for t, _ in blk[1:7]):
                        bad.append(f"R{R}{basis} anc {q} inst {j} window")
            for q in range(n):
                e = ev[q]
                if e[0] != (0, "R") or e[-1] != (END, "M") or any(k != "C" for _, k in e[1:-1]):
                    bad.append(f"R{R}{basis} data {q} pattern")
            if starts0 is None:
                starts0, dm = starts, dmq
            elif starts != starts0 or dmq != dm:
                bad.append(f"R{R}{basis} starts/dm depend on R")
            S_ = max(starts.values()) - min(starts.values()); dmax_ = max(dmq.values())
            if any(END > starts[q] + D * (R - 1) + S_ + dmax_ + 1 for q in starts):
                bad.append(f"R{R}{basis} END bound")
            want = set()
            for i, q in enumerate(anc[basis]):
                want.add(frozenset({(q, 0)}))
                want |= {frozenset({(q, j), (q, j - 1)}) for j in range(1, R)}
                want.add(frozenset({(int(d), 0) for d in np.flatnonzero(H[basis][i])} | {(q, R - 1)}))
            if set(dets) != want or len(dets) != len(want):
                bad.append(f"R{R}{basis} detector set")
    S = max(starts0.values()) - min(starts0.values())
    dmax = max(dm.values())
    G = max(2 * D + dmax - 1, D + S + dmax)
    span = 10 * (G - 1)
    s2 = json.load(open(f"{AUD}/s2_period.json"))
    lo, chi, nblk = set(), set(), set()
    for b in "ZX":
        for R in (6, 12):
            r = s2[f"{b}_R{R}"]
            if not r["contiguous"]:
                bad.append(f"s2 {b} R{R} not contiguous")
            lo.add(r["valid_insert_min"]); chi.add(r["valid_insert_max"] - D * (R + 1)); nblk.add(r["meas_targets_in_block"])
    if len(lo) != 1 or len(chi) != 1 or nblk != {144}:
        bad.append(f"s2 lo {lo} c_hi {chi} block meas {nblk}")
    lo, c_hi = max(lo), max(chi)
    Rp = (lo + D - 1 + span + 2 * D - 2 - c_hi) // D
    info = dict(D=D, S=S, dm_max=dmax, G=G, span=span, lo=lo, c_hi=c_hi, R_prime=Rp, rmax=rmax, problems=bad[:20],
                nproblems=len(bad))
    json.dump(info, open(f"{AUD}/premises.json", "w"), indent=1)
    ok = not bad and G == 52 and Rp <= rmax
    print(("PASS  " if ok else "FAIL  ") +
          f"e024a gap-argument premises (own parser of the evaluator circuits, R = 2, 3, 5, 9, both bases): D = {D}, "
          f"starts R-independent, dm_max = {dmax} <= D-1, S = {S}, CNOTs inside windows, template CNOT orientation, "
          f"detector set exact; G = max(2D+dm_max-1, D+S+dm_max) = {G} (audit: 52), span <= {span}; "
          f"insertion periodicity (auditor s2, R = 6, 12): x in [{lo}, D R {c_hi + D:+d}], 144 meas/block "
          f"=> R' = {Rp} (audit: 32) <= lifted R = {rmax}" + (f"; problems {bad[:5]}" if bad else ""))
    return int(not ok)


def check(rmax):
    d = AUD
    bad = 0

    def out(ok, msg):
        nonlocal bad
        print(("PASS  " if ok else "FAIL  ") + msg)
        bad |= not ok

    b1 = json.load(open(f"{d}/b1_legal.json"))
    det = b1["determinism"]; l0 = b1["L0"]
    ok = (b1["own_poly_eq_evaluator_transpose=False"] and b1["k"] == 12 and b1["HXHZt0"]
          and not b1["own_spec_problems"] and not b1["evaluator_validate_problems"] and b1["period"] == 18
          and b1["preps"] == [2, 15, 16, 17] and b1["meas"] == [0, 14, 15, 16]
          and not any(v["any_fire_noiseless"] for v in det.values()) and all(v["passed"] for v in l0.values())
          and b1["switch_hist"] == {"2": 48, "4": 96})
    out(ok, f"e024a legality (auditor b1): own gross matrices = evaluator, k = {b1['k']}; own spec check and evaluator "
            f"validate_schedule 0 problems; period {b1['period']}, prep {b1['preps']} / meas {b1['meas']} (wrapping); "
            f"noiseless 0 fires ({len(det)} circuits); L0 {sum(v['passed'] for v in l0.values())}/{len(l0)}; "
            f"X/Z switches per data qubit {b1['switch_hist']} (interleaved)")

    b2 = json.load(open(f"{d}/b2_ext.json"))
    dems = {k: v for k, v in b2.items() if k.startswith("dem_")}
    ok = (all(b2[f"ext_{k}"]["equal"] and b2[f"ext_{k}"]["equal_E018_audit_build"] and b2[f"ext_{k}"]["N_cand"] == 360
              for k in "XZ") and b2["order_relation"] == {"same": 0, "rev+swaps": 144, "other": 0}
          and b2["P1_T_P3_match_reversed"] and len(dems) == 6
          and all(v["equal_ext"] and v["telescoping_bad"] == 0 and v["bad_obs"] == 0 for v in dems.values()))
    out(ok, f"e024a extended code (auditor b2): key set = Fig. 12's, both sides (N = {b2['ext_X']['N_cand']}/"
            f"{b2['ext_Z']['N_cand']}; also = E-018 audit build); order relation to Fig. 12 {b2['order_relation']}; "
            f"DEM image set = extended code, telescoping_bad = bad_obs = 0 ({len(dems)} (R, basis))")

    for b in "ZX":
        recs = [r for fn in glob.glob(f"{d}/b3_cand_{b}_*.json") for r in json.load(open(fn))]
        Rs = sorted(r["R"] for r in recs)
        ok = (Rs == list(range(1, rmax + 1)) and all(r["lifting"] == 0 and r["of"] == 4224 and r["telescoping_bad"] == 0
                                                     and r["bad_obs"] == 0 for r in recs))
        out(ok, f"e024a lift basis {b} (auditor b3, CP-SAT, E-018 audit 4224 list): R = 1..{rmax} ({len(recs)} runs), "
                f"lifting {sorted({r['lifting'] for r in recs})} of 4224 at every R => no undetected logical of "
                f"weight <= 11")
    for b in "ZX":
        r = json.load(open(f"{d}/b3_fig12_{b}_1.json"))[0]
        out(r["lifting"] == 4224 and r["of"] == 4224,
            f"e024a positive control: Fig. 12 basis {b} R = 1 lifts {r['lifting']}/{r['of']} (d_circ = 11 circuit)")

    b6 = json.load(open(f"{d}/b6_inject.json"))
    for b in "ZX":
        r = b6[b]
        rr = [k for k in r if k.startswith("R")]
        ok = (r["weight"] == 12 and len(rr) == 4 and all(not r[k]["any_detector"] and any(r[k]["obs_flipped"])
                                                          and r[k]["minus_one_detected"] for k in rr))
        out(ok, f"e024a upper bound basis {b} (auditor b6): weight-{r['weight']} data logical injected after reset, "
                f"{', '.join(rr)}: 0 detectors, observable flipped; minus one fault detected => d_circ <= 12")

    s1 = {R: json.load(open(f"{d}/s1_slab_R{R}.json")) for R in (3, 8, 24)}
    ok = all(v["premiseA_Z_violations"] == 0 and v["premiseA_X_violations"] == 0 for v in s1.values())
    out(ok, f"e024a slab-argument premise (A) (auditor s1, supplementary second any-R route): R = 3, 8, 24 both bases, "
            f"violations {[(v['premiseA_Z_violations'], v['premiseA_X_violations']) for v in s1.values()]}; "
            f"slab 1 = {s1[3]['slabs'][1]}")

    pr = json.load(open(f"{d}/premises.json"))
    out(pr["nproblems"] == 0 and pr["G"] == 52 and pr["R_prime"] <= rmax,
        f"e024a any-R (gap argument): G = {pr['G']}, R' = {pr['R_prime']} <= {rmax} = largest lifted R "
        f"=> d_circ = 12 for every R, both bases")
    return int(bad)


if __name__ == "__main__":
    mode = sys.argv[1]
    sys.exit(premises(int(sys.argv[2])) if mode == "premises" else check(int(sys.argv[2])))
