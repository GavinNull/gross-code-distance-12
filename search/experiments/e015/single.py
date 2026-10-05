"""Single-check bound (Strikis 2603.05481 Prop. 4 argument; E-005 stage `single`) by heuristic witnesses:
for check 0 of each kind and every one of the 720 CNOT orders (grouped into residual classes), look for a logical
of weight <= target-1 in (code + residuals of check 0 only).  If EVERY class of one kind has such a verified
witness, then every non-interleaved single-ancilla circuit has d_circ <= target-1 (any depth, any tiling).

    PYTHONPATH=. uv run python search/experiments/e015/single.py --code bb120p --target 12
"""
import argparse
import itertools
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import HL, OUT, get_code, heur, now  # noqa: E402
from search.noninterleaved.ext import extended_matrices, residual_supports  # noqa: E402
from search.noninterleaved.schedules import neighbours  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--target", type=int, required=True)
    ap.add_argument("--kinds", default="XZ")
    ap.add_argument("--trials", type=int, default=300)
    a = ap.parse_args()
    code = get_code(a.code)
    out = {}
    for kind in a.kinds:
        H, L = HL(code, kind)
        sup = [neighbours(code, kind, 0, t) for t in range(6)]
        classes = {}
        for p in itertools.permutations(range(6)):
            He, Le, _ = extended_matrices(H, L, residual_supports([sup[t] for t in p]))
            key = tuple(sorted(He[:, j].tobytes() + Le[:, j].tobytes() for j in range(He.shape[1])))
            classes.setdefault(key, []).append(p)
        t0 = time.time()
        res = []
        for key, ps in classes.items():
            He, Le, _ = extended_matrices(H, L, residual_supports([sup[t] for t in ps[0]]))
            w, _ = heur(He, Le, (0, 1, 2), a.trials, a.target)
            res.append({"order": ps[0], "size": len(ps), "w": w})
        hist = {}
        for r in res:
            hist[str(r["w"])] = hist.get(str(r["w"]), 0) + 1
        allk = all(r["w"] is not None and r["w"] < a.target for r in res)
        out[kind] = {"classes": len(classes), "hist": hist, "all_killed": allk, "results": res,
                     "sec": round(time.time() - t0)}
        print(f"[{now()}] {a.code} {kind}: {len(classes)} classes, witness hist {hist}, "
              f"all below {a.target}: {allk} ({time.time() - t0:.0f}s)", flush=True)
    (OUT / f"single_{a.code}_T{a.target}.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
