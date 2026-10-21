"""A5: encoding-independent spot check of the uniform-family UNSAT (claim 2).
Random translation-invariant single-ancilla circuits of period P (wrapping allowed), X and Z orders drawn from the
8 orders of class A1A2A3B2B1B3 (the class whose complete lists the E-028 audit produced), random CNOT offsets in
[1, P-2] in order, prep at offset 0, meas at P-1; rejection-sampled for legality (own unroll) and determinism (stim).
Each is then handed to a3_lift.py --stop (R = 1..RMAX, both bases).  The UNSAT claim predicts that EVERY such circuit
has a weight <= 9 undetected logical (in the bulk, i.e. for some R).
    uv run python research/audits/2026-10-22-E-030-scripts/a5_random_uniform.py P NCIRC SEED"""
import json
import random
import subprocess
import sys

sys.path.insert(0, "research/audits/2026-10-22-E-030-scripts")
import numpy as np
from mylib import *

P, NC, SEED = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
RMAX = 4
rng = random.Random(SEED)
monoA = {"A1": mono(9, 0), "A2": mono(0, 1), "A3": mono(0, 2)}
monoB = {"B1": mono(0, 0), "B2": mono(2, 0), "B3": mono(7, 0)}


def col(Mx, i):
    return int(np.flatnonzero(Mx[i])[0])


def table(ty, i):
    if ty == "X":
        t = {k: col(m, i) for k, m in monoA.items()}
        t.update({k: N2 + col(m, i) for k, m in monoB.items()})
    else:
        t = {k: col(m.T, i) for k, m in monoB.items()}
        t.update({k: N2 + col(m.T, i) for k, m in monoA.items()})
    return t


HX, HZ = bb_code()
for i in range(N2):
    assert sorted(table("X", i).values()) == np.flatnonzero(HX[i]).tolist()
    assert sorted(table("Z", i).values()) == np.flatnonzero(HZ[i]).tolist()
base = ["A1", "A2", "A3", "B2", "B1", "B3"]


def rand_order():
    o = list(base)
    if rng.random() < .5: o[0], o[1] = o[1], o[0]
    if rng.random() < .5: o[4], o[5] = o[5], o[4]
    if rng.random() < .5: o = o[::-1]
    return o


def make():
    d = {"format": "qec-schedule/v1", "period": P, "x_checks": [], "z_checks": []}
    for ty, key, s in (("X", "x_checks", 0), ("Z", "z_checks", rng.randrange(P))):
        o = rand_order()
        offs = sorted(rng.sample(range(1, P - 1), 6))
        for i in range(N2):
            T = table(ty, i)
            d[key].append({"prep": s % P, "meas": (s + P - 1) % P,
                           "cnots": [[T[lab], (s + off) % P] for lab, off in zip(o, offs)]})
    return d


found, tries = [], 0
while len(found) < NC:
    tries += 1
    d = make()
    try:
        for b in "ZX":
            memory_circuit(d, b, 2).detector_error_model(allow_gauge_detectors=False)
    except Exception:
        continue
    found.append(d)
print("tries", tries, flush=True)
out = []
for n, d in enumerate(found):
    path = f"results/E-030-audit/rand_P{P}_s{SEED}_{n}.json"
    json.dump(d, open(path, "w"))
    hit = None
    for R in range(1, RMAX + 1):
        for b in "ZX":
            r = subprocess.run(["uv", "run", "python", "research/audits/2026-10-22-E-030-scripts/a3_lift.py", path, b,
                                str(R), "--stop"], capture_output=True, text=True, check=True)
            js = json.loads(r.stdout.strip().splitlines()[-1])
            if js["w8"] or js["w8z"] or js["w9"]:
                hit = {"R": R, "basis": b, "w8": js["w8"], "w8z": js["w8z"], "w9": js["w9"]}
                break
        if hit:
            break
    out.append({"spec": path, "hit": hit})
    print(json.dumps(out[-1]), flush=True)
json.dump({"P": P, "seed": SEED, "tries": tries, "results": out}, open(f"results/E-030-audit/a5_rand_P{P}_s{SEED}.json", "w"), indent=1)
