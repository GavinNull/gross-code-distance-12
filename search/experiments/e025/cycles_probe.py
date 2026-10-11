"""E-025 probe: size of the per-logical constraint graphs (bulk frame model, e021.nwfull skeleton) and number of
simple directed cycles, for the colour-symmetric family (orbit reps)."""
import itertools, sys, time
import networkx as nx
import search.experiments.e021.nwfull as NF
from search.experiments.e021.nwsat import Family, parse_sub

F = Family(parse_sub(sys.argv[1] if len(sys.argv) > 1 else "1,2;0,3"))
recs, sk = NF.prepare_full(F, "XZ")
print("reps", len(recs), "skipped", sk)
t0 = time.time()
tot = []
for r in recs[:int(sys.argv[2]) if len(sys.argv) > 2 else None]:
    rc = r["rc"]
    multi = [c for c, l in rc.items() if len(l) > 2]
    for choice in itertools.product(*[list(NF.pairings(sorted(rc[c]))) for c in multi]):
        cls = {}
        for c, l in rc.items():
            if len(l) == 2:
                cls[(c, l[0])] = cls[(c, l[1])] = ("c", c, 0)
        for c, prs in zip(multi, choice):
            for k, (x, y) in enumerate(prs):
                cls[(c, x)] = cls[(c, y)] = ("c", c, k)
        cons = NF.skeleton(F, r, cls)
        G = nx.DiGraph()
        for u, w, kd, _ in cons:
            G.add_edge(w, u)
        mult = {}
        for u, w, kd, _ in cons:
            mult[(w, u)] = mult.get((w, u), 0) + 1
        n = 0
        for cyc in nx.simple_cycles(G):
            if len(cyc) < 3: continue
            m = 1
            for a, b in zip(cyc, cyc[1:] + cyc[:1]):
                m *= mult[(a, b)]
            n += m
        tot.append((len(G), len(cons), len(multi), n))
print("nodes/edges/multi/cycles (first 20):", tot[:20])
import statistics
print("cycles: max", max(t[3] for t in tot), "median", statistics.median(t[3] for t in tot), "sum", sum(t[3] for t in tot),
      "graphs", len(tot), f"{time.time()-t0:.0f}s")
