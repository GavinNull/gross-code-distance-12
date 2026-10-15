"""A8: third algorithm at R=1: brute-force product enumeration (no pruning) of one term per column, with
detector masks as Python ints, for every S in the weight-8 list (with and without each zero-image term, forced exactly
one) and every S in the weight-9 list.  Usage: a8 SPEC BASIS"""
import sys, json, pickle, itertools, time
sys.path.insert(0, "research/audits/2026-10-15-E-028-scripts")
from alib import *
from a5_lift import augmented_terms
spec_path, basis = sys.argv[1], sys.argv[2]
spec = load_spec(spec_path); tag = spec_path.split("/")[-1][:3]
kind = "X" if basis == "Z" else "Z"
E = pickle.load(open(f"results/E-028-audit/ext_{tag}_{kind}.pkl", "rb"))
kidx = {k: j for j, k in enumerate(E["keys"])}
terms, nd = augmented_terms(spec, basis, 1)
G = {}; zeros = []
for d, img in terms:
    m = sum(1 << x for x in d)
    if not any(img[0]) and not any(img[1]):
        if m: zeros.append(m)
        continue
    G.setdefault(kidx[img], set()).add(m)
G = {j: sorted(g) for j, g in G.items()}
def sums(S):
    acc = {0}
    for j in S:
        acc = {a ^ m for a in acc for m in G[j]}
    return acc
t0 = time.time()
out = {"spec": spec_path, "basis": basis, "R": 1, "w8": 0, "w8_plus_forced_zero": 0, "w9": 0}
for S in E["s8"]:
    s = sums(S)
    out["w8"] += 0 in s
    out["w8_plus_forced_zero"] += any(z in s for z in zeros)
for S in E["s9"]:
    out["w9"] += 0 in sums(S)
out["sec"] = round(time.time() - t0, 1)
print(json.dumps(out), flush=True)
with open("results/E-028-audit/a8_brute.jsonl", "a") as f: f.write(json.dumps(out) + "\n")
