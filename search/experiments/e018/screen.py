"""E-018 stage c screening: for a list of candidate schedules (time-shift interleavings of Fig. 12), check
legality, determinism, count interleaved data qubits, and run the exact lift checker (lift.solve) at given R on
orbit representatives (symmetric candidates) or on all logicals.  Output: one JSON line per candidate.

    PYTHONPATH=.:tests uv run python -m search.experiments.e018.screen --family colour --P 10 --R 2 --workers 5
"""
from __future__ import annotations

import argparse
import json
import pickle
import time
from multiprocessing import Pool

import numpy as np

from search.experiments.e018.common import OUT, ext
from search.experiments.e018.gen import XCOL, ZCOL, deterministic, legal_spec, prep_starts, spec_P
from search.experiments.e018.lift import KIND_OF_BASIS, build_groups, check_orders, solve

_LOG = {}


def logicals(kind, reps):
    k = (kind, reps)
    if k not in _LOG:
        sols = pickle.load(open(OUT / f"w11_all_{kind}.pkl", "rb"))
        if reps:
            perms = ext(kind)["perms"]
            reps_ = set()
            for S in sols:
                reps_.add(min(tuple(sorted(int(P[j]) for j in S)) for P in perms))
            sols = sorted(reps_)
        _LOG[k] = sols
    return _LOG[k]


def interleaved_qubits(spec):
    P = spec.period
    seq = [["."] * P for _ in range(144)]
    for kind, chk in (("X", spec.x_checks), ("Z", spec.z_checks)):
        for c in chk:
            for col, t in c.cnots:
                seq[col][t] = kind
    n = 0
    for s in seq:
        s = "".join(s).replace(".", "")
        n += sum(s[i] != s[(i + 1) % 6] for i in range(6)) > 2
    return n


def lift_counts(spec, Rs, reps=True, bases="ZX", stop_at=None):
    out = {}
    for R in Rs:
        for b in bases:
            groups, stats, _, _ = build_groups(spec, R, b)
            sols = logicals(KIND_OF_BASIS[b], reps)
            n = 0
            for S in sols:
                if solve(S, groups)[0] is not None:
                    n += 1
                    if stop_at and n >= stop_at:
                        break
            out[f"{b}{R}"] = n
    return out


def evaluate(item):
    name, sx, sz, P, Rs, reps, stop_at = item
    t0 = time.time()
    if isinstance(sx, str) and sx == "times":      # class-level CNOT times from cpgen (sz holds the 6x6 table)
        from search.experiments.e018.cpgen import spec_from_times
        spec = spec_from_times(np.array(sz), P, name=name).canonical()
        rec = {"name": name, "P": P, "times": sz}
    else:
        spec = spec_P(np.array(sx), np.array(sz), P, name=name).canonical()
        rec = {"name": name, "P": P, "sx": list(map(int, sx)), "sz": list(map(int, sz))}
    if not legal_spec(spec):
        rec["status"] = "conflict"; return rec
    check_orders(spec)
    if not deterministic(spec):
        rec["status"] = "nondeterministic"; return rec
    rec["interleaved_qubits"] = interleaved_qubits(spec)
    rec["lift"] = lift_counts(spec, Rs, reps, stop_at=stop_at)
    rec["status"] = "ok"
    rec["sec"] = round(time.time() - t0, 1)
    return rec


def colour_family(P):
    px, pz = prep_starts()
    leg = np.load(OUT / f"colour_legal_P{P}.npy")
    # class order in colour_legal: X colours 0,1,2 then Z colours 2,0,1 (as enumerated in the session script)
    items = []
    for off in leg:
        ox = np.array([off[0], off[1], off[2]])
        oz = np.zeros(3, int); oz[2], oz[0], oz[1] = off[3], off[4], off[5]
        items.append((f"P{P}_" + "".join(map(str, off)), px + ox[XCOL], pz + oz[ZCOL], P))
    return items


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", default="colour")
    ap.add_argument("--P", type=int, nargs="+", default=[10])
    ap.add_argument("--R", type=int, nargs="+", default=[2])
    ap.add_argument("--all", action="store_true", help="all logicals instead of orbit representatives")
    ap.add_argument("--stop_at", type=int, default=None)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    items = []
    if a.family.endswith(".json"):
        for path in a.family.split(","):
            d = json.load(open(path))
            items += [(f"{path.split('/')[-1][:-5]}_{i}", "times", T, d["P"], a.R, not a.all, a.stop_at)
                      for i, T in enumerate(d["times"])]
    for P in a.P:
        if a.family == "colour":
            items += [(n, sx, sz, P_, a.R, not a.all, a.stop_at) for n, sx, sz, P_ in colour_family(P)]
    print(f"{len(items)} candidates", flush=True)
    t0 = time.time()
    with Pool(a.workers) as pool, open(a.out, "a") as f:
        for i, rec in enumerate(pool.imap_unordered(evaluate, items)):
            f.write(json.dumps(rec) + "\n"); f.flush()
            if rec["status"] == "ok" and (i % 20 == 0 or min(rec["lift"].values()) < 176):
                print(i, rec["name"], rec["interleaved_qubits"], rec["lift"], rec.get("sec"), flush=True)
    print(f"done {time.time() - t0:.0f}s", flush=True)
