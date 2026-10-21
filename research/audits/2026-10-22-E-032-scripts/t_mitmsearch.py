"""Self-test of mitmsearch against brute force on random small column systems (trivial orbits): every
solution with no proper zero-syndrome subset ("minimal") must be reported, every reported set must be valid,
no set reported twice."""
import itertools, random, subprocess, sys
binp = sys.argv[1]
random.seed(7)
bad = 0
for trial in range(60):
    n, nb, nl = random.randint(10, 22), random.randint(5, 10), random.randint(1, 3)
    cols = set()
    while len(cols) < n:
        h = tuple(sorted(random.sample(range(nb), random.randint(1, 3)))) if random.random() > 0.1 else ()
        l = tuple(sorted(random.sample(range(nl), random.randint(0, nl))))
        if h or l:
            cols.add((h, l))
    cols = list(cols)
    W = random.randint(3, 6); look = random.randint(1, 3)
    txt = f"{n} {nb}\n" + "".join(f"{len(h)} {' '.join(map(str,h))} {len(l)} {' '.join(map(str,l))}\n" for h, l in cols)
    txt += f"{n}\n{' '.join(map(str, range(n)))}\n{' '.join(map(str, range(n)))}\n"
    r = subprocess.run([binp, str(W), "enum", str(look)], input=txt, capture_output=True, text=True)
    got = [frozenset(map(int, l.split()[2:])) for l in r.stdout.splitlines() if l.startswith("SOL")]
    def syn(S):
        s = set(); lo = set()
        for j in S:
            s ^= set(cols[j][0]); lo ^= set(cols[j][1])
        return s, lo
    minimal = set()
    for w in range(1, W + 1):
        for S in itertools.combinations(range(n), w):
            s, lo = syn(S)
            if s or not lo:
                continue
            if any(not syn(T)[0] for k in range(1, w) for T in itertools.combinations(S, k)):
                continue
            minimal.add(frozenset(S))
    ok = len(got) == len(set(got)) and all(not syn(S)[0] and syn(S)[1] for S in got) and minimal <= set(got)
    bad += not ok
    if not ok:
        print("FAIL", trial, n, nb, W, look, len(minimal), len(got), len(minimal - set(got)))
print("trials 60, failures", bad)
