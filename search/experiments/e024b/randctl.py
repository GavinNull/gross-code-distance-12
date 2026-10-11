"""E-024b classical control for step 1: uniform random colour-dependent type assignments ((a+b) mod 3 colouring, given
side), each tested by the same W=10 DFS oracle (stop at first witness).  Compare with the SAT+nogood loop, which
enumerated the complete survivor list of this colouring/side in 35 oracle calls.

    PYTHONPATH=. uv run python -m search.experiments.e024b.randctl --kind X --n 100 --seed 20261011
"""
import argparse
import json
import random
import time

from search.experiments.e024b.common import OUT, dfs, ext_general, labord, name, types


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default="X")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20261011)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    TY = types(a.kind)
    col = (3, 1, 1)
    t0 = time.time()
    res = []
    for k in range(a.n):
        assign = [rng.randrange(45) for _ in range(3)]
        E = ext_general(a.kind, labord(col, tuple(TY[t] for t in assign)))
        sols, nodes, complete = dfs(E, 10, stopfirst=1, workers=4)
        res.append({"assign": assign, "orders": [name(TY[t]) for t in assign], "witness": bool(sols),
                    "nodes": nodes, "complete_no_witness": (not sols) and complete})
    out = {"kind": a.kind, "n": a.n, "seed": a.seed, "survivors": sum(r["complete_no_witness"] for r in res),
           "sec": round(time.time() - t0, 1), "nodes": sum(r["nodes"] for r in res), "runs": res}
    (OUT / f"randctl_{a.kind}.json").write_text(json.dumps(out))
    print({k: v for k, v in out.items() if k != "runs"})


if __name__ == "__main__":
    main()
