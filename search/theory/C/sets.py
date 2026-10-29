import collections
from search.experiments.e036_audit.core import checks
from search.experiments.e039.static import multisets
from search.theory.C.involved import involved
ks = checks("bb18"); kidx = {k: i for i, k in enumerate(ks)}
for t in ("DDH2",):
    c = collections.Counter()
    for b in ("Z", "X"):
        for m in multisets("bb18", b, {t}):
            c[tuple(sorted(kidx[k] for k in involved(b, m)))] += 1
    for s, n in sorted(c.items(), key=lambda x: (len(x[0]), x[0])):
        print(len(s), s, [ks[i][0]+str(ks[i][1]) for i in s], n)
