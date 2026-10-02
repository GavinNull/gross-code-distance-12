"""Pilot screen of weight-6 BB codes with n <= n_max (tool-chain validation, NOT a formal experiment).

    uv run python -m search.codes.pilot --n-max 150 --out results/codes-screen-pilot --workers 3 \
        --time-cap 3600 --seed 0

Stages
  0  enumerate the "ibm" family on every (l, m), l >= m >= 2, 2lm <= n_max; de-duplicate by canonical
     key (search.codes.equivalence); for each class compute k (GF(2) rank) and Tanner connectivity.
     Optionally (--general-samples S) add S random translation-normalised general trinomial pairs per
     group (including cyclic Z_N), de-duplicated against everything else.
  1  classes with k > 0 and connected Tanner graph: S1 BP-OSD trials -> d upper bound.
  2  top N2 by k*d_ub^2/n: S2 more trials (the bound only decreases).
  3  top N3: S3 more trials, then exact MILP (time-limited) for every code -> exact or [lower, upper].
  final: top 20 by k d^2 / n (d = exact value when proved, else best upper bound), plus thickness,
     default-schedule check and literature matching.
"""
from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
import csv
import json
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from search.codes.catalog import all_known_codes, known_params
from search.codes.constraints import is_connected, thickness_le2
from search.codes.construct import GroupAlgebraCode
from search.codes.distance import distance_exact_milp, distance_upper_bound_bposd
from search.codes.enumerate import bb_shapes, ibm_family
from search.codes.equivalence import canonical_key, canonical_key_abelian
from search.codes.groups import abelian_group
from search.codes.screen import merits

RESULTS = Path(__file__).resolve().parents[2] / "results"


def _stage0_shape(args):
    l, m, family, samples, seed = args
    G = abelian_group(l, m)
    seen = {}
    if family == "ibm":
        it = ibm_family(l, m)
    else:
        rng = np.random.default_rng(seed + 1000 * l + m)
        N = l * m

        def gen():
            for _ in range(samples):
                a = rng.choice(np.arange(1, N), 2, replace=False)
                b = rng.choice(np.arange(1, N), 2, replace=False)
                yield (0, int(a[0]), int(a[1])), (0, int(b[0]), int(b[1]))
        it = gen()
    total = 0
    for A, B in it:
        total += 1
        key = canonical_key_abelian(l, m, A, B)
        if key in seen:
            continue
        seen[key] = (l, m, A, B)
    out = []
    for key, (l_, m_, A, B) in seen.items():
        c = GroupAlgebraCode(G, A, B, family="BB")
        k = c.k
        conn = is_connected(c) if k > 0 else None
        out.append((key, l_, m_, A, B, k, conn))
    return (l, m, family, total, out)


def _code(rec):
    return GroupAlgebraCode(abelian_group(rec["l"], rec["m"]), tuple(rec["a_idx"]), tuple(rec["b_idx"]),
                            family="BB")


def _bposd_job(args):
    rec, trials, budget, seed = args
    c = _code(rec)
    ub = distance_upper_bound_bposd(c.to_css(), trials=trials, time_budget=budget, seed=seed,
                                    symmetric=True, osd_order=7)
    return rec["key"], ub["d_ub"], ub.get("Z_trials", 0)


def _milp_job(args):
    rec, upper, tl = args
    c = _code(rec)
    ex = distance_exact_milp(c.to_css(), time_limit=tl, upper=upper, symmetric=True, translation_n2=c.n2)
    return rec["key"], ex["d_lower"], ex["d_upper"], ex["exact"], ex["seconds"]


def _score(rec):
    return merits(rec["n"], rec["k"], rec["d"])["kd2_n"]


