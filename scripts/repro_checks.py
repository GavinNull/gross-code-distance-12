"""PASS/FAIL checks for the morphing sections of scripts/reproduce_theorems.sh.

    uv run python scripts/repro_checks.py e017fold DIR          # auditor's c2/c3 JSONs (E-017 fold premise etc.)
    uv run python scripts/repro_checks.py e019 DIR KEY [KEY ...] # experimenter's solve_<key>_<b>_T4.json (E-019)

Expected E-019 values are the audited ones (research/audits/2026-10-08-E-019.md, research/STATE.md item 8).
Exit code 1 if any check fails.
"""
import glob
import json
import os
import sys


def e017fold(d):
    bad = 0
    for p in sorted(glob.glob(f"{d}/c3_*.json")):
        tag = os.path.basename(p)[3:-5]
        c3 = json.load(open(p))
        c2 = json.load(open(f"{d}/c2_{tag}.json"))
        T = int(tag.split("_T")[1])
        errs = []
        if not (c2["stim_eq_mine"] and c2["locality_violations"] == 0 and c2["blocks_span_Kdet"]):
            errs.append("c2 (stim DEM = own faults / locality / detector blocks)")
        if c3["K_circuit_automorphisms"] != 72 or c3["nonK_automorphisms"]:
            errs.append("translation symmetry")
        if not all(v["ok"] and v["comp_bijective"] for v in c3["round_isomorphisms"].values()):
            errs.append("round instances not equivalent")
        if any(v["mirror_not_a_fault"] for v in c3["mirror"].values()):
            errs.append("mirror of a fault is not a fault")
        rs = [str(r) for r in range(2, T + 1)]
        if not all(c3["mirror_general"][r]["fold_ok"] for r in rs):
            errs.append("general fold condition")
        if not all(c3["mirror_local"][r]["fold_ok"] for r in rs):
            errs.append("local fold condition")
        s = c3["sym_round1"]
        if not (s["ok"] and s["n_perms"] == 72 and s["n_orbits"] == 12):
            errs.append("round-1 symmetry")
        if errs:
            bad = 1
            print(f"FAIL  e017_fold_{tag}: " + ", ".join(errs))
        else:
            print(f"PASS  e017_fold_{tag}: stim DEM = fault list ({c2['stim_terms']} terms), rounds 1..{T} equivalent, "
                  f"general + local fold condition r = 2..{T}, 72 translations / 12 orbits")
    return bad


# audited d_end (end-cycle distance) and d_circ per circuit
TEN = {"x_sw11", "x_swap2", "xy_sw01", "xy_sw10", "y_sw11", "y_swap2"}


def expected(key):
    code, hom, var = key.split("_")
    hv = f"{hom}_{var}"
    if code == "bb72":
        d = 4 if hv in {"x_sw01", "x_sw10", "xy_sw11", "xy_swap2", "y_sw01", "y_sw10"} else 3
        return d, d
    if code == "bb108":
        de = 7 if var in {"sw01", "sw11"} else 8
        return de, 6 if var in {"paper", "std01"} else 7
    if code == "bb144":
        de = {"x_sw01": 8, "x_sw10": 8, "y_sw01": 7, "y_sw10": 7, "y_swap2": 5, "xy_sw10": 5}.get(hv, 6)
        return de, 6 if hv in {"x_sw01", "x_sw10"} else de
    if code == "bb288":
        d = 10 if hv in TEN else 12
        return d, d
    raise KeyError(key)


def e019(d, keys):
    bad = 0
    for key in keys:
        de, dc = expected(key)
        errs, info = [], []
        for b in "ZX":
            p = f"{d}/solve_{key}_{b}_T4.json"
            if not os.path.exists(p):
                errs.append(f"{b}: no result")
                continue
            r = json.load(open(p))
            ch = r["checks"]
            if not (ch["stim_eq_mine"] and ch["locality_violations"] == 0 and ch["weight1_logicals"] == 0
                    and ch["all_rounds_equivalent"] and ch["fold_ok"]):
                errs.append(f"{b}: instance checks {ch}")
            if r["d_end"] != de:
                errs.append(f"{b}: d_end {r['d_end']} != {de}")
            if r.get("d_circ") != dc or not str(r.get("status", "")).startswith("exact"):
                errs.append(f"{b}: d_circ {r.get('d_circ')} ({r.get('status')}) != {dc}")
            ex = [x for x in r["runs"] if x.get("exhaustive")]
            if not ex or ex[-1]["found"] != 0 or ex[-1]["W"] != dc - 1:
                errs.append(f"{b}: no complete W = {dc - 1} search with 0 solutions")
            inj = r["injections"]
            if "dfs_witness" in inj and not inj["dfs_witness"]["ok"]:
                errs.append(f"{b}: DFS witness injection failed")
            if not all(e["ok"] for e in inj["end_cycle_logical"]):
                errs.append(f"{b}: end-cycle logical injection failed")
            wit = inj.get("dfs_witness", {}).get("weight")
            info.append(f"{b} {r.get('d_circ')}" + (f" (wit {wit})" if wit else ""))
        lt = " < d~" if dc < de else ""
        if errs:
            bad = 1
            print(f"FAIL  e019 {key}: " + "; ".join(errs))
        else:
            print(f"PASS  e019 {key}: d_circ = {dc}{lt} (d~ = {de}); " + ", ".join(info) +
                  f"; exhaustive W = {dc - 1}: 0; witness/end-cycle injections ok; fold ok")
    return bad


if __name__ == "__main__":
    mode, d = sys.argv[1], sys.argv[2]
    sys.exit(e017fold(d) if mode == "e017fold" else e019(d, sys.argv[3:]))
