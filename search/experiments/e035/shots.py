"""E-035 shot rule (yaml plan 3_shot_rule): N = A / sum t_shot, 2 significant digits rounded down, cap 300000,
floor 300 (amended from 2000 after timing, before sampling: see yaml).  Writes results/.../shots.json and search/experiments/e035/shots.json (committed before sampling)."""
import json
import math
from pathlib import Path

from search.experiments.e035.common import OUT
from search.experiments.e035.plan import blocks


def round2(x):
    if x <= 0:
        return 0
    e = 10 ** (int(math.floor(math.log10(x))) - 1)
    return int(math.floor(x / e) * e)


def main():
    t = json.loads((OUT / "timing.json").read_text())
    res = {}
    for fam, model, dec, A, cs in blocks():
        tot = sum(t[f"{c}|{b}|{model}|{dec}"] for c in cs for b in "ZX")
        N = max(300, min(300000, round2(A / tot)))
        res[f"{fam}|{model}|{dec}"] = dict(N=N, circuits=list(cs), allowance_s=A, sum_t_shot=tot,
                                           expected_cpu_s=N * tot)
        print(fam, model, dec, "N =", N, "expected CPU s", round(N * tot))
    s = json.dumps(res, indent=1)
    (OUT / "shots.json").write_text(s)
    (Path(__file__).parent / "shots.json").write_text(s)
    print("total expected CPU h", round(sum(r["expected_cpu_s"] for r in res.values()) / 3600, 2))


if __name__ == "__main__":
    main()
