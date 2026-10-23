"""Claim 1: 6-cycle X9->Z17->X12->Z20->X22->Z24->X9 and the wraparound straddle, read off the stim circuit itself
(R = 3, Z basis, noiseless), instances delimited by the ancilla's own reset / measurement ticks."""
import collections, json, sys
import networkx as nx
sys.path.insert(0, __import__("os").path.dirname(__file__))
from g_common import *


def instances(spec_json, R):
    c = circ(spec_json, R, "Z", noisy=False)
    cx, meas, reset = tick_tables(c)
    inst = {}   # (typ, i, j) -> dict(reset, meas, cnots=[(tick, q)])
    for typ, base in (("X", N), ("Z", N + NC)):
        for i in range(NC):
            a = base + i
            ms = sorted(meas[a]); rs = sorted(reset[a])
            evs = sorted([(t, q) for (x, y), ts in cx.items() for t in ts
                          for q in ([y] if x == a else [x] if y == a else [])])
            for j, m in enumerate(ms):
                r = max(x for x in rs if x < m)
                inst[(typ, i, j)] = dict(reset=r, meas=m, cnots=[e for e in evs if r < e[0] < m])
    return c, inst


def graph(inst):
    per_q = collections.defaultdict(list)
    for k, v in inst.items():
        for t, q in v["cnots"]: per_q[q].append((t, k))
    G = nx.DiGraph(); lab = {}
    for q, lst in per_q.items():
        lst.sort()
        for a in range(len(lst)):
            for b in range(a + 1, len(lst)):
                (t1, u), (t2, v) = lst[a], lst[b]
                assert t1 != t2
                if u[0] != v[0]:
                    G.add_edge(u, v); lab.setdefault((u, v), []).append((q, t1, t2))
    return G, lab


out = {}
for name, sj in (("u11", U11), ("segctl", segctl())):
    R = 3
    c, inst = instances(sj, R)
    G, lab = graph(inst)
    mixed = [s for s in nx.strongly_connected_components(G) if len({x[0] for x in s}) > 1]
    two = sum(1 for (u, v) in lab if (v, u) in lab) // 2
    out[name] = dict(nodes=G.number_of_nodes(), edges=G.number_of_edges(), mixed_SCCs=len(mixed),
                     mixed_SCC_sizes=sorted(collections.Counter((len(s), tuple(sorted(collections.Counter(x[0] for x in s).items())),
                                                                 tuple(sorted({x[2] for x in s}))) for s in mixed).items()),
                     two_cycles=two)
    if name == "u11":
        cyc = [("X", 9), ("Z", 17), ("X", 12), ("Z", 20), ("X", 22), ("Z", 24)]
        rows = []
        for j in range(R):
            ok = True; es = []
            for a, b in zip(cyc, cyc[1:] + cyc[:1]):
                u, v = (*a, j), (*b, j)
                L = lab.get((u, v))
                ok &= bool(L); es.append([f"{a[0]}{a[1]}->{b[0]}{b[1]}", L])
            rows.append(dict(round=j, closed=ok, edges=es))
        out[name]["cycle_by_round"] = rows
        out[name]["cycle_instances_round1"] = {f"{k[0]}{k[1]}": inst[(*k, 1)] for k in cyc}
        # straddle: for each Z instance on the cycle, its CNOT ticks relative to the X instances it touches
        st = {}
        for z in [k for k in cyc if k[0] == "Z"]:
            zi = inst[(*z, 1)]
            st[f"Z{z[1]}"] = dict(reset=zi["reset"], first_cnot=zi["cnots"][0][0], other_cnots=[t for t, _ in zi["cnots"][1:]],
                                  meas=zi["meas"], X_round1_reset=inst[("X", 9, 1)]["reset"],
                                  X_round1_cnots=[t for t, _ in inst[("X", 9, 1)]["cnots"]])
        out[name]["straddle"] = st
        # period boundary in ticks: X reset ticks
        out[name]["X_reset_ticks"] = sorted({inst[("X", i, j)]["reset"] for i in range(NC) for j in range(R)})
        out[name]["Z_reset_ticks"] = sorted({inst[("Z", i, j)]["reset"] for i in range(NC) for j in range(R)})
        # data qubit cyclic sequences (from spec, mod 11)
        P = sj["period"]; seq = collections.Counter()
        for q in range(N):
            ev = sorted([(t % P, "X") for ch in sj["x_checks"] for a, t in ch["cnots"] if a == q] +
                        [(t % P, "Z") for ch in sj["z_checks"] for a, t in ch["cnots"] if a == q])
            seq[tuple(ev)] += 1
        out[name]["data_sequences"] = [[list(map(list, k)), v] for k, v in seq.items()]
print(json.dumps(out, indent=1, default=str))
json.dump(out, open(OUT + "/g1_cycle.json", "w"), indent=1, default=str)
