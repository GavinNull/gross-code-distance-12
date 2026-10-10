"""reproduce_theorems.sh --with-gross12 helper (E-021: gross [[144,12,12]] interleaved circuit cand_p21, d_circ = 12).

Run through scripts/repro_redirect.py with results/E-018-audit and results/E-021-audit redirected into $OUT, so that
the auditors' scripts (research/audits/2026-10-08-E-018-scripts, 2026-10-10-E-021-scripts) read and write only the
fresh directory. Nothing from search/experiments/e021 (or e018) is imported; the only e021 input is the spec file.

    REPRO_MAP=... PYTHONPATH=.:tests uv run python scripts/repro_redirect.py scripts/repro_gross12.py jobs
        E-018 audit write_jobs(): column-orbit classes + EXCL files + jobs.txt for w11dfs (W = 11, both sides)
    REPRO_MAP=... SPEC=... PYTHONPATH=.:tests uv run python scripts/repro_redirect.py scripts/repro_gross12.py list
        collect the fresh DFS outputs, expand by the 24-element group (E-018 audit b_common.audit018_lists),
        check every list entry is a weight-11 extended logical (own matrices), count per side (expect 4224 = 176 x 24)
    REPRO_MAP=... SPEC=... PYTHONPATH=.:tests uv run python scripts/repro_redirect.py scripts/repro_gross12.py check RMAX
        PASS/FAIL on the auditor's JSON outputs (b1 legality, b2 extended code, b3 lift, b6 injection, b7 any-R premises)

Expected values are the audited ones (research/audits/2026-10-10-E-021.md F1; research/STATE.md item 10).
Exit code 1 if any check fails.
"""
import glob
import json
import os
import sys

sys.path.insert(0, "research/audits/2026-10-10-E-021-scripts")
sys.path.insert(0, "research/audits/2026-10-08-E-018-scripts")

AUD18 = "results/E-018-audit"     # redirected by REPRO_MAP
AUD21 = "results/E-021-audit"     # redirected by REPRO_MAP
NODES_AUDIT = {"X": 6174513371, "Z": 5819348553}   # E-018 audit a2_collect.json (deterministic DFS; informational)


def jobs():
    import a2_stage_a as A2
    A2.write_jobs()
    return 0


def lists():
    import numpy as np
    import b_common as B
    A2 = B.A2
    bad = 0
    for kind in "XZ":
        fns = sorted(glob.glob(f"{AUD18}/dfs_{kind}_*.txt"))
        summ = [l.split() for fn in fns for l in open(fn) if l.startswith("SUMMARY")]
        nodes = sum(int(s[4]) for s in summ)
        raw = sum(1 for fn in fns for l in open(fn) if not l.startswith("SUMMARY") and l.strip())
        L, kb = B.audit018_lists(kind)
        keys, kidx, colsup, supkey = A2.build_cache[kind]
        H = np.array([hb for hb, _ in keys], np.uint8).T     # rows: checks, cols: extended columns
        Lm = np.array([lb for _, lb in keys], np.uint8).T
        perms = [A2.colperm(kind, pp, kidx, colsup) for pp in A2.group(kind)]
        idx = {k: i for i, k in enumerate(kb)}
        okv = 0
        orbits = set()
        for S in L:
            cols = sorted(idx[k] for k in S)
            x = np.zeros(len(keys), np.uint8); x[cols] = 1
            if len(set(cols)) == 11 and not ((H @ x) % 2).any() and ((Lm @ x) % 2).any():
                okv += 1
            orbits.add(min(tuple(sorted(p[j] for j in cols)) for p in perms))
        njobs = sum(1 for l in open(f"{AUD18}/jobs.txt") if l.startswith(kind + " "))
        ok = len(summ) == njobs and len(L) == 4224 and okv == 4224 and len(orbits) == 176 and len(keys) == 360
        print(f"{'PASS' if ok else 'FAIL'}  e021 weight-11 list kind {kind} ({B.BASIS_OF_KIND[kind]}-basis memory): DFS W=11 "
              f"{len(summ)}/{njobs} jobs complete, {raw} raw solutions, {nodes} nodes (E-018 audit: "
              f"{NODES_AUDIT[kind]}{', same' if nodes == NODES_AUDIT[kind] else ', DIFFERENT'}); "
              f"expanded by {len(perms)}-element group: {len(L)} logicals ({okv} verified He x = 0, Le x != 0, "
              f"11 distinct of N = {len(keys)}), {len(orbits)} orbits")
        bad |= not ok
    return int(bad)


