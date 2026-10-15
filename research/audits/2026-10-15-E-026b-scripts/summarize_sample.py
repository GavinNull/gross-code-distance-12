"""Auditor (E-026b): summarize sample.jsonl: per-round eps = eps_Z + eps_X (Jeffreys MC, seed 4242), ratio p18/fig12
per round and per layer (x 8/18), and consistency of each (lam, circ, basis) shot-failure rate with the experimenter's
csv (ratio of Jeffreys posteriors).
  uv run python research/audits/2026-10-15-E-026b-scripts/summarize_sample.py"""
import glob, json
from collections import defaultdict
from pathlib import Path
import numpy as np, sinter
ROOT = Path(__file__).resolve().parents[3]
A = defaultdict(lambda: [0, 0, 0.0])
for l in open(ROOT / "results/E-026b-audit/sample.jsonl"):
    r = json.loads(l); k = (r["lam"], r["circ"], r["basis"]); A[k][0] += r["shots"]; A[k][1] += r["fails"]; A[k][2] += r["cpu"]
E = defaultdict(lambda: [0, 0])
for f in glob.glob(str(ROOT / "results/E-026b-idle-sensitivity/direct/*.csv")):
    for s in sinter.read_stats_from_csv_files(f):
        m = s.json_metadata
        if m["R"] == 12 and m["p"] == 0.004 and s.decoder == "bposd" and m["noise"] in ("lam0", "lam0.1"):
            k = (0.0 if m["noise"] == "lam0" else 0.1, m["circ"], m["basis"]); E[k][0] += s.shots; E[k][1] += s.errors
rng = np.random.default_rng(4242); NS = 200000
out = {"counts": {str(k): v for k, v in A.items()}, "cpu_total_s": sum(v[2] for v in A.values())}
def draws(k):
    n, f = k[0], k[1]; return 1 - (1 - rng.beta(f + .5, n - f + .5, NS)) ** (1 / 12)
for lam in (0.0, 0.1):
    d = {}
    for c in ("p18", "fig12"):
        d[c] = sum(draws(A[(lam, c, b)]) for b in "ZX")
        pt = sum(1 - (1 - A[(lam, c, b)][1] / A[(lam, c, b)][0]) ** (1 / 12) for b in "ZX")
        lo, hi = np.quantile(d[c], [.025, .975])
        out[f"eps_lam{lam:g}_{c}"] = [pt, float(lo), float(hi)]
        print(f"lam {lam} {c}: Z {A[(lam,c,'Z')][:2]} X {A[(lam,c,'X')][:2]} eps {pt:.3e} [{lo:.2e}, {hi:.2e}]")
    rr = d["p18"] / d["fig12"]; q = np.quantile(rr, [.025, .5, .975])
    pt = out[f"eps_lam{lam:g}_p18"][0] / max(out[f"eps_lam{lam:g}_fig12"][0], 1e-300)
    out[f"ratio_lam{lam:g}"] = dict(point=pt, ci=[float(q[0]), float(q[2])], per_layer=pt * 8 / 18,
                                     per_layer_ci=[float(q[0] * 8 / 18), float(q[2] * 8 / 18)])
    print(f"lam {lam}: p18/fig12 per round {pt:.3g} [{q[0]:.3g}, {q[2]:.3g}], per layer {pt*8/18:.3g} [{q[0]*8/18:.3g}, {q[2]*8/18:.3g}]")
    for c in ("p18", "fig12"):
        for b in "ZX":
            a, e = A[(lam, c, b)], E[(lam, c, b)]
            x = rng.beta(a[1] + .5, a[0] - a[1] + .5, NS) / rng.beta(e[1] + .5, e[0] - e[1] + .5, NS)
            qq = np.quantile(x, [.025, .975])
            out[f"consistency_lam{lam:g}_{c}_{b}"] = dict(audit=a[:2], exp=e, ratio=(a[1] / a[0]) / (e[1] / e[0]), ci=qq.tolist())
            print(f"   {c} {b}: audit {a[1]}/{a[0]} vs exp {e[1]}/{e[0]}  ratio {(a[1]/a[0])/(e[1]/e[0]):.2f} [{qq[0]:.2f}, {qq[1]:.2f}]")
print("cpu", out["cpu_total_s"])
(ROOT / "results/E-026b-audit/sample_summary.json").write_text(json.dumps(out, indent=1))
