"""Question C, Lemma 1 facts: twin pairs, degrees, intersection sizes of weight-4 logical residuals with all checks."""
import itertools, collections, numpy as np
from search.experiments.e036_audit.core import checks, support, observables
ks = checks("bb18")
tw = [(x, z) for x in ks for z in ks if x[0] == "X" and z[0] == "Z" and set(support(x)) == set(support(z))]
print("twins", tw)
print("degrees", collections.Counter(sum(q in support(k) for k in ks) for q in range(18)))
for b in ("Z", "X"):
    rd = [k for k in ks if k[0] == b]; obs = observables("bb18", b); L4 = []
    for T in itertools.combinations(range(18), 4):
        if all(len(set(T) & set(support(k))) % 2 == 0 for k in rd):
            v = np.zeros(18, int); v[list(T)] = 1
            if (obs @ v % 2).any(): L4.append(set(T))
    inter = collections.Counter(len(L & set(support(k))) for L in L4 for k in ks)
    pairs = collections.Counter(sum(1 for L in L4 if set(p) <= L) for k in ks if k[0] != b
                                for p in itertools.combinations(support(k), 2))
    print(b, "n_L4", len(L4), "|L ∩ supp k| over all 14 checks:", dict(inter), " #L4 per spreader pair:", dict(pairs))
