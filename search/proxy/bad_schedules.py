"""Find deliberately degraded (but valid, deterministic) depth-8 schedules by permuting IBM's term orders.

  PYTHONPATH=. uv run python -m search.proxy.bad_schedules --code "[[144,12,12]]" --tries 60 --seed 4

Enumerate all term orders (idle slots where IBM put them) that pass the necessary commutation conditions
(`valid_orders`), sample `tries` of them uniformly, check noiseless determinism (stim DEM, 2 rounds, both bases), then a low-budget circuit-distance upper
bound (evaluators.distance.upper_bound, 3 rounds, sd6, X and Z bases).  Writes a JSON line per tried schedule.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from baselines.circuit import memory_circuit
from baselines.schedule import IBM_SX, IBM_SZ
from evaluators.distance import upper_bound
from evaluators.noise import add_noise
from search.codes.schedule import default_schedule
from search.proxy.candidates import code_obj

OUT = Path("results/E-004-proxy-fidelity")


A_TERMS, B_TERMS = (0, 1, 2), (3, 4, 5)


def valid_orders(sX, sZ) -> bool:
    """Necessary conditions for a deterministic depth-8 BB cycle (idle slots as in IBM):
    (1) in a shared CNOT slot, X and Z checks must use terms of the same block type (A/A or B/B), otherwise both
        act on the same data block in the same layer; (2) an X check and a Z check overlap (if at all) on one L
        qubit (X via A_a, Z via B_b^T) and one R qubit (X via B_b, Z via A_a^T); they commute as measured only if
        the X-before-Z order is the same on both, i.e. [tX(A_a) < tZ(B_b)] == [tX(B_b) < tZ(A_a)] for all a, b.
    Sufficiency is checked afterwards with stim (noiseless determinism)."""
    tX = {t: i for i, t in enumerate(sX) if t is not None}
    tZ = {t: i for i, t in enumerate(sZ) if t is not None}
    for x, z in zip(sX, sZ):
        if x is not None and z is not None and ((x in A_TERMS) != (z in A_TERMS)):
            return False
    return all((tX[a] < tZ[b]) == (tX[b] < tZ[a]) for a in A_TERMS for b in B_TERMS)


def all_valid():
    import itertools
    out = []
    xs = [i for i, t in enumerate(IBM_SX) if t is not None]
    zs = [i for i, t in enumerate(IBM_SZ) if t is not None]
    for px in itertools.permutations(range(6)):
        sX = [None] * 7
        for i, t in zip(xs, px):
            sX[i] = t
        for pz in itertools.permutations(range(6)):
            sZ = [None] * 7
            for i, t in zip(zs, pz):
                sZ[i] = t
            if valid_orders(sX, sZ):
                out.append((sX, sZ))
    return out


def deterministic(css, sched) -> bool:
    try:
        for basis, L in (("Z", css.LZ), ("X", css.LX)):
            memory_circuit(sched, css.HX, css.HZ, L, 2, basis, 0.0, "both").detector_error_model()
        return True
    except Exception:  # noqa: BLE001
        return False


def dist(css, sched, rounds, seed, trials, lns, workers):
    out = {}
    for basis, L in (("Z", css.LZ), ("X", css.LX)):
        c = add_noise(memory_circuit(sched, css.HX, css.HZ, L, rounds, basis, 0.0), "sd6", 1e-3)
        r = upper_bound(c, seed=seed, bposd_trials=trials, lns_starts=lns, num_workers=workers,
                        methods=("graphlike", "bposd"))
        out[basis] = {"weight": r.weight, "seconds": r.seconds}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="[[144,12,12]]")
    ap.add_argument("--tries", type=int, default=40)
    ap.add_argument("--seed", type=int, default=4)
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--lns", type=int, default=8)
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    code = code_obj(a.code)
    css = code.to_css()
    rng = np.random.default_rng(a.seed)
    OUT.mkdir(parents=True, exist_ok=True)
    f = open(OUT / "bad_schedule_search.jsonl", "a")
    pool = all_valid()
    print(f"{len(pool)} term-order pairs pass the necessary conditions", flush=True)
    picks = rng.choice(len(pool), size=min(a.tries, len(pool)), replace=False)
    for i, j in enumerate(picks):
        sX, sZ = pool[j]
        sched = default_schedule(code, sX, sZ, name="perm")
        t0 = time.time()
        det = deterministic(css, sched)
        rec = {"code": a.code, "sX": sX, "sZ": sZ, "deterministic": det, "seed": a.seed, "try": i}
        if det:
            rec["dist_r3"] = dist(css, sched, 3, 0, a.trials, a.lns, a.workers)
        rec["seconds"] = round(time.time() - t0, 1)
        print(json.dumps(rec), flush=True)
        f.write(json.dumps(rec) + "\n")
        f.flush()


if __name__ == "__main__":
    main()
