"""E-006 (b) analysis: LER(p) = sum_w pi_w(p) f_w(p) for each decoder and the MLE reference.

f_w^D = failures / n_w (any sector).  f_w^ref: Horvitz-Thompson (ref ran on every sample where BP-OSD or Relay-BP-5
failed, and on a random subsample with rate sub of the rest).  pi_w exact (Poisson-binomial of the joint DEM priors).
Weights outside the sampled range: w < w_min contributes 0 (assumption, checked by method (c) / zero failures at
w_min); w > w_max is reported as a separate upper bound sum_{w>w_max} pi_w (f <= 1) and as a 'tail' added
with f_w = f_{w_max} (lower estimate) -- both listed.
CI: stratified bootstrap (resample within each w), 2000 resamples, percentile 95%.

uv run python -m search.decoders.analyze_fixedweight [tag ...]
"""
from __future__ import annotations

import json
import sys

import numpy as np

from search.decoders.common import RESULTS, build_model, weight_distribution

DIR = RESULTS / "fixedweight"


def load(tag):
    by_w = {}
    cpu = 0.0
    for f in sorted((DIR / tag).glob("w*_b*.npz")):
        d = dict(np.load(f))
        trig = str(d.pop("trigger")) if "trigger" in d else "bposd,relay5"
        d["sure"] = np.zeros(len(d["insub"]), bool)
        for nm in trig.split(","):
            d["sure"] |= d[f"Z_{nm}_fail"] | d[f"X_{nm}_fail"]
        cpu += float(d.pop("cpu"))
        w = int(d.pop("w"))
        sub = float(d.pop("sub"))
        d["wt"] = np.where(d["ref_done"] & ~d["insub"], 1.0, np.where(d["ref_done"], 1.0 / sub, 0.0))
        d["wt"] = np.where(d["sure"], 1.0, d["wt"])
        by_w.setdefault(w, []).append(d)
    out = {}
    for w, L in by_w.items():
        out[w] = {k: np.concatenate([x[k] for x in L]) for k in L[0]}
    return out, cpu


def decs(D):
    return sorted({k[2:-5] for k in D if k.startswith("Z_") and k.endswith("_fail")} - {"ref"})


