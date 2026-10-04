"""E-006 (a) analysis: per tag, LER (per shot, P_any = either sector fails) for every decoder and the exact MLE
reference, with the reference estimated by Horvitz-Thompson (ref run on all shots where BP-OSD or Relay-BP-5 failed,
plus a random subsample of rate `sub` of the others). Ratio CIs: shot bootstrap (2000 resamples, percentile 95%).

uv run python -m search.decoders.analyze_direct [tag ...]   -> results/E-006-decoder-headroom/direct/summary.json
"""
from __future__ import annotations

import json
import sys

import numpy as np

from search.decoders.common import RESULTS

DIR = RESULTS / "direct"


def load(tag):
    d = DIR / tag
    args = json.loads((d / "args.json").read_text())
    files = sorted(d.glob("batch_*.npz"))
    recs = [dict(np.load(f)) for f in files]
    for r in recs:   # per-batch subsample rate (older batches: args.json value)
        r["sub_b"] = np.full(len(r["nfaults"]), float(r.get("sub", args["sub"])))
    keys = [k for k in recs[0] if k not in ("stim_seed", "cpu", "timing", "sub")]
    R = {k: np.concatenate([r[k] for r in recs]) for k in keys}
    R["cpu_total"] = float(sum(float(r["cpu"]) for r in recs))
    R["timing"] = [json.loads(str(r["timing"])) for r in recs]
    return args, R


def decoders_in(R):
    return sorted({k.split("_")[1] for k in R if k.startswith("Z_") and k.endswith("_fail")} - {"ref", "pm"})


