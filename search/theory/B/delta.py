"""The precedence cochain delta(c, z) of a schedule and its cohomology class.

delta(c, z) = step index (instance of reader z) at which reader z first sees the deposits of writer c's instance 0 on
their shared qubits (pairing lemma: equal on all shared qubits for |Q| = 2; we report the multiset).  The schedule is
bulk-segmentable iff delta is a coboundary, delta(c, z) = b_z - a_c.  We try to build potentials by BFS on the overlap
graph and report a closed walk of nonzero holonomy if they do not exist.  For translation-invariant BB schedules we also
print delta as a function of the term pair (i, j) of the offset z - c = A_i + B_j.

  uv run python -m search.theory.B.delta --code gross --spec search/experiments/e032/u11_spec.json
"""
from __future__ import annotations

import argparse
import collections
import json

from search.theory.B.bulk import Sched, code_mats, load_spec


def analyse(sch):
    dl = sch.delta()
    multi = {k: v for k, v in dl.items() if len(set(v)) > 1}
    d = {k: v[0] for k, v in dl.items()}
    adj = collections.defaultdict(list)
    for (c, z), v in d.items():
        adj[("X", c)].append((("Z", z), v))
        adj[("Z", z)].append((("X", c), -v))
    pot, par = {}, {}
    conflict = None
    nconf = 0
    for s in adj:
        if s in pot:
            continue
        pot[s] = 0
        par[s] = None
        dq = collections.deque([s])
        while dq:
            u = dq.popleft()
            for w, v in adj[u]:
                # potential convention: pot[Z] - pot[X] = delta
                want = pot[u] + v
                if w not in pot:
                    pot[w] = want; par[w] = u; dq.append(w)
                elif pot[w] != want:
                    nconf += 1
                    if conflict is None:
                        conflict = (u, w, pot[w] - want)
    walk = None
    if conflict:
        u, w, h = conflict
        walk = {"edge": [u, w], "holonomy": h}
    vals = collections.Counter(d.values())
    return {"pairs": len(d), "multi_valued": len(multi), "delta_values": dict(vals),
            "pairing_violations": len(sch.pairing_ok()), "coboundary": nconf == 0, "conflict_edges": nconf,
            "sample_nonzero_holonomy": walk}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--spec", required=True)
    a = ap.parse_args()
    mats = code_mats(a.code)
    out = {"spec": a.spec}
    for b in ("Z", "X"):
        sch = Sched(load_spec(a.spec), mats, b)
        out[b] = analyse(sch)
    print(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
