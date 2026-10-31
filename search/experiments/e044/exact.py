"""E-044 (1): exact minimum-weight undetected logicals per round and their probability-weighted coefficients.

Lists:
  ibm, u11 : E-033 ccsearch enumerations (results/E-033-gross-u11-ler/runs, read by e033.lead.read_sols), columns =
             e029.export.dem_columns of e033.noisy(..., 1e-3, 'lam1'), expanded by the 72 DEM translations.
  c11, ibm90: E-030 ccsearch enumerations (e030.lead.run_enum reads the cached run files), 45 translations.
  g10      : new, mitmsearch (E-032 auditor's code, copied in the E-040 circuit audit) 'enum W look 3' on the instance
             built by search.experiments.e040_audit_circ.direct.build (72 translations verified term by term there),
             one orbit root case per process; solutions expanded by the 72 column permutations.
Every expanded logical is re-checked here on the DEM (detectors cancel, observable nonzero, W distinct columns).
Weights (per noise model m, DEM at p = P_LEAD, probabilities summed per (detectors, observables) signature):
  U_W = sum_L prod_{j in L} q_j / p^W                       (undetected-logical term, exact union form)
  A_t = c sum_L e_t(q_L) / p^t, t = ceil(W/2), c = 1/2 for even W (ties)   (ideal-decoder half-weight term)
Per round = difference between consecutive R.

  PYTHONPATH=.:tests uv run python -m search.experiments.e044.exact g10enum Z 1 12 --procs 2
  PYTHONPATH=.:tests uv run python -m search.experiments.e044.exact weights ibm 10 1,2,3
"""
from __future__ import annotations

import json
import subprocess
import sys
import time

import numpy as np

from search.experiments.e044.common import OUT

P_LEAD = 1e-4
MODELS = ("lam0", "lam1")
ED = OUT / "exact"
ED.mkdir(exist_ok=True)
MITM = OUT / "exact" / "mitm"


def esym(q, k):
    e = np.zeros(k + 1); e[0] = 1.0
    for x in q:
        e[1:] = e[1:] + x * e[:-1]
    return e[k]


def g10_instance(basis, R):
    from search.experiments.e040_audit_circ.direct import build
    keys, errs, nd, K, colperm = build("g10", basis, R)
    orb = [-1] * len(keys)
    reps = []
    for j in range(len(keys)):
        if orb[j] < 0:
            for pm in colperm:
                orb[pm[j]] = len(reps)
            reps.append(j)
    lines = [f"{len(keys)} {nd}"]
    for k in keys:
        lines.append(f"{len(k)} {' '.join(map(str, sorted(k)))} {len(errs[k])} {' '.join(map(str, sorted(errs[k])))}")
    lines += [str(len(reps)), " ".join(map(str, orb)), " ".join(map(str, reps))]
    inp = ED / f"g10_{basis}_R{R}.txt"
    inp.write_text("\n".join(lines) + "\n")
    return keys, errs, nd, colperm, reps, inp