def summarize(tag, nboot=2000, seed=0):
    args, R = load(tag)
    N = len(R["nfaults"])
    sub = args["sub"]
    decs = decoders_in(R)
    fany = {n: R[f"Z_{n}_fail"] | R[f"X_{n}_fail"] for n in decs}
    sure = np.zeros(N, bool)
    for n in ("bposd", "relay5"):
        if n in fany:
            sure |= fany[n]
    assert R["ref_done"][sure].all()
    w = np.where(sure, 1.0, np.where(R["ref_done"], 1.0 / R["sub_b"], 0.0))
    ref_any = R["Z_ref_fail"] | R["X_ref_fail"]
    st = np.concatenate([R["Z_ref_status"][R["ref_done"]], R["X_ref_status"][R["ref_done"]]])
    out = {"tag": tag, "args": args, "shots": N, "cpu_hours": R["cpu_total"] / 3600,
           "mean_faults": float(R["nfaults"].mean()),
           "ref_solves": int(R["ref_done"].sum()) * 2,
           "ref_status": {"optimal": int((st == 1).sum()), "feasible_timeout": int((st == 2).sum()),
                          "failed": int((st == 3).sum())},
           "ref_seconds": {"mean": float(np.mean(np.concatenate([R["Z_ref_sec"][R["ref_done"]],
                                                               R["X_ref_sec"][R["ref_done"]]]))),
                           "max": float(np.max(np.concatenate([R["Z_ref_sec"], R["X_ref_sec"]])))}}
    ler = {n: int(fany[n].sum()) for n in decs}
    if "Z_pm_fail" in R:
        fany["pm"] = R["Z_pm_fail"] | R["X_pm_fail"]
        ler["pm"] = int(fany["pm"].sum())
    out["fails"] = ler
    ref_ht = float((w * ref_any).sum())
    out["ref_fails_HT"] = ref_ht
    out["ref_fails_raw"] = {"in_sure": int(ref_any[sure].sum()),
                            "in_subsample_not_sure": int(ref_any[~sure & R["ref_done"]].sum()),
                            "subsample_not_sure_size": int((~sure & R["ref_done"]).sum())}
    # ties: ref fails with W_ref == W_true (to 1e-6) in a sector
    tie = np.zeros(N, bool)
    for s in "ZX":
        tie |= R[f"{s}_ref_fail"] & (np.abs(R[f"{s}_ref_W"] - R[f"{s}_Wtrue"]) < 1e-6)
    out["ref_fail_ties_HT"] = float((w * (ref_any & tie)).sum())
    # MILP timeouts (status 2: best feasible solution, optimality not proven): bracket the reference
    to = {sct: R[f"{sct}_ref_status"] == 2 for sct in "ZX"}
    any_hi = (R["Z_ref_fail"] | to["Z"]) | (R["X_ref_fail"] | to["X"])
    any_lo = (R["Z_ref_fail"] & ~to["Z"]) | (R["X_ref_fail"] & ~to["X"])
    out["ref_timeouts_shots"] = int((to["Z"] | to["X"]).sum())
    out["ref_fails_HT_bracket"] = [float((w * any_lo).sum()), float((w * any_hi).sum())]
    out["LER"] = {n: v / N for n, v in ler.items()}
    out["LER"]["ref"] = ref_ht / N
    # decomposition of each decoder's failures (sector level, only on shots where ref ran: all D-failures for
    # bposd/relay5; others only partially)
    dec = {}
    for n in decs:
        dd = {}
        for s in "ZX":
            fD = R[f"{s}_{n}_fail"] & R["ref_done"]
            fr = R[f"{s}_ref_fail"]
            dd[s] = {"D_fail_with_ref": int(fD.sum()),
                     "ref_also_fails": int((fD & fr).sum()),
                     "ref_succeeds": int((fD & ~fr).sum()),
                     "audit_criterion_W_D_gt_W_true": int((fD & (R[f"{s}_{n}_W"] > R[f"{s}_Wtrue"] + 1e-9)).sum()),
                     "D_fail_total": int(R[f"{s}_{n}_fail"].sum())}
        dec[n] = dd
    out["decomposition"] = dec
    # bootstrap ratios
    rng = np.random.default_rng(seed)
    boots = {n: [] for n in fany}
    for _ in range(nboot):
        idx = rng.integers(0, N, N)
        rr = (w[idx] * ref_any[idx]).sum()
        for n in fany:
            boots[n].append(fany[n][idx].sum() / rr if rr > 0 else np.inf)
    out["ratio_D_over_ref"] = {}
    for n in fany:
        b = np.array(boots[n])
        out["ratio_D_over_ref"][n] = {"best": ler[n] / ref_ht if ref_ht > 0 else None,
                                      "ci95": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]}
    out["ratio_D_over_ref_bracket"] = {n: [ler[n] / out["ref_fails_HT_bracket"][1],
                                           (ler[n] / out["ref_fails_HT_bracket"][0]
                                            if out["ref_fails_HT_bracket"][0] > 0 else None)] for n in fany}
    # relay vs bposd directly (paired)
    if "relay5" in fany and "bposd" in fany:
        b = []
        for _ in range(nboot):
            idx = rng.integers(0, N, N)
            r5 = fany["relay5"][idx].sum()
            b.append(fany["bposd"][idx].sum() / r5 if r5 else np.inf)
        out["ratio_bposd_over_relay5"] = {"best": ler["bposd"] / max(ler["relay5"], 1e-300),
                                          "ci95": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]}
    # decoder CPU
    tot = {}
    for t in R["timing"]:
        for k, v in t.items():
            tot[k] = tot.get(k, 0.0) + v
    out["cpu_seconds_by_decoder"] = tot
    return out


def main():
    tags = sys.argv[1:] or sorted(p.name for p in DIR.iterdir() if p.is_dir() and not p.name.startswith("test"))
    allres = {}
    path = DIR / "summary.json"
    if path.exists():
        allres = json.loads(path.read_text())
    for t in tags:
        try:
            allres[t] = summarize(t)
        except Exception as e:  # noqa: BLE001
            print("skip", t, e)
            continue
        r = allres[t]
        print(t, "shots", r["shots"], "cpu_h %.2f" % r["cpu_hours"], "fails", r["fails"],
              "ref_HT %.1f (ties %.1f)" % (r["ref_fails_HT"], r["ref_fail_ties_HT"]),
              {n: (None if v["best"] is None else round(v["best"], 2), [round(x, 2) for x in v["ci95"]])
               for n, v in r["ratio_D_over_ref"].items()}, r["ref_status"])
    path.write_text(json.dumps(allres, indent=1))


if __name__ == "__main__":
    main()
