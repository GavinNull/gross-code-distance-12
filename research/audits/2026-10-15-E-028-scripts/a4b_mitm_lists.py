"""A4b: complete weight-<=9 extended-logical lists by meet-in-the-middle (mitm.c), with a translation-orbit case split.
Own extended code (a4_extlist.ext_code) from the circuit's actual CNOT orders.  The 45 translations act on columns
(support translation + key lookup, asserted bijective); orbit case k: the set contains rep_k and no column of orbits < k.
Expanded by the group, deduplicated, re-verified, compared with the project's pickles.   Usage: a4b SPEC KIND WMAX"""
import sys, json, pickle, subprocess, time, itertools
sys.path.insert(0, "research/audits/2026-10-15-E-028-scripts")
import numpy as np
from alib import *
from a4_extlist import ext_code, verify

spec_path, kind, WMAX = sys.argv[1], sys.argv[2], int(sys.argv[3])
spec = load_spec(spec_path); tag = spec_path.split("/")[-1][:3]
keys, cols = ext_code(spec, kind)
n = len(keys); kidx = {k: j for j, k in enumerate(keys)}
HX, HZ, LX, LZ = code_with_logicals()
H, Lg = (HZ, LZ) if kind == "X" else (HX, LX)
def keyof(qs):
    v = np.zeros(N, np.int64); v[list(qs)] = 1
    return (tuple((H @ v) % 2), tuple((Lg @ v) % 2))
def qperm(ga, gb):
    p = np.zeros(N, int)
    for blk in (0, N2):
        for i in range(N2):
            a, b = divmod(i, M_)
            p[blk + i] = blk + ((a + ga) % L_) * M_ + (b + gb) % M_
    return p
perms = []
for ga in range(L_):
    for gb in range(M_):
        p = qperm(ga, gb)
        P = [kidx[keyof([p[q] for q in cols[k][0]])] for k in keys]
        assert sorted(P) == list(range(n))
        perms.append(P)
orb = [-1] * n; reps = []
for j in range(n):
    if orb[j] < 0:
        for P in perms: orb[P[j]] = len(reps)
        reps.append(j)
nh = len(keys[0][0])
ikey = []
for h, l in keys:
    v = sum(int(b) << i for i, b in enumerate(h)) | (sum(int(b) << i for i, b in enumerate(l)) << nh)
    ikey.append(v)
res = {"kind": kind, "N": n, "orbits": len(reps)}
allsols = {}
for w in range(1, WMAX + 1):
    t0 = time.time(); found = set()
    for k, r in enumerate(reps):
        A = [j for j in range(n) if orb[j] >= k and j != r]
        inp = f"{n} {w} {nh}\n" + " ".join(map(str, ikey)) + f"\n{r} {len(A)} " + " ".join(map(str, A)) + "\n"
        pr = subprocess.run(["results/E-028-audit/mitm"], input=inp, capture_output=True, text=True, check=True)
        for line in pr.stdout.splitlines():
            S = tuple(sorted(int(x) for x in line.split()[1:]))
            assert len(set(S)) == w
            for P in perms:
                found.add(tuple(sorted(P[j] for j in S)))
    assert all(verify(keys, S) for S in found)
    allsols[w] = sorted(found)
    res[f"w{w}"] = len(found)
    print(kind, "w", w, len(found), round(time.time() - t0, 1), "s", flush=True)
# compare with project lists
from evaluators.tasks import build_code, get_task
c, _ = build_code(get_task("bb90-dcirc"), None)
He, Le = ((np.asarray(c.HZ) % 2, np.asarray(c.LZ) % 2) if kind == "X" else (np.asarray(c.HX) % 2, np.asarray(c.LX) % 2))
def ekey(S):
    v = np.zeros(N, np.uint8); v[list(S)] = 1
    return ((He.astype(int) @ v) % 2).astype(np.uint8).tobytes() + ((Le.astype(int) @ v) % 2).astype(np.uint8).tobytes()
mykey = [ekey(cols[k][0]) for k in keys]
for w in (8, 9):
    if w > WMAX: continue
    d = pickle.load(open(f"results/E-028-bb90-interleaved/w{w}_{kind}_all_A1A2A3B2B1B3.pkl", "rb"))
    proj = {frozenset(S) for S in d["keys"]}
    mine = {frozenset(mykey[j] for j in S) for S in allsols[w]}
    res[f"cmp{w}"] = {"proj": len(proj), "mine": len(mine), "equal": proj == mine, "colset_equal": set(d["colset"]) == set(mykey)}
print(json.dumps(res), flush=True)
pickle.dump({"keys": keys, "cols": cols, "s8": allsols.get(8, []), "s9": allsols.get(9, []), "all": allsols},
            open(f"results/E-028-audit/ext_{tag}_{kind}.pkl", "wb"))
with open("results/E-028-audit/a4b_lists.jsonl", "a") as f:
    f.write(json.dumps({"spec": spec_path, **res}) + "\n")
