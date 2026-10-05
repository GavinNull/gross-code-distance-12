"""Exact (complete DFS) search over LRC circuits whose block order depends on a colour class, for any partition
of the group derived from a homomorphism h: G -> Z_p:
   z2   : colour = h(g) in Z_2                         (two-colour rule, index-2 subgroup)
   z3   : colour = h(g) in Z_3                         (three-colour, Strikis-style)
   z3two: colour = 0 if h(g) == 0 else 1               (two classes of sizes 1/3, 2/3; not a homomorphism)
Pipeline per kind: (1) class test (residuals of one colour class only, every block order; for z3two both classes,
for z2/z3 class 0 suffices because classes are translates) decided by DFS at W = target-1; (2) all proper
combinations of surviving orders decided by DFS.  All decisions are complete; symmetry = colour-preserving
translations.

    PYTHONPATH=. uv run python search/experiments/e015/part.py --code bb90 --target 9 --scheme z3two
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import BLOCKS, OUT, check_orders, colour_symmetry, get_code, homs_to_Zp, now, proper  # noqa: E402
from dfsrun import decide  # noqa: E402
from search.noninterleaved.colour_search import order_terms  # noqa: E402
from search.noninterleaved.schedules import neighbours  # noqa: E402


def colourings(code, scheme):
    p = 2 if scheme == "z2" else 3
    out = []
    for h in homs_to_Zp(code, p):
        col = h["colour"] if scheme in ("z2", "z3") else tuple(0 if c == 0 else 1 for c in h["colour"])
        out.append((f"{scheme}:{h['u']}{h['v']}", col))
    return out


def run(codekey, target, scheme, kinds="XZ", log=print, max_states=None):
    code = get_code(codekey)
    res = {}
    for name, col in colourings(code, scheme):
        ncol = max(col) + 1
        sym = colour_symmetry(code, col)
        for kind in kinds:
            t0 = time.time()
            # class tests
            classes = range(ncol) if scheme == "z3two" else [0]
            alive = {}
            for c in classes:
                alive[c] = []
                for bi, b in enumerate(BLOCKS):
                    o = order_terms(kind, *b)
                    orders = [[neighbours(code, kind, i, t) for t in o] if col[i] == c else
                              [neighbours(code, kind, i, 0)] for i in range(code.n2)]  # length-1 order: no residual
                    r = decide(code, kind, orders, sym, target - 1)
                    if not r["found_any"]:
                        alive[c].append(bi)
            if scheme != "z3two":
                for c in range(1, ncol):
                    alive[c] = alive[0]
            states = []
            for combo in itertools.product(*[alive[c] for c in range(ncol)]):
                if proper(code, kind, col, {c: BLOCKS[b] for c, b in enumerate(combo)}):
                    states.append(combo)
            good = []
            nodes = 0
            for st in states[:max_states]:
                orders = check_orders(code, kind, col, {c: BLOCKS[b] for c, b in enumerate(st)})
                r = decide(code, kind, orders, sym, target - 1)
                nodes += r["nodes"]
                if not r["found_any"]:
                    good.append(st)
            res[f"{name}_{kind}"] = {"colouring": name, "kind": kind, "class_sizes": [col.count(c) for c in range(ncol)],
                                     "sym": len(sym), "class_alive": {str(c): len(v) for c, v in alive.items()},
                                     "num_states": len(states), "achieving": good,
                                     "achieving_blocks": [[BLOCKS[b] for b in s] for s in good],
                                     "sec": round(time.time() - t0, 1)}
            log(f"[{now()}] {codekey} {name} {kind}: class alive {res[f'{name}_{kind}']['class_alive']}, "
                f"{len(states)} proper states, {len(good)} with d_ext>={target} (DFS complete) {time.time() - t0:.0f}s")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--target", type=int, required=True)
    ap.add_argument("--scheme", default="z3two")
    ap.add_argument("--kinds", default="XZ")
    a = ap.parse_args()
    logf = open(OUT / f"part_{a.code}_{a.scheme}_T{a.target}.log", "a")

    def log(m):
        print(m, flush=True); logf.write(m + "\n"); logf.flush()
    res = run(a.code, a.target, a.scheme, a.kinds, log)
    (OUT / f"part_{a.code}_{a.scheme}_T{a.target}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
