"""Auditor (E-029): adversarial random tests of ccsearch and auditsearch against meet-in-the-middle brute force.

    uv run python research/audits/2026-10-15-E-029-scripts/advtest.py CCSEARCH AUDITSEARCH NTRIALS SEED OUTDIR

Instances (unlike the experimenter's selftest):
  * cyclic group Z_g (g in 1..6) acting freely on rows (block shift) AND on observables (block shift of observable
    indices), so the observable matrix is NOT invariant - only equivariant;
  * "gauge dressing": every observable row gets a random combination of D rows added (L' = L + N D), so L' P != L'
    entrywise while ker[D;L'] is still invariant - this is the situation the rank test in export.py admits;
  * a planted zero-syndrome nontrivial set of weight dp (4..8) built orbit-wise, plus random noise columns with
    weights 1..7, some heavy rows;
  * truth from meet-in-the-middle over subsets of size <= 4 (exact for d <= 8): the minimum weight and the full
    list of minimum-weight solutions.
Checks per instance, for both engines: decide d-1 -> NONE; decide d -> FOUND (witness re-verified here);
enum d expanded by the group == brute-force set; also with the group switched off (each column its own orbit,
order reversed) for ccsearch.
"""
import itertools
import random
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


HARD = False


def make(rng):
    g = rng.choice([1, 2, 3, 4, 6])
    rb = rng.randint(3, 6) if not HARD else rng.randint(4, 10)          # rows per block
    nr = g * rb
    ob = rng.randint(1, 2)          # observables per block
    nobs = g * ob
    while True:
        base = []
        nbase = rng.randint(max(3, 8 // g), max(4, 36 // g))
        for _ in range(nbase):
            k = rng.choice([1, 2, 2, 3, 3, 3, 4, 5, 6, 7]) if not HARD else rng.choice([2, 2, 3, 3, 3, 4, 5, 6, 9])
            rows = frozenset(rng.sample(range(nr), min(k, nr)))
            obs = frozenset(o for o in range(nobs) if rng.random() < 0.25)
            base.append((rows, obs))
        # plant: dp-1 base columns + their xor (all in base, so the planted set is orbit-wise translated too)
        dp = rng.randint(3, 7) if not HARD else rng.randint(6, 8)
        pl = rng.sample(range(len(base)), min(dp - 1, len(base)))
        r = frozenset()
        o = frozenset()
        for j in pl:
            r ^= base[j][0]
            o ^= base[j][1]
        if r:
            o2 = o ^ frozenset([rng.randrange(nobs)])  # make it nontrivial
            base.append((r, o2))
        break

    def sh(rows, obs, t):
        return (frozenset(((x // rb + t) % g) * rb + x % rb for x in rows),
                frozenset(((x // ob + t) % g) * ob + x % ob for x in obs))
    cols, orbs, seenrows = [], [], set()
    for rows, obs in base:
        imgs = [sh(rows, obs, t) for t in range(g)]
        if len({i[0] for i in imgs}) < g or any(i[0] in seenrows for i in imgs) or not rows:
            continue
        orb = []
        for i in imgs:
            seenrows.add(i[0])
            orb.append(len(cols))
            cols.append(i)
        orbs.append(orb)
    # gauge dressing: observable o += sum of rows in a random set R_o (equivalent on ker D)
    dress = {o: [x for x in range(nr) if rng.random() < 0.2] for o in range(nobs)}
    cols2 = []
    for rows, obs in cols:
        ob2 = set(obs)
        for o, R in dress.items():
            if sum(1 for x in R if x in rows) % 2:
                ob2 ^= {o}
        cols2.append((sorted(rows), sorted(ob2)))
    return nr, nobs, cols2, orbs, g


def brute(cols, maxd=8):
    n = len(cols)
    S = [sum(1 << r for r in c[0]) for c in cols]
    L = [sum(1 << o for o in c[1]) for c in cols]
    buckets = defaultdict(list)
    for k in range(0, 5):
        for comb in itertools.combinations(range(n), k):
            s = l = m = 0
            for j in comb:
                s ^= S[j]; l ^= L[j]; m |= 1 << j
            buckets[s].append((m, l))
    best, sols = None, set()
    for lst in buckets.values():
        if len(lst) > 4000:
            return "big", None
        for i in range(len(lst)):
            mi, li = lst[i]
            for j in range(i + 1, len(lst)):
                mj, lj = lst[j]
                if li == lj:
                    continue
                x = mi ^ mj
                w = bin(x).count("1")
                if w > maxd:
                    continue
                if best is None or w < best:
                    best, sols = w, {x}
                elif w == best:
                    sols.add(x)
    return best, {tuple(j for j in range(n) if (x >> j) & 1) for x in sols}


def write(path, nr, nobs, cols, orbs):
    with open(path, "w") as f:
        f.write(f"{nr} {len(cols)} {nobs} {len(orbs)}\n")
        for r, o in cols:
            f.write(f"{len(r)} {' '.join(map(str, r))} {len(o)} {' '.join(map(str, o))}\n")
        for orb in orbs:
            f.write(f"{len(orb)} {' '.join(map(str, orb))}\n")


def run(binp, path, mode, W):
    out = subprocess.run([binp, path, mode, str(W)], capture_output=True, text=True, timeout=600)
    if out.returncode != 0:
        return "ERR%d" % out.returncode, []
    lines = out.stdout.splitlines()
    sols = [tuple(sorted(int(x) for x in ln.split(":")[1].split())) for ln in lines if ln.startswith("SOL")]
    st = [ln for ln in lines if ln.startswith("DONE")][0].split()[1]
    return st, sols


def check_sol(cols, s):
    if len(set(s)) != len(s):
        return False
    r, o = set(), set()
    for j in s:
        r ^= set(cols[j][0]); o ^= set(cols[j][1])
    return not r and bool(o)


def main():
    global HARD
    cc, au, ntr, seed, outdir = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), Path(sys.argv[5])
    HARD = len(sys.argv) > 6 and sys.argv[6] == "hard"
    outdir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    stats = defaultdict(int)
    bad = []
    for trial in range(ntr):
        nr, nobs, cols, orbs, g = make(rng)
        if len(cols) < 4 or len(cols) > 40:
            continue
        d, bs = brute(cols)
        if d is None or d == "big":
            stats["skipped"] += 1
            continue
        path = outdir / f"t{seed}_{trial}.txt"
        write(path, nr, nobs, cols, orbs)
        # no-symmetry version, orbits singletons in reverse order
        path1 = outdir / f"t{seed}_{trial}_nosym.txt"
        write(path1, nr, nobs, cols, [[j] for j in reversed(range(len(cols)))])

        def act(t, j):
            for orb in orbs:
                if j in orb:
                    return orb[(orb.index(j) + t) % len(orb)]
        ok = True
        for name, binp, p, grp in (("cc", cc, path, g), ("au", au, path, g), ("cc1", cc, path1, 1), ("au1", au, path1, 1)):
            lo = run(binp, p, "decide", d - 1)[0] if d > 1 else "NONE"
            hi, hs = run(binp, p, "decide", d)
            _, es = run(binp, p, "enum", d)
            exp = {tuple(sorted(act(t, j) if grp > 1 else j for j in s)) for s in es for t in range(grp)}
            good = lo == "NONE" and hi == "FOUND" and len(hs) == 1 and check_sol(cols, hs[0]) and exp == bs \
                and all(check_sol(cols, s) for s in es)
            if not good:
                ok = False
                bad.append((trial, name, d, lo, hi, len(exp), len(bs), str(p)))
        stats["done"] += 1
        stats[f"d={d}"] += 1
        stats[f"g={g}"] += 1
        if ok:
            path.unlink(); path1.unlink()
    print(dict(stats))
    for b in bad:
        print("MISMATCH", b)
    print(f"advtest seed={seed}: {stats['done']} instances, {len(bad)} mismatches")


if __name__ == "__main__":
    main()
