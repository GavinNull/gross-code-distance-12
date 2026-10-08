"""Audit E-018 (a2): independent re-derivation of claim A.
prep:    own extended code per kind (columns = distinct nonzero (H s, L s) keys over data qubits and Fig. 12 residual
         suffixes), instance file for w11dfs.c, column orbits under the 24 order/colour-preserving translations.
collect: union of orbits of the DFS outputs, compare with the experimenter's w11_all_{X,Z}.pkl (as key sets).
    PYTHONPATH=.:tests uv run python research/audits/2026-10-08-E-018-scripts/a2_stage_a.py prep
    PYTHONPATH=.:tests uv run python research/audits/2026-10-08-E-018-scripts/a2_stage_a.py collect
"""
import json, pickle, sys, glob, collections
import numpy as np
sys.path.insert(0, "tests"); sys.path.insert(0, "research/audits/2026-10-08-E-018-scripts")
from a1_common import HX, HZ, LX, LZ, xo, zo, xcol, zcol, tr

OUT = "results/E-018-audit"

def build(kind):
    H, L, ords = (HZ, LZ, xo) if kind == "X" else (HX, LX, zo)
    sups = [(j,) for j in range(144)] + [tuple(sorted(o[l:])) for o in ords for l in range(1, 6)]
    keys, kidx, colsup = [], {}, []
    supkey = {}
    for s in sups:
        v = np.zeros(144, np.uint8); v[list(s)] = 1
        hb, lb = (H @ v) % 2, (L @ v) % 2
        if not hb.any() and not lb.any():
            continue
        k = hb.tobytes() + lb.tobytes()
        supkey[s] = k
        if k not in kidx:
            kidx[k] = len(keys); keys.append((hb, lb)); colsup.append(s)
    return keys, kidx, colsup, supkey

def group(kind):
    ords = xo if kind == "X" else zo; cl = xcol if kind == "X" else zcol
    ords_set = {tuple(o): i for i, o in enumerate(ords)}
    G = []
    for a in range(12):
        for b in range(6):
            p = tr(a, b); pp = p + [x + 72 for x in p]
            if all(tuple(pp[q] for q in o) in ords_set and cl[ords_set[tuple(pp[q] for q in o)]] == cl[i]
                   for i, o in enumerate(ords)):
                G.append(pp)
    return G

def colperm(kind, pp, kidx, colsup):
    return [kidx[build_cache[kind][3][tuple(sorted(pp[q] for q in s))]] for s in colsup]

build_cache = {}
if __name__ == "__main__":
    mode = sys.argv[1]
    info = {}
    for kind in "XZ":
        keys, kidx, colsup, supkey = build_cache.setdefault(kind, build(kind))
        G = group(kind)
        perms = [colperm(kind, pp, kidx, colsup) for pp in G]
        N = len(keys)
        orb, seen = [], set()
        for j in range(N):
            if j in seen: continue
            o = {p[j] for p in perms}; seen |= o; orb.append(min(o))
        if mode == "prep":
            with open(f"{OUT}/inst_{kind}.txt", "w") as f:
                f.write(f"{N} 72 12\n")
                for hb, lb in keys:
                    h = int("".join(map(str, hb[::-1])), 2); l = int("".join(map(str, lb[::-1])), 2)
                    f.write(f"{h & ((1 << 64) - 1)} {h >> 64} {l}\n")
            info[kind] = {"N": N, "group": len(G), "col_orbit_reps": orb}
        else:
            found = set(); nodes = 0; summ = 0
            for fn in glob.glob(f"{OUT}/dfs_{kind}_*.txt"):
                for line in open(fn):
                    if line.startswith("SUMMARY"):
                        nodes += int(line.split()[4]); summ += 1; continue
                    S = tuple(map(int, line.split()))
                    for p in perms:
                        found.add(tuple(sorted(p[j] for j in S)))
            # experimenter's set as key sets
            from search.experiments.e018.common import ext
            E = ext(kind)
            theirs = set()
            for S in pickle.load(open(f"results/E-018-gross-interleaved-12/w11_all_{kind}.pkl", "rb")):
                theirs.add(tuple(sorted(kidx[supkey[E["col_sups"][j][0]]] for j in S)))
            orbs = collections.Counter()
            for S in found:
                orbs[len({tuple(sorted(p[j] for j in S)) for p in perms})] += 1
            info[kind] = {"N": N, "jobs_done": summ, "nodes": nodes, "found_total": len(found),
                          "theirs": len(theirs), "equal": found == theirs,
                          "only_mine": len(found - theirs), "only_theirs": len(theirs - found),
                          "orbit_size_hist": {k: v // k for k, v in orbs.items()}}
    print(json.dumps(info, indent=1))
    json.dump(info, open(f"{OUT}/a2_{mode}.json", "w"), indent=1)


def write_jobs():
    """EXCL files (columns of lower orbit classes) and the job list; run with
    xargs -P3 -L1 sh -c 'EXCL=$4 ./w11dfs inst_$0.txt 11 $1 $2 $3 > dfs_$0_$1_$3.txt' < jobs.txt  (in OUT)."""
    lines = []
    for kind in "XZ":
        keys, kidx, colsup, supkey = build_cache.setdefault(kind, build(kind))
        G = group(kind)
        perms = [colperm(kind, pp, kidx, colsup) for pp in G]
        classes, seen = [], set()
        for j in range(len(keys)):
            if j in seen: continue
            o = sorted({p[j] for p in perms}); seen |= set(o); classes.append(o)
        for k, cl in enumerate(classes):
            low = [c for cc in classes[:k] for c in cc]
            fn = f"excl_{kind}_{k}.txt"
            open(f"{OUT}/{fn}", "w").write(f"{len(low)}\n" + " ".join(map(str, low)) + "\n")
            for s in range(8):
                lines.append(f"{kind} {cl[0]} 8 {s} {fn}")
    open(f"{OUT}/jobs.txt", "w").write("\n".join(lines) + "\n")
    print(len(lines), "jobs")
