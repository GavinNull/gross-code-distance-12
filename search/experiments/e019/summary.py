"""E-019: collect per-circuit results into results/E-019-morphing-family/summary.{json,md}."""
from __future__ import annotations

import glob
import json
import os

RES = "/Users/ephemeral/Desktop/qec-ai-search/results/E-019-morphing-family"
NAMES = {"bb72": "[[72,12,6]]", "bb108": "[[108,8,10]]", "bb144": "[[144,12,12]]", "bb288": "[[288,12,18]]"}


def main():
    rows = []
    for f in sorted(glob.glob(f"{RES}/solve_*_T4.json")):
        s = json.load(open(f))
        tag = f"{s['key']}_{s['basis']}_T4"
        info = json.load(open(f"{RES}/inst/info_{tag}.json"))
        ec = json.load(open(f"{RES}/ec/dist_{s['key']}.json"))
        checks = dict(stim=info.get("stim_eq_mine"), loc=info["locality_violations"] == 0,
                      rounds=info["all_rounds_equivalent"], fold=info["fold_ok"], sym=info["sym_round1"]["ok"],
                      w1=info["weight1_logicals"] == 0)
        wit = s["injections"].get("dfs_witness", {})
        exh = [r for r in s["runs"] if r.get("exhaustive")]
        rows.append(dict(key=s["key"], basis=s["basis"], n_end=ec["n"], k=ec["k"], d_end=ec["d"],
                         d_circ=s.get("d_circ"), status=s["status"], checks=checks, all_checks=all(checks.values()),
                         witness_ok=wit.get("ok"), witness_weight=wit.get("weight"),
                         ec_inject_ok=all(e["ok"] for e in s["injections"]["end_cycle_logical"]),
                         exhaustive_W=[r["W"] for r in exh], nodes=sum(r["nodes"] for r in exh),
                         dfs_cpu_sec=s["dfs_cpu_sec"]))
    json.dump(rows, open(f"{RES}/summary.json", "w"), indent=1)
    # merge bases
    by = {}
    for r in rows:
        by.setdefault(r["key"], {})[r["basis"]] = r
    lines = ["| circuit | end-cycle | d_circ (Z mem / X mem) | status | checks | witness inj. | DFS CPU s |", "|---|---|---|---|---|---|---|"]
    for key in sorted(by, key=lambda k: (list(NAMES).index(k.split("_")[0]), k)):
        z, x = by[key].get("Z"), by[key].get("X")
        ref = z or x
        dz = z["d_circ"] if z else "-"
        dx = x["d_circ"] if x else "-"
        ok = all(r["all_checks"] for r in by[key].values())
        wok = all((r["witness_ok"] is not False) and r["ec_inject_ok"] for r in by[key].values())
        cpu = sum(r["dfs_cpu_sec"] for r in by[key].values())
        name, hom, v = key.split("_")
        flag = "" if min(r["d_circ"] or 0 for r in by[key].values()) == ref["d_end"] else " **<d**"
        lines.append(f"| {NAMES[name]} f_{hom} {v} | [[{ref['n_end']},{ref['k']},{ref['d_end']}]] | {dz} / {dx}{flag} | "
                     f"{'; '.join(sorted(set(r['status'] for r in by[key].values())))} | {'ok' if ok else 'FAIL'} | "
                     f"{'ok' if wok else 'FAIL'} | {cpu:.0f} |")
    open(f"{RES}/summary.md", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
