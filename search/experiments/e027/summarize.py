"""Summaries of the E-027 result files (CPU totals, sizes, verdicts).

    uv run python search/experiments/e027/summarize.py
"""
import json
from collections import Counter
from pathlib import Path

RES = Path("results/E-027-certificates")


def load(p):
    return [json.loads(l) for l in open(p)] if p.exists() else []


def cpu(r):
    return sum(r.get(k, {}).get("cpu_s", 0) for k in ("solver", "drat_trim", "cake_lpr"))


p3 = {r["name"]: r for r in load(RES / "part3/results.jsonl")}
print(f"part 3: {len(p3)} CNFs; verdicts", Counter(r.get("drat_trim", {}).get("verdict") for r in p3.values()),
      "cake", Counter(r.get("cake_lpr", {}).get("verdict") for r in p3.values()))
print(f"  CPU h total {sum(map(cpu, p3.values())) / 3600:.2f}; solver {sum(r['solver']['cpu_s'] for r in p3.values())/3600:.2f}"
      f" drat-trim {sum(r.get('drat_trim', {}).get('cpu_s', 0) for r in p3.values())/3600:.2f}"
      f" cake {sum(r.get('cake_lpr', {}).get('cpu_s', 0) for r in p3.values())/3600:.2f}")
print(f"  DRAT bytes total {sum(r.get('drat_bytes', 0) for r in p3.values())/1e9:.2f} GB; > 100 MB:",
      sum(r.get("drat_bytes", 0) > 100e6 for r in p3.values()))
groups = {}
for n, r in p3.items():
    groups.setdefault(n.split("__")[0], []).append(r)
for g, rs in sorted(groups.items()):
    print(f"  {g:32s} n={len(rs):3d} ok={sum(r['ok'] for r in rs):3d} drat max {max(r.get('drat_bytes',0) for r in rs)/1e6:8.1f} MB "
          f"check max {max(r.get('drat_trim',{}).get('cpu_s',0) for r in rs):7.1f} s  cpu {sum(map(cpu, rs))/3600:.2f} h")
top = sorted(p3.values(), key=lambda r: -r.get("drat_bytes", 0))[:12]
for r in top:
    print(f"    {r['name']:55s} {r['clauses']:7d} cl  DRAT {r.get('drat_bytes',0)/1e6:8.1f} MB  LRAT {r.get('lrat_bytes',0)/1e6:8.1f} MB "
          f"solve {r['solver']['cpu_s']:7.1f} drat-trim {r.get('drat_trim',{}).get('cpu_s',0):7.1f} cake {r.get('cake_lpr',{}).get('cpu_s',0):6.1f}")

la = load(RES / "lift_A/results.jsonl")
if la:
    cov = {}
    for r in la:
        cov.setdefault((r["basis"], r["R"]), []).append(r)
    full = [k for k, rs in cov.items() if len({r["split"][0] for r in rs if r["ok"]}) == rs[0]["split"][1]]
    print(f"lift A: {len(la)} batches, ok {sum(r['ok'] for r in la)}, (basis,R) complete {len(full)}/64, "
          f"instances {sum(r['instances'] for r in la if r['ok'])}, CPU h {sum(map(cpu, la))/3600:.2f}, "
          f"DRAT {sum(r.get('drat_bytes',0) for r in la)/1e9:.1f} GB, LRAT {sum(r.get('lrat_bytes',0) for r in la)/1e9:.1f} GB, "
          f"max clauses {max(r['clauses'] for r in la)}")
    missing = sorted({(b, R) for b in "ZX" for R in range(1, 33)} - set(full))
    print("  incomplete (basis,R):", missing[:70])
