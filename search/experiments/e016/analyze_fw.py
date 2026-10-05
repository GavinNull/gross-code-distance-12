"""E-016：固定权重结果汇总与外推。experimenter。

对每个 (电路, 解码器)：各层 w 的样本数 n_w、失败数 k_w（任一 sector 失败），f_w = k_w / n_w；
MLE（分 sector 精确）用 Horvitz–Thompson：Σ_{运行了 MLE 的 sector} 1[失败] / pi，再 Z + X 相加（两 sector 同时失败极少，忽略）。
没有进入 MLE 的 sector（所有解码器都成功、且不在随机子样本里）按 MLE 成功处理，所以 MLE 的 f_w 偏低（下界）。

外推模型：cloglog(f_w) = a + b·log w（“失败 ⇔ 至少包含一个坏子组合”，坏子组合期望个数 ∝ w^b；--deg 2 加二次项），
按二项似然拟合所有测量层（含 0 失败层）。LER(p) = Σ_w π_w(p) f(w)，π_w 用该电路在 p 下的联合 DEM 精确计算。
区间：参数 bootstrap（k_w ~ Binomial(n_w, f_fit(w)) 重抽后重拟合，2000 次）；同时给出模型外推区（w 小于最小测量层）
在 LER 中所占的比例。比值 = IBM / 两色（每轮每逻辑比特）。

    PYTHONPATH=. uv run python -m search.experiments.e016.analyze_fw --prior 0.002
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict

import numpy as np
from scipy.optimize import minimize

from search.decoders.common import weight_distribution
from search.experiments.e016.common import CIRCS, OUT, build_model, per_round_per_logical

DECS = ("bposd", "relay_s", "relay_j", "mle")


def load(prior):
    d = OUT / "fw" / f"p{prior}"
    agg = defaultdict(lambda: defaultdict(lambda: {"n": 0, "k": 0.0, "cpu": 0.0, "mle_runs": 0, "mle_nonopt": 0,
                                                    "nonconv": 0}))
    cpu = 0.0
    for f in sorted(d.glob("*.npz")):
        if f.stem.endswith("_rj"):
            continue
        z = np.load(f)
        circ = f.name.split("_w")[0]
        w = int(z["w"])
        cpu += float(z["cpu"])
        n = int(z["n"])
        for dec in DECS[:3]:
            if f"{dec}_fZ" not in z.files:
                continue
            a = agg[(circ, dec)][w]
            a["n"] += n
            a["k"] += float((z[f"{dec}_fZ"] | z[f"{dec}_fX"]).sum())
            a["nonconv"] += int((~z[f"{dec}_conv"]).sum())
        frj = f.with_name(f.stem + "_rj.npz")
        if frj.exists():
            r = np.load(frj)
            cpu += float(r["cpu"])
            a = agg[(circ, "relay_j")][w]
            a["n"] += n
            fl = (r["rj_fZ"] | r["rj_fX"]) & r["rj_run"]
            a["k"] += float((fl / r["rj_pi"]).sum())
            a["k_raw"] = a.get("k_raw", 0) + int(fl.sum())
            a["nonconv"] += int((~r["rj_conv"]).sum())
        a = agg[(circ, "mle")][w]
        a["n"] += n
        for s in "ZX":
            run = z[f"mle_{s}_run"]
            pi = z[f"mle_{s}_pi"] if f"mle_{s}_pi" in z.files else np.ones(n)
            opt = z[f"mle_{s}_opt"]
            fl = z[f"mle_{s}_f"] & run & opt          # 只计证明最优的 MLE 失败；超时单独计
            a["k"] += float((fl / np.where(pi > 0, pi, 1)).sum())
            a["mle_fail_raw"] = a.get("mle_fail_raw", 0) + int(fl.sum())
            a["mle_timeout_fail"] = a.get("mle_timeout_fail", 0) + int((z[f"mle_{s}_f"] & run & ~opt).sum())
            a["mle_runs"] += int(run.sum())
            a["mle_nonopt"] += int((run & ~z[f"mle_{s}_opt"]).sum())
    return agg, cpu


DEG = 1
LW0 = np.log(40.0)


def _eta(th, w):
    lw = np.log(w) - LW0
    return sum(th[i] * lw ** i for i in range(len(th)))


def cloglog_fit(ws, ns, ks):
    ws, ns, ks = map(np.asarray, (ws, ns, ks))

    def nll(th):
        eta = _eta(th, ws)
        f = -np.expm1(-np.exp(np.clip(eta, -60, 5)))
        f = np.clip(f, 1e-300, 1 - 1e-15)
        return -(ks * np.log(f) + (ns - ks) * np.log1p(-f)).sum()

    best = None
    for b0 in (4.0, 8.0, 12.0):
        x0 = np.array([-3.0, b0] + [0.0] * (DEG - 1))
        r = minimize(nll, x0=x0, method="Nelder-Mead",
                     options={"xatol": 1e-6, "fatol": 1e-8, "maxiter": 8000})
        if best is None or r.fun < best.fun:
            best = r
    return best.x


def f_model(th, w):
    return -np.expm1(-np.exp(np.clip(_eta(th, np.asarray(w, float)), -60, 5)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--prior", type=float, default=0.002)
    ap.add_argument("--ps", default="0.001,0.0015,0.002,0.003,0.004")
    ap.add_argument("--nboot", type=int, default=2000)
    ap.add_argument("--deg", type=int, default=1, help="cloglog(f) 关于 log w 的多项式次数（1 = 幂律）")
    a = ap.parse_args(argv)
    global DEG
    DEG = a.deg
    agg, cpu = load(a.prior)
    ps = [float(x) for x in a.ps.split(",")]
    pis = {}
    for c in CIRCS:
        for p in ps:
            pis[(c, p)] = weight_distribution(build_model(c, p).priors, 200)
    rng = np.random.default_rng(1)
    out = {"cpu_s": round(cpu), "layers": {}, "fits": {}, "ler": {}}
    print(f"fixed-weight data, decoder priors p={a.prior}, cpu {cpu:.0f} s")
    for dec in DECS:
        fits = {}
        for c in CIRCS:
            L = agg.get((c, dec))
            if not L:
                continue
            ws = sorted(L)
            ns = [L[w]["n"] for w in ws]
            ks = [L[w]["k"] for w in ws]
            out["layers"][f"{c}/{dec}"] = {w: L[w] for w in ws}
            print(f"  {c:9s} {dec:8s} " + "  ".join(f"w{w}:{L[w]['k']:.1f}/{L[w]['n']}" for w in ws))
            if sum(ks) < 3:
                continue
            th = cloglog_fit(ws, ns, ks)
            boots = []
            for _ in range(a.nboot):
                kb = rng.binomial(np.array(ns), f_model(th, np.array(ws, float)))
                boots.append(cloglog_fit(ws, ns, kb) if kb.sum() > 0 else th)
            fits[c] = (th, np.array(boots), min(ws))
            out["fits"][f"{c}/{dec}"] = {"theta": list(th), "w_min_measured": min(ws)}
            print(f"     fit cloglog f = poly(log w - log 40): {np.round(th, 2).tolist()}")
        if len(fits) < 2:
            continue
        for p in ps:
            row = {}
            vals = {}
            for c in CIRCS:
                th, boots, wmin = fits[c]
                pi = pis[(c, p)]
                w = np.arange(1, len(pi))
                P = float((pi[1:] * f_model(th, w)).sum())
                extr = float((pi[1:wmin] * f_model(th, w[:wmin - 1])).sum()) / P if P > 0 else np.nan
                Pb = np.array([(pi[1:] * f_model(bt, w)).sum() for bt in boots])
                vals[c] = np.array([per_round_per_logical(x) for x in Pb])
                row[c] = {"P_any": P, "B": per_round_per_logical(P), "B_ci95": list(np.percentile(vals[c], [2.5, 97.5])),
                          "frac_from_extrapolated_w": extr}
            rb = vals["ibm"] / vals["twocolour"]
            row["ratio"] = row["ibm"]["B"] / row["twocolour"]["B"]
            row["ratio_ci95"] = list(np.percentile(rb, [2.5, 97.5]))
            out["ler"][f"{dec}/p{p}"] = row
            print(f"   {dec:8s} p={p:<7} IBM B={row['ibm']['B']:.2e} [{row['ibm']['B_ci95'][0]:.1e},{row['ibm']['B_ci95'][1]:.1e}]"
                  f" (extrap {row['ibm']['frac_from_extrapolated_w']:.0%})  2c B={row['twocolour']['B']:.2e}"
                  f" (extrap {row['twocolour']['frac_from_extrapolated_w']:.0%})  ratio {row['ratio']:.2f}"
                  f" [{row['ratio_ci95'][0]:.2f}, {row['ratio_ci95'][1]:.2f}]")
    (OUT / f"fw_summary_prior{a.prior}_deg{a.deg}.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
