"""Analyse joint_sample / trim_sample outputs: per decoder, per-round rates, Strikis/IBM ratios with bootstrap CIs,
true joint P_any vs independence approximation.

uv run python analyze_joint.py noisy_p0.005 [trim_p0.005]
"""
import json
import sys

import numpy as np

from common import OUT

pr = lambda P, n=12: 1 - (1 - P) ** (1 / n)  # noqa: E731
rng = np.random.default_rng(0)
B = 4000


def boot_ratio(a, b, f):
    """bootstrap ratio f(a)/f(b), a and b arrays resampled independently along axis 0."""
    na, nb = len(a), len(b)
    r = []
    for _ in range(B):
        ia = rng.integers(0, na, na); ib = rng.integers(0, nb, nb)
        fb = f(b[ib])
        r.append(f(a[ia]) / fb if fb > 0 else np.inf)
    return np.percentile(r, [2.5, 97.5]).round(3).tolist()


def joint(tag):
    d = OUT / tag
    meta = json.loads((d / "meta.json").read_text())
    decs = sorted({k.split("_")[-1] for k in meta.get("decode", {})})
    out = {}
    for dec in decs:
        row = {}
        F = {}
        for s in ("strikis", "ibm"):
            try:
                fz = np.load(d / f"fails_{s}_Z_{dec}.npy"); fx = np.load(d / f"fails_{s}_X_{dec}.npy")
            except FileNotFoundError:
                break
            F[s] = np.stack([fz, fx], 1)
            Pz, Px = fz.mean(), fx.mean()
            Pany = (fz | fx).mean(); Pboth = (fz & fx).mean()
            Pind = 1 - (1 - Pz) * (1 - Px)
            row[s] = {"n": len(fz), "fail_Z": int(fz.sum()), "fail_X": int(fx.sum()), "fail_any": int((fz | fx).sum()),
                      "fail_both": int((fz & fx).sum()), "pr_Z": pr(Pz), "pr_X": pr(Px), "pr_any_joint": pr(Pany),
                      "pr_indep_approx": pr(Pind), "indep_over_joint": pr(Pind) / pr(Pany) if Pany else None,
                      "P_both_obs": Pboth, "P_both_if_indep": Pz * Px}
        if len(F) == 2:
            a, b = F["strikis"], F["ibm"]
            row["ratio"] = {
                "Z": pr(a[:, 0].mean()) / pr(b[:, 0].mean()),
                "X": pr(a[:, 1].mean()) / pr(b[:, 1].mean()),
                "any_joint": pr(a.any(1).mean()) / pr(b.any(1).mean()),
                "indep_approx": row["strikis"]["pr_indep_approx"] / row["ibm"]["pr_indep_approx"],
                "any_joint_ci95_boot": boot_ratio(a, b, lambda x: pr(x.any(1).mean())),
            }
        out[dec] = row
        print(tag, dec, json.dumps(row, default=float))
    return out


def trimmed(tag):
    d = OUT / tag
    meta = json.loads((d / "meta.json").read_text())
    decs = sorted({k.split("_")[-1] for k in meta.get("decode", {})})
    out = {}
    for dec in decs:
        f = {nm: np.load(d / f"fails_{nm}_Z_{dec}.npy") for nm in ("strikisZ", "strikisX", "ibmZ", "ibmX")}
        row = {nm: {"fails": int(v.sum()), "n": len(v), "pr": pr(v.mean())} for nm, v in f.items()}
        comb = lambda z, x: 1 - (1 - z.mean()) * (1 - x.mean())  # noqa: E731
        cs, ci = comb(f["strikisZ"], f["strikisX"]), comb(f["ibmZ"], f["ibmX"])
        row["ratio_Z"] = row["strikisZ"]["pr"] / row["ibmZ"]["pr"]
        row["ratio_X"] = row["strikisX"]["pr"] / row["ibmX"]["pr"]
        row["ratio_indep_comb"] = pr(cs) / pr(ci)
        # bootstrap of combined ratio
        rs = []
        for _ in range(B):
            g = {k: v[rng.integers(0, len(v), len(v))] for k, v in f.items()}
            rs.append(pr(comb(g["strikisZ"], g["strikisX"])) / pr(comb(g["ibmZ"], g["ibmX"])))
        row["ratio_indep_comb_ci95_boot"] = np.percentile(rs, [2.5, 97.5]).round(3).tolist()
        out[dec] = row
        print(tag, dec, json.dumps(row, default=float))
    return out


if __name__ == "__main__":
    res = {}
    for tag in sys.argv[1:]:
        res[tag] = trimmed(tag) if tag.startswith("trim") else joint(tag)
    (OUT / "analysis.json").write_text(json.dumps(res, indent=1, default=float))
