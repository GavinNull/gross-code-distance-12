"""E-029: randomised test of ccsearch against brute force (own code).

Random sparse instances (columns with 1-4 rows, a few observables, optional random free group action by a cyclic
shift of blocks); brute force enumerates all subsets up to weight w and finds the minimum weight d and all
weight-d solutions.  ccsearch must report NONE at d-1, FOUND at d, and (enum d, expanded by the group) exactly the
brute-force weight-d set.

    uv run python search/experiments/e029/selftest.py BIN NTRIALS
"""
import itertools
import random
import subprocess
import sys
import tempfile


def make(rng):
    # cyclic group Z_g acting on rows (blocks of size rb) and columns (orbits of size g)
    g = rng.choice([1, 2, 3, 4])
    rb = rng.randint(4, 7)
    nr = g * rb
    norb = rng.randint(4, 12 // g + 4)
    nobs = rng.randint(1, 3)
    base = []
    for _ in range(norb):
        k = rng.randint(1, 4)
        rows = rng.sample(range(nr), k)
        obs = [o for o in range(nobs) if rng.random() < 0.3]
        base.append((rows, obs))
    cols, orbs, seen = [], [], set()
    for rows, obs in base:
        orb = []
        for t in range(g):
            r = tuple(sorted(((x // rb + t) % g) * rb + x % rb for x in rows))
            if (r, tuple(obs)) in seen:
                continue
            seen.add((r, tuple(obs)))
            orb.append(len(cols))
            cols.append((r, tuple(obs)))
        if len(orb) != g:      # skip non-free orbits: drop them entirely
            for _ in orb:
                cols.pop()
            continue
        orbs.append(orb)
    # remove duplicate syndromes (engine assumes distinct row sets)
    rs = {}
    keep_orbs = []
    for orb in orbs:
        if any(cols[j][0] in rs for j in orb):
            continue
        for j in orb:
            rs[cols[j][0]] = j
        keep_orbs.append(orb)
    ren = {}
    newcols, neworbs = [], []
    for orb in keep_orbs:
        o2 = []
        for j in orb:
            ren[j] = len(newcols); o2.append(len(newcols)); newcols.append(cols[j])
        neworbs.append(o2)
    # observables are NOT shifted by the group, so the group need not preserve nontriviality -> only use g>1
    # when nobs observables are invariant: make observables depend on the orbit only
    return nr, nobs, newcols, neworbs, g, rb


def act(t, j, orbs):
    for orb in orbs:
        if j in orb:
            return orb[(orb.index(j) + t) % len(orb)]


def brute(nr, nobs, cols, wmax):
    n = len(cols)
    S = [sum(1 << r for r in c[0]) for c in cols]
    L = [sum(1 << o for o in c[1]) for c in cols]
    for w in range(1, wmax + 1):
        sols = []
        for comb in itertools.combinations(range(n), w):
            s = l = 0
            for j in comb:
                s ^= S[j]; l ^= L[j]
            if s == 0 and l:
                sols.append(comb)
        if sols:
            return w, set(sols)
    return None, set()


def run(binp, path, mode, W):
    out = subprocess.run([binp, path, mode, str(W)], capture_output=True, text=True).stdout
    sols = [tuple(sorted(int(x) for x in line.split(":")[1].split())) for line in out.splitlines() if line.startswith("SOL")]
    status = [line for line in out.splitlines() if line.startswith("DONE")][0].split()[1]
    return status, sols


def main():
    binp, ntr = sys.argv[1], int(sys.argv[2])
    rng = random.Random(2029)
    bad = 0
    done = 0
    for trial in range(ntr):
        nr, nobs, cols, orbs, g, rb = make(rng)
        # observables: make them group-invariant by giving every column of an orbit the same observable set
        cols = list(cols)
        for orb in orbs:
            o = cols[orb[0]][1]
            for j in orb:
                cols[j] = (cols[j][0], o)
        if len(cols) < 3 or len(cols) > 30:
            continue
        d, bs = brute(nr, nobs, cols, 5)
        if d is None:
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write(f"{nr} {len(cols)} {nobs} {len(orbs)}\n")
            for r, o in cols:
                f.write(f"{len(r)} {' '.join(map(str, r))} {len(o)} {' '.join(map(str, o))}\n")
            for orb in orbs:
                f.write(f"{len(orb)} {' '.join(map(str, orb))}\n")
            path = f.name
        st_lo = run(binp, path, "decide", d - 1)[0] if d > 1 else "NONE"
        st_hi = run(binp, path, "decide", d)[0]
        _, es = run(binp, path, "enum", d)
        exp = {tuple(sorted(act(t, j, orbs) for j in s)) for s in es for t in range(g)}
        ok = st_lo == "NONE" and st_hi == "FOUND" and exp == bs
        done += 1
        if not ok:
            bad += 1
            print("MISMATCH", trial, d, st_lo, st_hi, len(exp), len(bs), path)
    print(f"selftest: {done} instances, {bad} mismatches")


if __name__ == "__main__":
    main()
