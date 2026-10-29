"""Question C: reader structure of weight-4 logical residuals (Z memory: X errors, readers = Z checks)."""
import itertools, collections, numpy as np
from search.experiments.e036_audit.core import checks, support, observables
ks = checks("bb18")
b = "Z"
readers = [k for k in ks if k[0] == b]; spreaders = [k for k in ks if k[0] != b]
obs = observables("bb18", b)
L4 = []
for S in itertools.combinations(range(18), 4):
    if all(len(set(S) & set(support(k))) % 2 == 0 for k in readers):
        v = np.zeros(18, int); v[list(S)] = 1
        if (obs @ v % 2).any(): L4.append(S)
shape = collections.Counter()
for L in L4:
    cov = []
    for g in readers:
        I = tuple(sorted(set(L) & set(support(g))))
        if I: cov.append(I)
    sp = [tuple(sorted(set(L) & set(support(k)))) for k in spreaders if set(L) & set(support(k))]
    zdeg = [sum(q in support(g) for g in readers) for q in L]
    shape[(tuple(sorted(len(c) for c in cov)), tuple(sorted(zdeg)))] += 1
    if len(shape) < 4: print(L, "readers", cov, "spreaders", sp, "zdeg", zdeg)
print(shape)
