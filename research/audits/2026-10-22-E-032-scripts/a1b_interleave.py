"""A1b: is the circuit segmentable?  Instance precedence graph: node = check instance (typ, check, round);
edge u -> v if on a shared data qubit u's CNOT comes before v's CNOT.  A segmented circuit (blocks of whole X
instances and whole Z instances, any re-ordering of commuting gates allowed) needs a block index b(u) with
b(u) <= b(v) on every edge and b(u) != b(v) when types differ.  So: (i) an SCC containing both types => not
segmentable; (ii) otherwise the max number of type switches along a path lower-bounds (#blocks - 1).
Usage: a1b_interleave.py SPEC R"""
import sys, json, collections
sys.path.insert(0, "research/audits/2026-10-22-E-032-scripts")
import networkx as nx
from alib32 import *

spec = load_spec(sys.argv[1]); R = int(sys.argv[2])
D, st, info, nl, sg = my_unroll(spec, R)
ev = collections.defaultdict(list)
for k, (dm, offs) in info.items():
    for j in range(R):
        for o, a in offs:
            ev[a].append((st[k] + D * j + o, (k[0], k[1], j)))
G = nx.DiGraph()
for a, lst in ev.items():
    lst.sort()
    # only X-CNOT / Z-CNOT pairs on a qubit fail to commute (same-type CNOTs on a data qubit commute), so
    # precedence edges are added for every cross-type pair, never for same-type pairs
    for i1 in range(len(lst)):
        for i2 in range(i1 + 1, len(lst)):
            (t1, u), (t2, v) = lst[i1], lst[i2]
            assert t1 < t2
            if u[0] != v[0]:
                G.add_edge(u, v)
mixed = [c for c in nx.strongly_connected_components(G) if len({x[0] for x in c}) > 1]
out = {"spec": sys.argv[1], "R": R, "nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
       "mixed_type_SCCs": len(mixed), "largest_mixed_SCC": max((len(c) for c in mixed), default=0)}
if not mixed:
    C = nx.condensation(G)
    best = {}
    for n in nx.topological_sort(C):
        typ = next(iter(C.nodes[n]["members"]))[0]
        b = 0
        for p in C.predecessors(n):
            pt, pv = best[p]
            b = max(b, pv + (pt != typ))
        best[n] = (typ, b)
    out["max_type_switches_on_a_path"] = max(v for _, v in best.values())
    out["segmented_would_allow_at_most"] = 2 * R
else:
    # shortest witness cycle through both types
    c = min(mixed, key=len)
    H = G.subgraph(c)
    cyc = nx.find_cycle(H)
    out["witness_cycle"] = [str(e) for e in cyc][:12]
    out["witness_cycle_len"] = len(cyc)
print(json.dumps(out, indent=1))
