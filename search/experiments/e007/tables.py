import ast, json, re
from search.experiments.e007 import common as C
from search.experiments.e007.analyze import RUNS, fails, ratio
lines = []
for name, d in RUNS.items():
    ev = C.load_evals(C.RESULTS / d)
    n = ev[0]["metrics"]["counts"].get("shots", ev[0]["metrics"]["counts"].get("n"))
    lines += [f"### {name}（搜索集 {n} shot；CPU 比 = 候选 CPU/shot ÷ 参考(论文参数) CPU/shot）", "",
              "| # | 失败数 | P_any | CPU 比 | γ0 | γ 区间 | pre_iter | set_max_iter | num_sets | stop_nconv |", "|---|---|---|---|---|---|---|---|---|---|"]
    best = 10**9
    for r in ev:
        m = r["metrics"]
        if "params" in m:
            p = m["params"]
        else:
            p = ast.literal_eval(re.search(r"PARAMS = (\{.*?\})\n", r["src"], re.S).group(1))
        g = p["gamma_dist_interval"]; f = fails(m); best = min(best, f)
        lines.append(f"| {r['eval_index']} | {f} | {f/n:.4f} | {ratio(m):.2f} | {p['gamma0']:.3f} | [{g[0]:.2f}, {g[1]:.3f}] | {p['pre_iter']} | {p['set_max_iter']} | {p['num_sets']} | {p['stop_nconv']} |")
    lines.append("")
open(C.RESULTS / "candidates.md", "w").write("\n".join(lines))
print("\n".join(lines[:30]))
