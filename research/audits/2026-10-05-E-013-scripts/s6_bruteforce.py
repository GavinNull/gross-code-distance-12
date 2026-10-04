"""Independent check of dfs.c completeness: on BB72 [[72,12,6]] (l=m=6) extended codes with random row-parity
two-colour orders, enumerate ALL minimum-weight logicals by meet-in-the-middle brute force (Python, no pruning,
no symmetry), then compare (i) the minimum weight and (ii) the exact number of solutions y with
rep(min orbit of y) in y, which is exactly what the DFS must enumerate (each once)."""
import sys, json, random, itertools, subprocess
sys.path.insert(0, "research/audits/2026-10-05-E-013-scripts")
import numpy as np
import aud13
aud13.L_ = 6
from extcode import ext, dump_instance

DFS = "results/E-013-audit/dfs"


def brute(He, Le, wmax=6):
    N = He.shape[1]
    hk = [int("".join(map(str, He[:, j][::-1])), 2) for j in range(N)]
    lk = [int("".join(map(str, Le[:, j][::-1])), 2) for j in range(N)]
    for w in range(1, wmax + 1):
        a, b = (w + 1) // 2, w // 2
        tab = {}
        for S in itertools.combinations(range(N), b):
            h = 0
            for j in S: h ^= hk[j]
            tab.setdefault(h, []).append(S)
        sols = set()
        for S in itertools.combinations(range(N), a):
            h = 0
            for j in S: h ^= hk[j]
            for T in tab.get(h, ()):
                U = set(S) | set(T)
                if len(U) != w: continue
                l = 0
                for j in U: l ^= lk[j]
                if l: sols.add(frozenset(U))
        if sols:
            return w, sols
    return None, set()


rng = random.Random(int(sys.argv[1]))
res = []
for t in range(int(sys.argv[2])):
    kw = {k: rng.sample(range(6), 6) for k in ("xe", "xo", "ze", "zo")}
    for kind in "ZX":
        d = ext(kind, **kw)
        path = f"results/E-013-audit/bf_{kind}.txt"; dump_instance(d, path)
        w, sols = brute(d["He"], d["Le"])
        orb, reps = d["orbit"], d["reps"]
        expect = sum(1 for y in sols if reps[min(orb[j] for j in y)] in y)
        # DFS at W = w-1 must find nothing; at W = w count must equal expect
        cnt = {}
        for W in (w - 1, w):
            c = 0
            for k in range(len(reps)):
                o = subprocess.run([DFS, path, str(W), str(k)], capture_output=True, text=True).stdout
                c += int(o.split("found=")[1].split()[0])
            cnt[W] = c
        r = dict(t=t, kind=kind, N=d["He"].shape[1], orbits=len(reps), brute_min=w, brute_nsol=len(sols),
                 expected_dfs=expect, dfs_below=cnt[w - 1], dfs_at=cnt[w], ok=(cnt[w - 1] == 0 and cnt[w] == expect))
        print(json.dumps(r), flush=True); res.append(r)
json.dump(res, open(f"results/E-013-audit/s6_bruteforce_{sys.argv[1]}.json", "w"), indent=1)
