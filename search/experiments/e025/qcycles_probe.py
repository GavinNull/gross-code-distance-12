"""E-025 probe: simple cycles in the QUBIT graph (vertices = free data qubits of the logical + F (all pinned hook
qubits), edges = Z-check nodes joining the two qubits they read).  Non-dominated negative cycles of the constraint
graph are exactly these (a detour c1 -w- c2 -w- c3 through one qubit is dominated by c1 -w- c3 since
floor(a)+floor(b)+1 >= floor(a+b))."""
import itertools, sys, time, statistics
import networkx as nx
import search.experiments.e021.nwfull as NF
from search.experiments.e021.nwsat import Family, parse_sub


def qgraph(F, r, cls):
    """returns list of edges (node, v1, v2) where node = check node, v = qubit or 'F'; plus self-loops at F."""
    evs = r["evs"]
    pinned = set()
    for e in evs:
        if e[0] == "h":
            pinned |= set(e[2])
    rd = r["rd"]
    ends = {}
    for e in evs:
        qs = [e[1]] if e[0] == "d" else list(e[2])
        for q in qs:
            for ty, c, lab in F.touch[q]:
                if ty == rd:
                    ends.setdefault(cls[(c, q)], []).append("F" if q in pinned else q)
    return ends


if __name__ == "__main__":
    F = Family(parse_sub(sys.argv[1] if len(sys.argv) > 1 else "1,2;0,3"))
    recs, sk = NF.prepare_full(F, "XZ")
    t0 = time.time(); tot = []
    for r in recs:
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
            ends = qgraph(F, r, cls)
            G = nx.MultiGraph()
            loops = 0
            for nd, vs in ends.items():
                assert len(vs) == 2, vs
                if vs[0] == vs[1]:
                    loops += 1; continue
                G.add_edge(vs[0], vs[1], key=nd)
            n = sum(1 for _ in nx.simple_cycles(G))
            tot.append((G.number_of_nodes(), G.number_of_edges(), loops, n))
    print("first", tot[:12])
    print("graphs", len(tot), "cycles max", max(t[3] for t in tot), "median", statistics.median(t[3] for t in tot),
          "sum", sum(t[3] for t in tot), "Fdeg/loops max", max(t[2] for t in tot), f"{time.time()-t0:.0f}s")