def g10enum(basis, R, W, procs):
    keys, errs, nd, colperm, reps, inp = g10_instance(basis, R)
    nw = -(-nd // 64)
    exe = ED / f"mitm_nw{max(2, nw)}"
    if not exe.exists():
        subprocess.run(["cc", "-O3", "-march=native", f"-DNW={max(2, nw)}", "-o", str(exe),
                        "search/experiments/e040_audit_circ/mitmsearch.c"], check=True)
    outd = ED / f"g10_{basis}_R{R}_W{W}"
    outd.mkdir(exist_ok=True)
    pending = [o for o in range(len(reps)) if not (outd / f"o{o}.done").exists()]
    running = []
    t0 = time.time()
    while pending or running:
        while pending and len(running) < procs:
            o = pending.pop(0)
            fo = open(outd / f"o{o}.sol", "w")
            fe = open(outd / f"o{o}.err", "w")
            running.append((o, subprocess.Popen([str(exe), str(W), "enum", "3", str(o), str(o)], stdin=open(inp),
                                                stdout=fo, stderr=fe)))
        time.sleep(2)
        for o, p in list(running):
            if p.poll() is not None:
                assert p.returncode == 0, (o, p.returncode)
                (outd / f"o{o}.done").write_text("ok")
                running.remove((o, p))
                print(f"orbit {o} done {time.time() - t0:.0f}s", flush=True)


def load_g10(basis, R, W):
    keys, errs, nd, colperm, reps, inp = g10_instance(basis, R)
    outd = ED / f"g10_{basis}_R{R}_W{W}"
    assert all((outd / f"o{o}.done").exists() for o in range(len(reps)))
    sols = []
    for o in range(len(reps)):
        for ln in (outd / f"o{o}.sol").read_text().splitlines():
            if ln.startswith("SOL"):
                x = list(map(int, ln.split()[2:]))
                assert len(x) == W, "lower-weight solution"
                sols.append(x)
    full = set()
    for S in sols:
        for pm in colperm:
            full.add(tuple(sorted(pm[j] for j in S)))
    cols = [(tuple(sorted(k)), tuple(sorted(errs[k]))) for k in keys]
    return full, cols


def load_ccsearch(circ, basis, R, W):
    from search.experiments.e029.export import dem_columns, translations_dem
    if circ in ("ibm", "u11"):
        from search.experiments.e033.common import noisy
        from search.experiments.e033.lead import read_sols
        sols, _ = read_sols(circ, basis, R, W)
        dem, cols = dem_columns(noisy(circ, basis, R, 1e-3, "lam1"))
        cols = [c for c in cols if c[0] or c[1]]
        group, _ = translations_dem(dem, cols, 12, 6)
        assert len(group) == 72
    else:
        from search.experiments.e030.common import noisy
        from search.experiments.e030.lead import run_enum
        name = {"c11": "c11", "ibm90": "ibm"}[circ]
        sols, _ = run_enum(name, basis, R, W)
        dem, cols = dem_columns(noisy(name, basis, R, 1e-3, "lam1"))
        cols = [c for c in cols if c[0] or c[1]]
        group, _ = translations_dem(dem, cols, 15, 3)
        assert len(group) == 45
    full = set()
    for S in sols:
        for _, perm in group:
            full.add(tuple(sorted(perm[j] for j in S)))
    return full, cols


def priors(circ, basis, R, m):
    from search.experiments.e044.common import noisy
    dm = noisy(circ, basis, P_LEAD, m, rounds=R).detector_error_model(decompose_errors=False,
                                                                      approximate_disjoint_errors=True)
    pr = {}
    for e in dm.flattened():
        if e.type != "error":
            continue
        d, o = set(), set()
        for t in e.targets_copy():
            if t.is_relative_detector_id():
                d ^= {t.val}
            elif t.is_logical_observable_id():
                o ^= {t.val}
        k = (tuple(sorted(d)), tuple(sorted(o)))
        x = pr.get(k, 0.0)
        pr[k] = x * (1 - e.args_copy()[0]) + e.args_copy()[0] * (1 - x)
    return pr


def weights(circ, W, Rs, bases="ZX"):
    res = {"circ": circ, "W": W, "P_LEAD": P_LEAD, "per_R": {}}
    t = (W + 1) // 2
    for b in bases:
        for R in Rs:
            full, cols = load_g10(b, R, W) if circ == "g10" else load_ccsearch(circ, b, R, W)
            for S in full:
                d, o = set(), set()
                for j in S:
                    d ^= set(cols[j][0]); o ^= set(cols[j][1])
                assert not d and o and len(set(S)) == W
            row = {"N": len(full)}
            for m in MODELS:
                pr = priors(circ, b, R, m)
                U = A = 0.0
                dead = 0
                for S in full:
                    q = [pr.get(cols[j], 0.0) for j in S]
                    dead += any(x == 0 for x in q)
                    U += float(np.prod(q))
                    A += esym(q, t) * (0.5 if W % 2 == 0 else 1.0)
                row[m] = {"U": U / P_LEAD ** W, "A": A / P_LEAD ** t, "dead": dead}
            res["per_R"][f"{b}{R}"] = row
            print(circ, b, R, json.dumps(row), flush=True)
    pr_ = {}
    for b in bases:
        rr = sorted(Rs)
        e = {"N_diff": [res["per_R"][f"{b}{y}"]["N"] - res["per_R"][f"{b}{x}"]["N"] for x, y in zip(rr, rr[1:])]}
        for m in MODELS:
            for key in ("U", "A"):
                e[f"{key}_{m}"] = [res["per_R"][f"{b}{y}"][m][key] - res["per_R"][f"{b}{x}"][m][key] for x, y in zip(rr, rr[1:])]
        pr_[b] = e
    res["per_round"] = pr_
    print(json.dumps(pr_), flush=True)
    (ED / f"weights_{circ}_W{W}_R{'-'.join(map(str, Rs))}_{bases}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "g10enum":
        procs = int(sys.argv[sys.argv.index("--procs") + 1]) if "--procs" in sys.argv else 1
        g10enum(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), procs)
    elif sys.argv[1] == "weights":
        weights(sys.argv[2], int(sys.argv[3]), [int(x) for x in sys.argv[4].split(",")],
                sys.argv[5] if len(sys.argv) > 5 else "ZX")