def check(rmax):
    d = AUD21
    bad = 0

    def out(ok, msg):
        nonlocal bad
        print(("PASS  " if ok else "FAIL  ") + msg)
        bad |= not ok

    b1 = json.load(open(f"{d}/b1_legal.json"))
    det = b1["determinism"]; l0 = b1["L0"]
    ok = (b1["own_poly_eq_evaluator_transpose=False"] and b1["k"] == 12 and b1["HXHZt0"]
          and not b1["own_spec_problems"] and not b1["evaluator_validate_problems"]
          and b1["preps"] == [0] and b1["meas"] == [b1["period"] - 1] and b1["period"] == 21
          and not any(v["any_fire_noiseless"] for v in det.values()) and all(v["passed"] for v in l0.values())
          and set(b1["switch_hist"]) != {"2"})
    out(ok, f"e021 legality (auditor b1): own gross matrices = evaluator, k = {b1['k']}; own spec check and evaluator "
            f"validate_schedule 0 problems; period {b1['period']}, all prep 0 / meas {b1['meas']}; noiseless 0 fires "
            f"({len(det)} circuits); L0 {sum(v['passed'] for v in l0.values())}/{len(l0)}; "
            f"X/Z switches per data qubit {b1['switch_hist']} (interleaved)")

    b2 = json.load(open(f"{d}/b2_ext.json"))
    dems = {k: v for k, v in b2.items() if k.startswith("dem_")}
    ok = (all(b2[f"ext_{k}"]["equal"] and b2[f"ext_{k}"]["equal_E018_audit_build"] and b2[f"ext_{k}"]["N_cand"] == 360
              for k in "XZ")
          and all(v["equal_ext"] and v["telescoping_bad"] == 0 and v["bad_obs"] == 0 for v in dems.values()))
    out(ok, f"e021 extended code (auditor b2): key set = Fig. 12's, both sides (N = {b2['ext_X']['N_cand']}/"
            f"{b2['ext_Z']['N_cand']}; also = E-018 audit build); order relation to Fig. 12 {b2['order_relation']}; "
            f"DEM image set = extended code, telescoping_bad = bad_obs = 0 ({len(dems)} (R, basis))")

    Rs = list(range(1, rmax + 1))
    for b in "ZX":
        recs = json.load(open(f"{d}/b3_cand_{b}_{'-'.join(map(str, Rs))}.json"))
        ok = ([r["R"] for r in recs] == Rs and all(r["lifting"] == 0 and r["of"] == 4224 and r["telescoping_bad"] == 0
                                                    and r["bad_obs"] == 0 for r in recs))
        out(ok, f"e021 lift basis {b} (auditor b3, CP-SAT): R = 1..{rmax}, lifting "
                f"{sorted({r['lifting'] for r in recs})} of 4224 at every R => no undetected logical of weight <= 11")
    for b in "ZX":
        r = json.load(open(f"{d}/b3_fig12_{b}_1.json"))[0]
        out(r["lifting"] == 4224 and r["of"] == 4224,
            f"e021 positive control: Fig. 12 basis {b} R = 1 lifts {r['lifting']}/{r['of']} (d_circ = 11 circuit)")

    b6 = json.load(open(f"{d}/b6_inject.json"))
    for b in "ZX":
        r = b6[b]
        rr = [k for k in r if k.startswith("R")]
        ok = (r["weight"] == 12 and len(rr) == 4 and all(not r[k]["any_detector"] and any(r[k]["obs_flipped"])
                                                          and r[k]["minus_one_detected"] for k in rr))
        out(ok, f"e021 upper bound basis {b} (auditor b6): weight-{r['weight']} data logical injected after reset, "
                f"{', '.join(rr)}: 0 detectors, observable flipped; minus one fault detected => d_circ <= 12")

    b7 = json.load(open(f"{d}/b7_periodic.json"))
    out(all(v["ok"] if isinstance(v, dict) else v for v in b7.values()),
        f"e021 any-R premises (auditor b7): round separation R = 3, 8; layer periodicity rounds 1..12; R = 7 = R = 6 + "
        f"one block; detector coordinates complete (both bases) => weight-11 logicals span <= 11 rounds, R <= 13 suffices")
    return int(bad)


if __name__ == "__main__":
    mode = sys.argv[1]
    sys.exit(jobs() if mode == "jobs" else lists() if mode == "list" else check(int(sys.argv[2])))