def _update_ub(recs, results):
    for key, d, t in results:
        r = recs[key]
        if d is not None and (r["d"] is None or d < r["d"]):
            r["d"] = d
        r["bposd_trials"] = r.get("bposd_trials", 0) + t


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-max", type=int, default=150)
    ap.add_argument("--out", default=str(RESULTS / "codes-screen-pilot"))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--time-cap", type=float, default=3600.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--s1", type=int, default=12)
    ap.add_argument("--n2", type=int, default=400)
    ap.add_argument("--s2", type=int, default=200)
    ap.add_argument("--n3", type=int, default=40)
    ap.add_argument("--s3", type=int, default=1000)
    ap.add_argument("--milp-time", type=float, default=300.0)
    ap.add_argument("--general-samples", type=int, default=0)
    ap.add_argument("--top", type=int, default=20)
    a = ap.parse_args(argv)
    assert a.workers <= 3, "CPU policy: at most 3 workers"
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    T0 = time.time()
    log = {"args": vars(a), "stages": {}}

    def left():
        return a.time_cap - (time.time() - T0)

    # ---------------------------------------------------------------- stage 0
    shapes = bb_shapes(a.n_max, min_side=2, l_ge_m=True)
    jobs = [(l, m, "ibm", 0, a.seed) for l, m in shapes]
    if a.general_samples:
        gshapes = bb_shapes(a.n_max, min_side=1, l_ge_m=True)
        jobs += [(l, m, "general", a.general_samples, a.seed) for l, m in gshapes if l * m >= 4]
    jobs.sort(key=lambda j: -j[0] * j[1])
    recs: dict = {}
    enumerated = 0
    per_shape = []
    with Pool(a.workers) as pool:
        for l, m, fam, total, res in pool.imap_unordered(_stage0_shape, jobs):
            enumerated += total
            new = 0
            for key, l_, m_, A, B, k, conn in res:
                ks = str(key)
                if ks in recs:
                    recs[ks]["families"].add(fam)
                    continue
                new += 1
                recs[ks] = {"key": ks, "l": l_, "m": m_, "a_idx": list(A), "b_idx": list(B), "n": 2 * l_ * m_,
                            "k": k, "connected": conn, "d": None, "families": {fam}}
            per_shape.append({"l": l, "m": m, "family": fam, "enumerated": total, "classes": len(res),
                              "new_classes": new})
    n_cls = len(recs)
    cand = [r for r in recs.values() if r["k"] > 0 and r["connected"]]
    log["stages"]["0"] = {"enumerated": enumerated, "classes": n_cls,
                          "classes_k_pos": sum(1 for r in recs.values() if r["k"] > 0),
                          "classes_k_pos_connected": len(cand), "seconds": round(time.time() - T0, 1)}
    print("stage0", log["stages"]["0"], flush=True)

    # ---------------------------------------------------------------- stage 1-3 BP-OSD
    def bposd_round(sel, trials, per_code_budget, tag):
        t = time.time()
        jobs = [(r, trials, per_code_budget, a.seed + 7919 * i) for i, r in enumerate(sel)]
        with Pool(a.workers) as pool:
            res = []
            for x in pool.imap_unordered(_bposd_job, jobs, chunksize=8):
                res.append(x)
                if left() < 0:
                    pool.terminate()
                    break
        _update_ub(recs, res)
        log["stages"][tag] = {"codes": len(sel), "done": len(res), "trials_each": trials,
                              "seconds": round(time.time() - t, 1)}
        print(tag, log["stages"][tag], flush=True)

    bposd_round(cand, a.s1, 2.0, "1")
    ranked = sorted((r for r in cand if r["d"]), key=lambda r: (-_score(r), r["n"]))
    sel2 = ranked[:a.n2]
    bposd_round(sel2, a.s2, 20.0, "2")
    ranked = sorted((r for r in cand if r["d"]), key=lambda r: (-_score(r), r["n"]))
    sel3 = ranked[:a.n3]
    bposd_round(sel3, a.s3, 60.0, "3")
    for r in sel3:
        r["d_ub_bposd"] = r["d"]

    # ---------------------------------------------------------------- stage 3 MILP
    t = time.time()
    sel3 = sorted(sel3, key=lambda r: (-_score(r), r["n"]))
    jobs = [(r, r["d"], min(a.milp_time, max(5.0, left() / 2))) for r in sel3]
    milp_res = []
    with Pool(a.workers) as pool:
        for x in pool.imap_unordered(_milp_job, jobs):
            milp_res.append(x)
    for key, lo, hi, exact, secs in milp_res:
        r = recs[key]
        r["d_lower"], r["d"], r["d_kind"], r["milp_seconds"] = lo, hi, ("exact" if exact else "upper"), round(secs, 1)
    log["stages"]["3_milp"] = {"codes": len(jobs), "exact": sum(1 for x in milp_res if x[3]),
                               "seconds": round(time.time() - t, 1)}
    print("milp", log["stages"]["3_milp"], flush=True)

    # ---------------------------------------------------------------- final
    for r in recs.values():
        r.setdefault("d_kind", "upper")
    final = sorted(sel3, key=lambda r: (-_score(r), r["n"]))[:a.top]
    known = {str(canonical_key(c)): row[0] for row, c in all_known_codes()}
    kp = known_params()
    from search.codes.schedule import check_schedule, default_schedule
    rows = []
    for rank_, r in enumerate(final, 1):
        c = _code(r)
        th = thickness_le2(c)
        sch = check_schedule(c, default_schedule(c), rounds=(1, 2), shots=8)
        same = [s for (n, k, d, s) in kp if (n, k, d) == (r["n"], r["k"], r["d"])]
        dominates_gross = (r["k"] >= 12 and r["d"] >= 12 and r["n"] <= 144 and
                           (r["k"], r["d"], -r["n"]) != (12, 12, -144))
        row = {"rank": rank_, "n": r["n"], "k": r["k"], "d": r["d"], "d_kind": r["d_kind"],
               "d_lower": r.get("d_lower"), "d_ub_bposd": r.get("d_ub_bposd"),
               "kd2_n": round(_score(r), 3), "l": r["l"], "m": r["m"], "A": c.poly("A"), "B": c.poly("B"),
               "family": "+".join(sorted(r["families"])), "bposd_trials": r.get("bposd_trials"),
               "milp_seconds": r.get("milp_seconds"), "thickness": th["status"],
               "thickness_split": th["split_terms"], "ibm_schedule_deterministic": sch["deterministic"],
               "known_code_equivalent": known.get(r["key"], ""), "same_params_as": "; ".join(same),
               "gross_or_better_not_in_ibm_table3": bool(r["k"] * r["d"] ** 2 / r["n"] >= 12 and
                                                          not known.get(r["key"], "").startswith("[[")),
               "dominates_gross_nkd": dominates_gross, "key": r["key"]}
        rows.append(row)
    with open(out / "top20.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(out / "top20_polynomials.txt", "w") as f:
        for row in rows:
            f.write(f"#{row['rank']} [[{row['n']},{row['k']},{row['d']}]] ({row['d_kind']}) l={row['l']} m={row['m']}\n"
                    f"   A = {row['A']}\n   B = {row['B']}\n   known: {row['known_code_equivalent'] or '-'}"
                    f" | same (n,k,d) as: {row['same_params_as'] or '-'}\n")
    # all stage-1 classes (compact)
    with open(out / "all_classes_kpos.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["n", "k", "d_ub", "kd2_n_ub", "l", "m", "a_idx", "b_idx", "families", "key"])
        for r in sorted(cand, key=lambda r: (-_score(r) if r["d"] else 0, r["n"])):
            w.writerow([r["n"], r["k"], r["d"], round(_score(r), 3) if r["d"] else "", r["l"], r["m"],
                        " ".join(map(str, r["a_idx"])), " ".join(map(str, r["b_idx"])),
                        "+".join(sorted(r["families"])), r["key"]])
    log["per_shape"] = per_shape
    log["total_seconds"] = round(time.time() - T0, 1)
    with open(out / "run_log.json", "w") as f:
        json.dump(log, f, indent=1, default=str)
    print(json.dumps({k: v for k, v in log.items() if k != "per_shape"}, indent=1, default=str))
    for row in rows:
        print(row["rank"], f"[[{row['n']},{row['k']},{row['d']}]]", row["d_kind"], row["kd2_n"], row["l"], row["m"],
              row["A"], "|", row["B"], row["known_code_equivalent"], row["same_params_as"], row["thickness"],
              row["ibm_schedule_deterministic"])


if __name__ == "__main__":
    main()
