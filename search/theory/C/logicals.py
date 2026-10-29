"""Question C: weight-4 logical residuals per basis and how they meet check supports."""
import itertools, numpy as np
from search.experiments.e036_audit.core import checks, support, observables
ks = checks("bb18")
for b in ("Z", "X"):
    readers = [k for k in ks if k[0] == b]; spreaders = [k for k in ks if k[0] != b]
    obs = observables("bb18", b)
    L4 = []
    for S in itertools.combinations(range(18), 4):
        if all(len(set(S) & set(support(k))) % 2 == 0 for k in readers):
            v = np.zeros(18, int); v[list(S)] = 1
            if (obs @ v % 2).any():
                L4.append(frozenset(S))
    print(b, "weight-4 logical residuals:", len(L4))
    for k in spreaders:
        s = support(k)
        cnt = [sum(1 for L in L4 if {s[i], s[j]} <= L) for i, j in itertools.combinations(range(6), 2)]
        inside = [L for L in L4 if len(L & set(s)) >= 3]
        print(" ", k, "pairs->#L4:", cnt, " L4 with >=3 in supp:", len(inside))
    # weight <=3 logicals?
    for w in (1, 2, 3):
        n = 0
        for S in itertools.combinations(range(18), w):
            if all(len(set(S) & set(support(k))) % 2 == 0 for k in readers):
                v = np.zeros(18, int); v[list(S)] = 1
                if (obs @ v % 2).any(): n += 1
        print("  weight", w, "logicals", n)
