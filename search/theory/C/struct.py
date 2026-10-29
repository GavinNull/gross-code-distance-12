"""Question C: basic structure of the 14 measured checks of bb18 (degrees, overlaps)."""
from search.experiments.e036_audit.core import checks, support
ks = checks("bb18")
deg = {q: [k for k in ks if q in support(k)] for q in range(18)}
for q in range(18):
    print(q, len(deg[q]), "X", sum(k[0]=="X" for k in deg[q]), "Z", sum(k[0]=="Z" for k in deg[q]))
print("same-type overlaps / X-Z overlaps")
for i,k in enumerate(ks):
    row=[]
    for l in ks:
        row.append(len(set(support(k))&set(support(l))))
    print(k, support(k), row)
