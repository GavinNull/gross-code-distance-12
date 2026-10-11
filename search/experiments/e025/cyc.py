"""E-025: exact cycle description of the bulk frame model (e021.nwfull skeleton, wrap weights as e024a.cegar.bf_P).

For a modelled weight-11 logical r and a pairing choice, the frame-model constraint system is
    free qubit w read by Z-check nodes c, d:      H_c - H_d <= 1 + floor((t_d(w) - t_c(w)) / P)
    pinned (hook) qubit q of hook check a:        H_c - F_a  = 1 + floor((t_a(q) - t_c(q)) / P)
and the logical LIFTS (model) iff the system is feasible, i.e. iff the constraint graph has no negative cycle.

Qubit-graph reduction (my derivation, E-025): vertices = free qubits of the logical and one vertex F_a per hook check
a (all of a's pinned qubits); every check node joins the two qubits it reads (|Q∩c| = 2 or a pair of a pairing).  A
constraint-graph cycle that passes two readers of one free qubit w consecutively more than once ... is dominated:
the detour c1 -w- c2 -w- c3 has weight 2 + fl(a) + fl(b) >= 1 + fl(a + b) = direct c1 -w- c3.  Hence a negative
cycle exists iff a negative SIMPLE cycle of the qubit multigraph exists (either direction), where the weight of a
directed qubit-graph cycle  v0 -n0- v1 -n1- ... is the sum of its vertex transitions:
    free vertex w, from node p to node n:   1 + floor((t_p(w) - t_n(w)) / P)
    vertex F_a, from p (via pinned q) to n (via pinned q'):  h_n(q') - h_p(q),  h_c(q) = 1 + floor((t_a(q) - t_c(q))/P)
(a node reading two pinned qubits of the same hook gives a self-loop at F_a with weight h(q2) - h(q1) / reverse.)
A term (s, i1, i2) below stands for  s * (1 + floor((t_i2 - t_i1) / P)).
"""
from __future__ import annotations

import itertools

import search.experiments.e021.nwfull as NF


def pairing_classes(r):
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
        yield cls


def cycles_of(F, r, cls):
    """list of directed cycles; each = list of terms (s, i1, i2)."""
    kind, rd = r["kind"], r["rd"]
    vtx = {}          # qubit -> vertex
    hook_item = {}    # pinned qubit -> item of the hook check on it
    for e in r["evs"]:
        if e[0] == "d":
            vtx[e[1]] = ("q", e[1])
        else:
            a = e[1]
            for q in e[2]:
                vtx[q] = ("F", a)
                hook_item[q] = F.item(kind, a, F.label_of(kind, a, q))
    att = {}          # node -> list of (vertex, qubit, item of node on qubit)
    for q in vtx:
        for ty, c, lab in F.touch[q]:
            if ty == rd:
                att.setdefault(cls[(c, q)], []).append((vtx[q], q, F.item(rd, c, lab)))
    edges = []        # (node, (v, q, item), (v', q', item'))
    for n, l in att.items():
        assert len(l) == 2, (n, l)
        edges.append((n, l[0], l[1]))

    def trans(v, p_att, n_att):
        """transition at vertex v from node p (attachment p_att on v) to node n (n_att on v)."""
        if v[0] == "q":
            return [(1, n_att[2], p_att[2])]
        return [(1, n_att[2], hook_item[n_att[1]]), (-1, p_att[2], hook_item[p_att[1]])]

    out = []
    # self loops (only possible at F vertices)
    for n, x, y in edges:
        if x[0] == y[0]:
            assert x[0][0] == "F"
            out.append(trans(x[0], x, y))
            out.append(trans(x[0], y, x))
    # adjacency of the multigraph without loops: vertex -> list of (edge index, my attachment, other attachment)
    adj = {}
    for k, (n, x, y) in enumerate(edges):
        if x[0] == y[0]:
            continue
        adj.setdefault(x[0], []).append((k, x, y))
        adj.setdefault(y[0], []).append((k, y, x))
    order = {v: i for i, v in enumerate(sorted(adj, key=repr))}
    # enumerate directed simple cycles: start at the minimum vertex s; path of (edge, attachment-at-arrival)
    for s in adj:
        so = order[s]

        def dfs(v, path, used_v, used_e):
            for k, mine, other in adj[v]:
                if k in used_e:
                    continue
                w = other[0]
                if w == s:
                    if len(path) == 0 and False:
                        continue
                    cyc = path + [(k, mine, other)]
                    if len(cyc) == 1:
                        continue      # a single non-loop edge is not a cycle
                    # vertex transitions: at s (from last edge to first edge) and at each intermediate vertex
                    terms = []
                    L = len(cyc)
                    for i in range(L):
                        _, m_out, _ = cyc[i]                 # leaving vertex via edge i (attachment on vertex)
                        _, _, o_in = cyc[i - 1]              # arriving at that vertex via edge i-1
                        terms += trans(m_out[0], o_in, m_out)
                    out.append(terms)
                    continue
                if order[w] <= so or w in used_v:
                    continue
                dfs(w, path + [(k, mine, other)], used_v | {w}, used_e | {k})
        dfs(s, [], {s}, set())
    return out


def cycle_sum(terms, t, P):
    return sum(s * (1 + (t[i2] - t[i1]) // P) for s, i1, i2 in terms)


def blocked(cyc_lists, t, P):
    """cyc_lists: list over pairings of list of cycles.  Model-blocked iff every pairing has a negative cycle."""
    return all(any(cycle_sum(c, t, P) < 0 for c in cl) for cl in cyc_lists)


def rec_cycles(F, r):
    return [cycles_of(F, r, cls) for cls in pairing_classes(r)]
