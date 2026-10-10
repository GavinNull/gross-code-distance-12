"""E-022: held-out codes for the prediction test. Registers extra weight-6 BB codes into the E-019 code table
(at runtime; E-019 files are not modified) and checks which (hom, variant) give valid two-round morphing circuits
(Shaw-Terhal 2407.16336 rule: f: G -> Z_2 onto, each of A, B has exactly one term with a different f-value;
validity re-derived by Pauli propagation in e019.common.analyse: every mid-cycle stabiliser contracts in exactly
one round onto one same-basis measured right qubit, end-cycle k = mid-cycle k).

usage: uv run python -m search.experiments.e022.newcodes survey     # validity + end-cycle (n, k) for all
       uv run python -m search.experiments.e022.newcodes random S   # draw random small BB codes (seed S)
"""
from __future__ import annotations

import json
import random
import sys

import numpy as np

from search.experiments.e019 import common
from search.experiments.e019.common import VARIANTS, Code, analyse, hom_valid, rank, spec

NEW = {
    # project catalogue (search/experiments/e015/common.py); polynomials as exponent pairs (i, j) = x^i y^j
    "bb120p": (20, 3, [(0, 0), (3, 2), (7, 2)], [(0, 0), (16, 1), (9, 1)]),      # [[120,8,12]] (E-004 pilot)
    "bb124p": (31, 2, [(0, 0), (27, 1), (17, 0)], [(0, 0), (30, 1), (12, 1)]),   # [[124,10,10]] (E-004 pilot)
    "wmc108": (2, 27, [(0, 0), (1, 3), (0, 15)], [(0, 0), (0, 6), (1, 12)]),     # 2408.10001 Tab.2 coprime, pi = xy
    "wm180": (6, 15, [(3, 0), (0, 1), (0, 2)], [(0, 6), (4, 0), (5, 0)]),        # 2408.10001 Tab.1 [[180,8,16]]
}

RES = "/Users/ephemeral/Desktop/qec-ai-search/results/E-022-morphing-criterion"


def register(extra=None):
    common.CODES.update(NEW)
    if extra:
        common.CODES.update(extra)


def load_random():
    try:
        d = json.load(open(f"{RES}/random_codes.json"))
    except FileNotFoundError:
        return {}
    return {k: (v["l"], v["m"], [tuple(t) for t in v["A"]], [tuple(t) for t in v["B"]]) for k, v in d.items()}


def mid_k(code):
    HX, HZ = code.checks()
    return int(2 * code.N - rank(HX) - rank(HZ))


def valid_variants(name):
    code = common.get_code(name)
    out = []
    for hom in ("x", "y", "xy"):
        if not hom_valid(code, hom):
            continue
        for v in VARIANTS:
            try:
                gates, meas, _, _ = spec(code, hom, v)
                info, ec = analyse(code, gates, meas)
                ok = bool(info["each_stab_contracted_once"] and info["ec0"]["k"] == info["k_mid"] == info["ec1"]["k"])
            except AssertionError as e:
                ok, info = False, {"error": repr(e)}
            out.append(dict(key=f"{name}_{hom}_{v}", ok=ok, k=info.get("k_mid"),
                            w=(info.get("ec0", {}).get("wX"), info.get("ec1", {}).get("wX"))))
    return out


def random_codes(seed, n_want=6, Nmax=60):
    """random weight-6 BB codes with N = l*m <= Nmax, k >= 4, at least one valid homomorphism."""
    rng = random.Random(seed)
    got = {}
    tries = 0
    while len(got) < n_want and tries < 20000:
        tries += 1
        l, m = rng.choice([(4, 6), (6, 4), (6, 6), (8, 6), (6, 8), (10, 6), (6, 10), (8, 4), (4, 8), (12, 4), (10, 4),
                           (12, 5), (14, 4), (8, 8), (10, 3), (12, 3), (14, 3)])
        if l * m > Nmax:
            continue

        def poly():
            while True:
                t = [(rng.randrange(l), rng.randrange(m)) for _ in range(3)]
                if len(set(t)) == 3:
                    return t
        A, B = poly(), poly()
        code = Code("tmp", l, m, A, B)
        if not any(hom_valid(code, h) for h in ("x", "y", "xy") if not ((h in ("x", "xy") and l % 2) or (h in ("y", "xy") and m % 2))):
            continue
        k = mid_k(code)
        if k < 4:
            continue
        name = f"r{seed}n{2 * l * m}k{k}_{len(got)}".replace("_", "i")
        got[name] = dict(l=l, m=m, A=A, B=B, k=k)
    return got


if __name__ == "__main__":
    register(load_random())
    if sys.argv[1] == "survey":
        names = sys.argv[2:] or list(NEW) + list(load_random())
        res = {}
        for nm in names:
            vv = valid_variants(nm)
            res[nm] = vv
            print(nm, "N", common.get_code(nm).N, "k_mid", mid_k(common.get_code(nm)),
                  "valid", sum(x["ok"] for x in vv), "/", len(vv), flush=True)
        json.dump(res, open(f"{RES}/survey_{'_'.join(names) if len(names) < 4 else 'all'}.json", "w"), indent=1)
    elif sys.argv[1] == "random":
        seed = int(sys.argv[2])
        got = random_codes(seed)
        old = {}
        try:
            old = json.load(open(f"{RES}/random_codes.json"))
        except FileNotFoundError:
            pass
        old.update(got)
        json.dump(old, open(f"{RES}/random_codes.json", "w"), indent=1)
        print(json.dumps(got))
