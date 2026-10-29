"""Question C: size of the set of checks involved in each static witness multiset (spreaders of H slots + readers on
any slot qubit).  usage: uv run python -m search.theory.C.involved"""
import collections
from search.experiments.e036_audit.core import checks, support
from search.experiments.e039.static import multisets
ks = checks("bb18")
def involved(b, heads):
    S = set()
    for h in heads:
        if h[0] == "H":
            S.add(h[1]); qs = [support(h[1])[a] for a in h[2]]
        elif h[0] == "D":
            qs = [h[1]]
        else:
            S.add(h[1]); qs = []
        for q in qs:
            S |= {k for k in ks if k[0] == b and q in support(k)}
    return frozenset(S)
if __name__ == "__main__":
    for t in ("HH", "HHM", "DDH2", "DDH"):
        for b in ("Z",):
            ms = multisets("bb18", b, {t})
            c = collections.Counter(len(involved(b, m)) for m in ms)
            print(t, b, len(ms), sorted(c.items()))
