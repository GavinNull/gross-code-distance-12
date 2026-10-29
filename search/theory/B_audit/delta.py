"""Item 2: the cochain delta(c, z) (index at which reader z first sees writer c's instance-0 deposits on shared
qubits), the pairing property (Lemma 2), and whether delta is a coboundary b_z - a_c (spanning-forest test: fix
potentials on a BFS forest, count edges violating them; coboundary iff 0 violations).

  uv run python -m search.theory.B_audit.delta gross search/experiments/e032/u11_spec.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict, deque

from search.theory.B_audit.common import Bulk, get_code, load_spec_dict


def analyse(B: Bulk):
    multi, pairing_bad, delta, qsize = 0, 0, {}, Counter()
    for c, (order, tm) in enumerate(B.wr):
        S = set(order)
        for z, (ro, _) in enumerate(B.rd):
            Q = S & set(ro)
            if not Q:
                continue
            qsize[len(Q)] += 1
            vals = Counter(B.sig(z, q, tm[q]) for q in Q)
            if any(v % 2 for v in vals.values()):
                pairing_bad += 1
            if len(vals) > 1:
                multi += 1
            delta[(c, z)] = min(vals)
    # coboundary test (only meaningful when single-valued)
    adj = defaultdict(list)
    for (c, z), v in delta.items():
        adj[("X", c)].append((("Z", z), v))
        adj[("Z", z)].append((("X", c), -v))
    pot, viol = {}, 0
    for s in list(adj):
        if s in pot:
            continue
        pot[s] = 0
        dq = deque([s])
        while dq:
            u = dq.popleft()
            for w, v in adj[u]:
                if w not in pot:
                    pot[w] = pot[u] + v
                    dq.append(w)
    for (c, z), v in delta.items():
        if pot[("Z", z)] - pot[("X", c)] != v:
            viol += 1
    return {"pairs": len(delta), "overlap_sizes": dict(qsize), "pairing_violations": pairing_bad,
            "multi_valued_pairs": multi, "delta_values": dict(Counter(delta.values())),
            "coboundary": viol == 0 and multi == 0, "violating_edges": viol}


def main():
    codename, sp = sys.argv[1], sys.argv[2]
    code = get_code(codename)
    spec = load_spec_dict(sp)
    out = {"spec": sp}
    for b in ("Z", "X"):
        out[b] = analyse(Bulk(spec, code, b))
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