def summarize(tag, nboot=2000, seed=1):
    code, p = tag.split("_p")[0], float(tag.split("_p")[1].split("_")[0])
    data, cpu = load(tag)
    ws = sorted(data)
    m = build_model(code, p)
    wmax_pi = max(ws) + 200
    pi = weight_distribution(m.priors, wmax_pi)
    names = decs(data[ws[0]])
    per_w = {}
    fails = {}
    for w in ws:
        D = data[w]
        n = len(D["insub"])
        # samples that triggered the reference with weight 1 (D-failure) were run with prob 1
        sure = D["sure"]
        assert D["ref_done"][sure].all()
        wt = np.where(sure, 1.0, D["wt"])
        fz = {nm: D[f"Z_{nm}_fail"] | D[f"X_{nm}_fail"] for nm in names}
        ref = D["Z_ref_fail"] | D["X_ref_fail"]
        fails[w] = (fz, ref, wt)
        row = {"n": n, "pi_w": float(pi[w])}
        for nm in names:
            row[nm] = int(fz[nm].sum())
        row["ref_HT"] = float((wt * ref).sum())
        row["ref_raw"] = int(ref.sum())
        # decoder fails where ref succeeds (strictly decoder-suboptimal), per decoder
        for nm in ("bposd", "relay5"):
            if nm in fz:
                row[f"{nm}_fail_ref_ok"] = int((fz[nm] & ~ref & D["ref_done"]).sum())
                row[f"{nm}_fail_ref_run"] = int((fz[nm] & D["ref_done"]).sum())
        st = np.concatenate([D["Z_ref_status"][D["ref_done"]], D["X_ref_status"][D["ref_done"]]])
        row["ref_nonoptimal"] = int((st != 1).sum())
        to = (D["Z_ref_status"] == 2) | (D["X_ref_status"] == 2)
        row["ref_HT_if_timeouts_fail"] = float((wt * (ref | to)).sum())
        ties = np.zeros(n, bool)
        for sct in "ZX":
            ties |= D[f"{sct}_ref_fail"] & (np.abs(D[f"{sct}_ref_W"] - D[f"{sct}_Wtrue"]) < 1e-6)
        row["ref_tie_fails_HT"] = float((wt * ties).sum())
        per_w[w] = row

    def ler(sel):
        res = {nm: 0.0 for nm in names + ["ref"]}
        for w in ws:
            fz, ref, wt = fails[w]
            idx = sel[w]
            n = len(idx)
            for nm in names:
                res[nm] += pi[w] * fz[nm][idx].mean()
            res["ref"] += pi[w] * (wt[idx] * ref[idx]).sum() / n
        return res

    base = ler({w: np.arange(len(fails[w][1])) for w in ws})
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(nboot):
        boots.append(ler({w: rng.integers(0, len(fails[w][1]), len(fails[w][1])) for w in ws}))
    tail_ub = float(pi[max(ws) + 1:].sum())
    tail_lo = {nm: float(pi[max(ws) + 1:].sum() * per_w[max(ws)][nm] / per_w[max(ws)]["n"]) for nm in names}
    tail_lo["ref"] = float(pi[max(ws) + 1:].sum() * per_w[max(ws)]["ref_HT"] / per_w[max(ws)]["n"])
    below = float(pi[:min(ws)].sum())
    out = {"tag": tag, "code": code, "p": p, "cpu_hours": cpu / 3600, "mean_faults": float(m.priors.sum()),
           "w_range": [min(ws), max(ws)], "pi_below_range": below, "pi_above_range": tail_ub,
           "per_w": {str(w): per_w[w] for w in ws}, "LER_in_range": base, "tail_lower_est": tail_lo}
    out["LER_total_est"] = {nm: base[nm] + tail_lo[nm] for nm in base}
    out["ratio"] = {}
    for nm in names:
        b = np.array([x[nm] / x["ref"] if x["ref"] > 0 else np.inf for x in boots])
        out["ratio"][nm] = {"best": base[nm] / base["ref"] if base["ref"] > 0 else None,
                            "ci95": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]}
    out["LER_ci95"] = {nm: [float(np.percentile([x[nm] for x in boots], 2.5)),
                            float(np.percentile([x[nm] for x in boots], 97.5))] for nm in base}
    if "bposd" in names and "relay5" in names:
        b = np.array([x["bposd"] / x["relay5"] if x["relay5"] > 0 else np.inf for x in boots])
        out["ratio_bposd_over_relay5"] = {"best": base["bposd"] / base["relay5"] if base["relay5"] else None,
                                          "ci95": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]}
    # dominant weights
    out["contrib_by_w"] = {nm: {str(w): float(pi[w] * (per_w[w][nm] if nm != "ref" else per_w[w]["ref_HT"])
                                         / per_w[w]["n"]) for w in ws} for nm in names + ["ref"]}
    return out


def main():
    tags = sys.argv[1:] or sorted(p.name for p in DIR.iterdir() if p.is_dir() and not p.name.startswith("test"))
    path = DIR / "summary.json"
    allres = json.loads(path.read_text()) if path.exists() else {}
    for t in tags:
        r = summarize(t)
        allres[t] = r
        print(t, "cpu %.2fh" % r["cpu_hours"], "LER", {k: "%.3g" % v for k, v in r["LER_total_est"].items()},
              "ratio", {k: (None if v["best"] is None else round(v["best"], 2), [round(x, 2) for x in v["ci95"]])
                        for k, v in r["ratio"].items()}, "pi_above %.2g" % r["pi_above_range"])
        for w, row in r["per_w"].items():
            print("  w", w, row)
    path.write_text(json.dumps(allres, indent=1))


if __name__ == "__main__":
    main()
