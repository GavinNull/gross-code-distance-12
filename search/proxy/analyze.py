"""E-004 analysis: gold ranking, proxy rankings, Spearman with bootstrap intervals, costs.

  PYTHONPATH=. uv run python -m search.proxy.analyze

Reads results/E-004-proxy-fidelity/{l2,distance}/*.json; writes summary.json, gold.csv, proxies.csv, spearman.csv.

Conventions
  B (H-003 metric B) = per-round P_any / k, per-round = 1-(1-P)^(1/rounds) (arXiv:2308.07915 Sec. 3).
  Gold-paper:  full E-002 decoder, rounds = d, boundary="paper", seed 1.
  Gold-diff:   rounds-difference bulk rate from the rounds = d run (seed 1) and a rounds = d/2 run (seed 2):
               1 - eps = ((1-P_d)/(1-P_{d/2}))^(1/(d - d/2)); B_diff = eps / k (P = P_any).
  Spearman is computed between proxy "goodness" (oriented so that larger = predicted better) and -B (larger = better),
  so +1 = perfect agreement.  Ties get average ranks.
  Bootstrap (2000 replicates, seed 0): each replicate resamples (i) batches within every L2 run (measurement noise,
  gold and stochastic proxies independently) and (ii) the candidate set with replacement; reported: point estimate,
  2.5/97.5 percentiles of (i) alone ("noise CI") and of (i)+(ii) ("full CI").
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

OUT = Path("results/E-004-proxy-fidelity")
RNG = np.random.default_rng(0)
NBOOT = 2000


def load_l2():
    runs = {}
    for f in sorted((OUT / "l2").glob("*.json")):
        if f.name.startswith("timing__"):
            continue
        d = json.loads(f.read_text())
        e = d["e004"]
        used = d["counts"]["batches_used"]
        pb = [b for b in e["per_batch"] if b["index"] < used]
        runs[e["tag"]] = {"cand": e["candidate"]["name"], "k": e["candidate"]["k"], "d": e["candidate"]["d"],
                          "rounds": e["rounds"], "decoder": e["decoder_preset"], "seed": d["inputs"]["seed"],
                          "shots": d["counts"]["shots"], "fail_Z": d["counts"]["fail_Z"],
                          "fail_X": d["counts"]["fail_X"], "fail_any": d["counts"]["fail_any"],
                          "batches": np.array([[b["shots"], b["fail_Z"], b["fail_X"], b["fail_any"]] for b in pb]),
                          "cpu_used": sum(b["cpu_s"] for b in pb), "cpu_all": e["cpu_s_all_batches"],
                          "cpu_per_shot": e["cpu_s_per_shot_used"], "meta": e["candidate"],
                          "rates": d["rates"], "per_round": d["per_round"]}
    return runs


def per_round(P, r):
    return 1 - (1 - P) ** (1 / r)


def B_from(b, k, r):
    s = b[:, 0].sum()
    return per_round(b[:, 3].sum() / s, r) / k


def Bdiff_from(bd, bh, k, d, h):
    Pd = bd[:, 3].sum() / bd[:, 0].sum()
    Ph = bh[:, 3].sum() / bh[:, 0].sum()
    ratio = (1 - Pd) / (1 - Ph)
    if ratio >= 1:
        return 1e-12  # unresolved (non-positive difference)
    return (1 - ratio ** (1 / (d - h))) / k


def resample(b):
    return b[RNG.integers(0, len(b), len(b))]


def prefix_until(b, min_sector):
    """Shortest batch prefix with >= min_sector failures in both sectors (all batches if never)."""
    cz = np.cumsum(b[:, 1]); cx = np.cumsum(b[:, 2])
    ok = np.nonzero((cz >= min_sector) & (cx >= min_sector))[0]
    return b[: ok[0] + 1] if len(ok) else b


def spearman(x, y):
    rx, ry = rankdata(x), rankdata(y)
    if np.std(rx) == 0 or np.std(ry) == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def main():
    runs = load_l2()
    gold = {r["cand"]: r for t, r in runs.items() if r["decoder"] == "full" and r["seed"] == 1 and r["rounds"] == r["d"]}
    half = {r["cand"]: r for t, r in runs.items() if r["decoder"] == "full" and r["seed"] == 2 and r["rounds"] == r["d"] // 2}
    cands = sorted(gold)
    # ------------------------------------------------------------------ gold table
    gold_rows = []
    for c in cands:
        g = gold[c]
        k, d = g["k"], g["d"]
        row = {"cand": c, "n": g["meta"]["n"], "k": k, "d": d, "Q": g["meta"]["Q"], "kd2_n": g["meta"]["kd2_n"],
               "pipelined": g["meta"]["pipelined"], "shots": g["shots"], "fail_Z": g["fail_Z"], "fail_X": g["fail_X"],
               "fail_any": g["fail_any"], "B_paper": B_from(g["batches"], k, d),
               "B_paper_LR_low": g["per_round"]["P_any"]["low"] / k, "B_paper_LR_high": g["per_round"]["P_any"]["high"] / k,
               "cpu_s": g["cpu_used"], "cpu_s_per_shot": g["cpu_per_shot"]}
        bs = [B_from(resample(g["batches"]), k, d) for _ in range(NBOOT)]
        row["B_paper_boot95"] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
        if c in half:
            h = half[c]
            row.update({"half_rounds": h["rounds"], "half_shots": h["shots"], "half_fail_Z": h["fail_Z"],
                        "half_fail_X": h["fail_X"], "half_fail_any": h["fail_any"], "half_cpu_s": h["cpu_used"]})
            row["B_diff"] = Bdiff_from(g["batches"], h["batches"], k, d, h["rounds"])
            from evaluators.l2 import diff_per_round   # public evaluator estimator (boundary="diff"), LR interval
            dd = diff_per_round(h["fail_any"], h["shots"], h["rounds"], g["fail_any"], g["shots"], d,
                                num_observables=2 * k)
            row["B_diff_evaluator"] = None if dd["best"] is None else dd["best"] / k
            row["B_diff_LR_low"] = None if dd["low"] is None else dd["low"] / k
            row["B_diff_LR_high"] = None if dd["high"] is None else dd["high"] / k
            bs = [Bdiff_from(resample(g["batches"]), resample(h["batches"]), k, d, h["rounds"]) for _ in range(NBOOT)]
            row["B_diff_boot95"] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
            row["B_half_paper"] = B_from(h["batches"], k, h["rounds"])
        gold_rows.append(row)
    have_diff = all("B_diff" in r for r in gold_rows)
    import os
    variant = os.environ.get("E004_MAIN", "diff")
    main_key = "B_diff" if (have_diff and variant == "diff") else "B_paper"
    if main_key == "B_paper" and variant == "paper":
        # paper boundary is not comparable between pipelined and non-pipelined circuits (evaluator_issues):
        # the paper-variant ranking excludes the pipelined candidate
        cands = [c for c in cands if not gold[c]["meta"]["pipelined"]]
        gold_rows = [r for r in gold_rows if r["cand"] in cands]
    suffix = "" if variant == "diff" else "_paper"
    order = sorted(gold_rows, key=lambda r: r[main_key])
    for i, r in enumerate(order):
        r["rank_main"] = i + 1
    # ------------------------------------------------------------------ proxies
    dist = {}
    for f in sorted((OUT / "distance").glob("*.json")):
        d = json.loads(f.read_text())
        dist[(d["cand"], d["budget"])] = d
    proxies = {}   # name -> {cand: (value or callable for bootstrap), cost}

    def det_proxy(name, fn, cost_fn=lambda c: 0.0, note=""):
        vals = {}
        for c in cands:
            try:
                v = fn(c)
            except KeyError:
                v = None
            if v is not None:
                vals[c] = v
        proxies[name] = {"kind": "det", "vals": vals, "cost": {c: cost_fn(c) for c in vals}, "note": note}

    meta = {c: gold[c]["meta"] for c in cands}
    det_proxy("code: k*d^2/n", lambda c: meta[c]["kd2_n"])
    det_proxy("code: d", lambda c: meta[c]["d"])
    det_proxy("code: -Q (Q=2n/k)", lambda c: -meta[c]["Q"])
    det_proxy("code: d - log10(n)  [d, tie-break small n]", lambda c: meta[c]["d"] - math.log10(meta[c]["n"]))
    for bud in ("low", "default"):
        det_proxy(f"d_circ ub ({bud}, 3 rounds)", lambda c, b=bud: dist[(c, b)]["d_circ_ub"],
                  lambda c, b=bud: dist[(c, b)]["cpu_s_total"])

        def wit(c, b=bud):
            dd = dist[(c, b)]
            w = dd["d_circ_ub"]
            # distinct BP-OSD solutions at weight <= w plus LNS chains ending at w (may repeat a solution)
            n = sum(x["n_bposd_solutions_le_w"] + x.get("lns_hits_at_w", 0) for x in dd["bases"].values()
                    if x["weight"] == w)
            return w - 0.01 * min(n, 99)   # lexicographic: higher d_circ first, then fewer witnesses at that weight
        det_proxy(f"d_circ ub + witness count ({bud})", wit, lambda c, b=bud: dist[(c, b)]["cpu_s_total"])

        def wit_kd(c, b=bud):   # circuit analogue of k d^2 / n
            dd = dist[(c, b)]
            return meta[c]["k"] * dd["d_circ_ub"] ** 2 / meta[c]["n"]
        det_proxy(f"k*d_circ^2/n ({bud})", wit_kd, lambda c, b=bud: dist[(c, b)]["cpu_s_total"])

    # stochastic proxies: cheap decoder runs (seed 3), at 50 and 30 failures/sector (prefix of the same run)
    decs = sorted({r["decoder"] for r in runs.values() if r["seed"] == 3})
    for dec in decs:
        rr = {r["cand"]: r for r in runs.values() if r["seed"] == 3 and r["decoder"] == dec and r["rounds"] == r["d"]}
        for nmin in (50, 30):
            bat = {c: prefix_until(rr[c]["batches"], nmin) for c in cands if c in rr}
            if any(min(b[:, 1].sum(), b[:, 2].sum()) < nmin and b[:, 0].sum() < 7999 for b in bat.values()):
                continue   # this run was stopped at a smaller failure target: level not available
            cost = {c: rr[c]["cpu_per_shot"] * bat[c][:, 0].sum() for c in bat}
            proxies[f"L2 {dec}, ~{nmin} fail/sector"] = {"kind": "l2", "batches": bat, "cost": cost,
                                                        "k": {c: meta[c]["k"] for c in bat},
                                                        "r": {c: rr[c]["rounds"] for c in bat}}
    # full decoder, few shots: disjoint split of the gold run (first batches until ~N fails) vs. the gold remainder
    for nmin in (50, 30):
        bat, rest = {}, {}
        for c in cands:
            b = gold[c]["batches"]
            p = prefix_until(b, nmin)
            bat[c] = p
            rest[c] = b[len(p):]
        proxies[f"L2 full decoder, ~{nmin} fail/sector (gold prefix; compared with disjoint remainder)"] = {
            "kind": "l2_split", "batches": bat, "rest": rest,
            "cost": {c: gold[c]["cpu_per_shot"] * bat[c][:, 0].sum() for c in cands},
            "k": {c: meta[c]["k"] for c in cands}, "r": {c: gold[c]["rounds"] for c in cands}}
    # gold reliability ceiling: first half of the gold batches vs. the disjoint second half (paper boundary)
    bat, rest = {}, {}
    for c in cands:
        b = gold[c]["batches"]
        bat[c], rest[c] = b[: len(b) // 2], b[len(b) // 2:]
    proxies["gold split-half: first half vs second half (reliability ceiling, paper B)"] = {
        "kind": "l2_split", "batches": bat, "rest": rest,
        "cost": {c: gold[c]["cpu_per_shot"] * bat[c][:, 0].sum() for c in cands},
        "k": {c: meta[c]["k"] for c in cands}, "r": {c: gold[c]["rounds"] for c in cands}}
    # paper-boundary gold itself as a "proxy" for the diff gold (and the d/2 run)
    if main_key == "B_diff":
        proxies["gold-paper (rounds d) vs gold-diff"] = {"kind": "l2_gold_paper", "cost": {c: gold[c]["cpu_used"] for c in cands}}

    # ------------------------------------------------------------------ Spearman + bootstrap
    def gold_vec(cs, boot):
        out = []
        for c in cs:
            g = gold[c]
            if main_key == "B_diff":
                h = half[c]
                gb = resample(g["batches"]) if boot else g["batches"]
                hb = resample(h["batches"]) if boot else h["batches"]
                out.append(-Bdiff_from(gb, hb, g["k"], g["d"], h["rounds"]))
            else:
                gb = resample(g["batches"]) if boot else g["batches"]
                out.append(-B_from(gb, g["k"], g["d"]))
        return np.array(out)

    def proxy_vec(name, cs, boot):
        P = proxies[name]
        if P["kind"] == "det":
            return np.array([P["vals"][c] for c in cs])
        if P["kind"] == "l2_gold_paper":
            return np.array([-B_from(resample(gold[c]["batches"]) if boot else gold[c]["batches"], gold[c]["k"], gold[c]["d"]) for c in cs])
        out = []
        for c in cs:
            b = P["batches"][c]
            b = resample(b) if boot else b
            out.append(-B_from(b, P["k"][c], P["r"][c]))
        return np.array(out)

    def gold_split_vec(name, cs, boot):
        P = proxies[name]
        out = []
        for c in cs:
            b = P["rest"][c]
            b = resample(b) if boot else b
            out.append(-B_from(b, gold[c]["k"], gold[c]["d"]))
        return np.array(out)

    subsets = {"all": cands, "gross [[144,12,12]] schedules only": [c for c in cands if c.startswith("G-")],
               "IBM schedule, different codes": [c for c in cands if c.endswith("-ibm")]}
    sp_rows = []
    for name, P in proxies.items():
        for sname, cs0 in subsets.items():
            cs = [c for c in cs0 if (P["kind"] not in ("det",) or c in P["vals"]) and
                  (P["kind"] not in ("l2", "l2_split") or c in P["batches"])]
            if len(cs) < 3:
                continue
            gv = gold_split_vec if P["kind"] == "l2_split" else (lambda n, cc, b: gold_vec(cc, b))
            if P["kind"] == "l2_gold_paper" and main_key != "B_diff":
                continue
            rho = spearman(proxy_vec(name, cs, False), gv(name, cs, False))
            noise, full = [], []
            for _ in range(NBOOT):
                noise.append(spearman(proxy_vec(name, cs, True), gv(name, cs, True)))
                idx = RNG.integers(0, len(cs), len(cs))
                cc = [cs[i] for i in idx]
                full.append(spearman(proxy_vec(name, cc, True), gv(name, cc, True)))
            noise = np.array([x for x in noise if not math.isnan(x)])
            full = np.array([x for x in full if not math.isnan(x)])
            costs = [P["cost"].get(c, float("nan")) for c in cs]
            gross_costs = [P["cost"][c] for c in cs if c.startswith("G-") and c in P["cost"]]
            sp_rows.append({"proxy": name, "subset": sname, "n_cand": len(cs), "spearman": rho,
                            "noise_ci95": [float(np.percentile(noise, 2.5)), float(np.percentile(noise, 97.5))] if len(noise) else None,
                            "full_ci95": [float(np.percentile(full, 2.5)), float(np.percentile(full, 97.5))] if len(full) else None,
                            "mean_cost_cpu_s": float(np.nanmean(costs)),
                            "mean_cost_cpu_s_gross": float(np.mean(gross_costs)) if gross_costs else None})
    # per-candidate proxy values (point estimates)
    prox_tab = []
    for c in cands:
        row = {"cand": c}
        for name, P in proxies.items():
            if P["kind"] == "det":
                row[name] = P["vals"].get(c)
            elif P["kind"] in ("l2", "l2_split"):
                if c in P["batches"]:
                    b = P["batches"][c]
                    row[name] = B_from(b, P["k"][c], P["r"][c])
                    row[name + " [shots]"] = int(b[:, 0].sum())
            row[name + " [cpu_s]"] = P["cost"].get(c)
        prox_tab.append(row)
    summary = {"main_metric": main_key, "gold": gold_rows, "spearman": sp_rows, "proxy_values": prox_tab,
               "nboot": NBOOT}
    (OUT / f"summary{suffix}.json").write_text(json.dumps(summary, indent=1, default=float))
    with open(OUT / f"gold{suffix}.csv", "w", newline="") as f:
        keys = sorted({k for r in gold_rows for k in r})
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in order:
            w.writerow(r)
    with open(OUT / f"spearman{suffix}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sp_rows[0]) if sp_rows else ["proxy"])
        w.writeheader()
        for r in sp_rows:
            w.writerow(r)
    with open(OUT / f"proxies{suffix}.csv", "w", newline="") as f:
        keys = ["cand"] + sorted({k for r in prox_tab for k in r} - {"cand"})
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in prox_tab:
            w.writerow(r)
    # print
    print(f"main metric: {main_key}")
    for r in order:
        s = f"{r['rank_main']:2d} {r['cand']:10s} Q={r['Q']:5.1f} d={r['d']:2d} shots={r['shots']:6d} fZ={r['fail_Z']:4d} fX={r['fail_X']:4d} " \
            f"B_paper={r['B_paper']:.3e} [{r['B_paper_boot95'][0]:.2e},{r['B_paper_boot95'][1]:.2e}]"
        if "B_diff" in r:
            s += f" B_diff={r['B_diff']:.3e} [{r['B_diff_boot95'][0]:.2e},{r['B_diff_boot95'][1]:.2e}]"
        print(s)
    for r in sp_rows:
        ci = r["full_ci95"] or [float("nan")] * 2; ni = r["noise_ci95"] or [float("nan")] * 2
        print(f"{r['proxy'][:70]:70s} | {r['subset'][:22]:22s} n={r['n_cand']:2d} rho={r['spearman']:+.2f} "
              f"noise[{ni[0]:+.2f},{ni[1]:+.2f}] full[{ci[0]:+.2f},{ci[1]:+.2f}] cost={r['mean_cost_cpu_s']:.0f}s")


if __name__ == "__main__":
    main()
