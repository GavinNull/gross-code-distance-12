"""Difference-constraint form of the bulk lift (second, independent exact solver) and its negative-cycle certificates.

Variables: one integer y(j, z) per column j of S and reader z it hits (the step index at which z sees column j).
  * hook realisation: y(j, z) = x_j + o_j(z)                       (rigid; offsets from the writer's timing)
  * data realisation on q: the cut patterns are exactly the integer vectors with
        lo(z, z') <= y(j, z) - y(j, z') <= hi(z, z')                 (checked against the enumerated options)
  * reader z hit by exactly two items: y(f, z) = y(g, z); hit by 2m items: a perfect matching (branched);
  * a readout flip at z adds two items t, t + 1 with t free (branched).
For a fixed choice of realisations, matchings and flip readers the system is a difference-constraint system, feasible
iff its constraint graph has no negative cycle (Bellman-Ford).  So: S lifts in the bulk iff some branch has no negative
cycle; when no branching is needed the obstruction is ONE cycle whose offset sum (holonomy) exceeds the slack of the
data columns it passes through.

  uv run python -m search.theory.B.dc --code gross --spec search/experiments/e032/u11_spec.json --basis Z \
      --list results/E-032-gross-short-period/w11_X_all_A1A2A3B3B1B2.pkl
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import pickle
import time

from search.theory.B.bulk import ROOT, Sched, code_mats, load_spec, _matchings
from search.theory.B.enum import enumerate_w


def real_constraints(sch, real):
    """returns (items, edges): items = {z: [node,...]} (one node per step item), edges = [(u, v, w)] meaning
    y_v - y_u <= w.  Node names are local tuples."""
    opts = sch.options(real)
    if real[0] == "h":
        o = opts[0]
        items, E = {}, []
        for z, offs in o.items():
            items[z] = []
            for t, off in enumerate(offs):
                n = ("y", z, t)
                items[z].append(n)
                E.append((("x",), n, off)); E.append((n, ("x",), -off))
        return items, E, True
    zs = sorted(opts[0])
    items = {z: [("y", z, 0)] for z in zs}
    E = []
    for z, z2 in itertools.permutations(zs, 2):
        diffs = [o[z][0] - o[z2][0] for o in opts]
        E.append((("y", z2, 0), ("y", z, 0), max(diffs)))     # y_z - y_z2 <= max
    # exactness: the integer solutions modulo shift are exactly the options
    lo = {(z, z2): min(o[z][0] - o[z2][0] for o in opts) for z, z2 in itertools.permutations(zs, 2)}
    hi = {(z, z2): max(o[z][0] - o[z2][0] for o in opts) for z, z2 in itertools.permutations(zs, 2)}
    rng = range(-3, 4)
    sols = set()
    for v in itertools.product(rng, repeat=len(zs) - 1):
        y = dict(zip(zs, (0,) + v))
        if all(lo[p] <= y[p[0]] - y[p[1]] <= hi[p] for p in lo):
            m = min(y.values())
            sols.add(tuple(y[z] - m for z in zs))
    optset = {tuple(o[z][0] - min(o[w][0] for w in zs) for z in zs) for o in opts}
    return items, E, sols == optset


def neg_cycle(nodes, E):
    dist = {n: 0 for n in nodes}
    for _ in range(len(nodes) + 1):
        ch = False
        for u, v, w in E:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w; ch = True
        if not ch:
            return False
    return True


def lift_dc(S, cols, sch, flips=0, stats=None):
    per_col = []
    for j, k in enumerate(S):
        alts = []
        for r in cols[k]:
            it, E, exact = real_constraints(sch, r)
            assert exact, ("data patterns not a difference-constraint polytope", r)
            alts.append((it, E))
        per_col.append(alts)
    branches = 1
    for alts in per_col:
        branches *= len(alts)
    if stats is not None:
        stats["realisation_branches>1"] += branches > 1
    for choice in itertools.product(*[range(len(a)) for a in per_col]):
        nodes, E = set(), []
        at = collections.defaultdict(list)
        for j, c in enumerate(choice):
            it, Ej = per_col[j][c]
            ren = lambda n, j=j: (j,) + n
            for u, v, w in Ej:
                E.append((ren(u), ren(v), w)); nodes |= {ren(u), ren(v)}
            for z, ns in it.items():
                at[z] += [ren(n) for n in ns]
                nodes |= {ren(n) for n in ns}
        flip_sets = [()] + ([(z,) for z in at] if flips else [])
        for fz in flip_sets:
            at2 = {z: list(v) for z, v in at.items()}
            E2, nodes2 = list(E), set(nodes)
            for z in fz:
                t0, t1 = ("t", z, 0), ("t", z, 1)
                at2[z] += [t0, t1]
                E2 += [(t0, t1, 1), (t1, t0, -1)]
                nodes2 |= {t0, t1}
            if any(len(v) % 2 for v in at2.values()):
                continue
            multi = [z for z, v in at2.items() if len(v) > 2]
            if stats is not None and not fz:
                stats["reader_branching"] += bool(multi)
            fixed = []
            for z, v in at2.items():
                if len(v) == 2:
                    fixed += [(v[0], v[1], 0), (v[1], v[0], 0)]
            for ms in itertools.product(*[list(_matchings(at2[z])) for z in multi]):
                E3 = E2 + fixed
                for m in ms:
                    for a, b in m:
                        E3 += [(a, b, 0), (b, a, 0)]
                if not neg_cycle(nodes2, E3):
                    return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--basis", default="Z")
    ap.add_argument("--list", required=True)
    ap.add_argument("--flips", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    sch = Sched(load_spec(a.spec), code_mats(a.code), a.basis)
    cols, _ = sch.ext()
    if a.list.startswith("enum:"):
        L = enumerate_w(sch, cols, int(a.list[5:]))
    else:
        L = pickle.load(open(ROOT / a.list, "rb"))["keys"]
    if a.limit:
        L = L[:a.limit]
    st = collections.Counter()
    t0 = time.time()
    lifted = [i for i, S in enumerate(L) if lift_dc(S, cols, sch, a.flips, st)]
    res = {"spec": a.spec, "basis": a.basis, "list": a.list, "n": len(L), "flips": a.flips, "dc_lifted": len(lifted),
           "first": lifted[:10], "no_branching": len(L) - st["realisation_branches>1"] - 0,
           "stats": dict(st), "sec": round(time.time() - t0, 1)}
    print(json.dumps(res))
    if a.out:
        with open(ROOT / a.out, "a") as f:
            f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
