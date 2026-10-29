"""Hook-cycle criterion (HC).

For an extended logical S: rigid columns = columns all of whose realisations are hooks with one and the same pattern
(no data realisation).  A reader z is private to rigid columns f, g if exactly two columns of S hit z oddly, namely f
and g, each with a single step item: o_f(z), o_g(z).  Bulk undetectability forces  x_f + o_f(z) = x_g + o_g(z).
HC(S): the graph of these equalities is inconsistent (some cycle has nonzero holonomy) -> S cannot lift (bulk, hence
every R under the window lemma).  HC1(S): it stays inconsistent after deleting any single edge -> S cannot lift even
with one extra zero-image fault (a readout flip changes only one reader's constraint).
Reports, per list, how many logicals satisfy HC / HC1, the shortest inconsistent cycle length and its holonomy.

  uv run python -m search.theory.B.hc --code gross --spec search/experiments/e032/u11_spec.json --basis Z \
      --list results/E-032-gross-short-period/w10_X_all_A1A2A3B3B1B2.pkl
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import pickle

import numpy as np

from search.theory.B.bulk import ROOT, Sched, code_mats, load_spec
from search.theory.B.enum import enumerate_w


def edges_of(S, cols, sch):
    nh = sch.H.shape[0]
    hitters = collections.defaultdict(list)
    for j, k in enumerate(S):
        for z in np.flatnonzero(np.frombuffer(k, np.uint8)[:nh]):
            hitters[int(z)].append(j)
    rigid = {}
    for j, k in enumerate(S):
        reals = cols[k]
        if any(r[0] == "d" for r in reals):
            continue
        pats = {tuple(sorted(sch.options(r)[0].items())) for r in reals}
        if len(pats) == 1:
            rigid[j] = dict(next(iter(pats)))
    E = []
    for z, hs in hitters.items():
        if len(hs) == 2 and all(h in rigid for h in hs):
            f, g = hs
            of, og = rigid[f].get(z, ()), rigid[g].get(z, ())
            if len(of) == 1 and len(og) == 1:
                E.append((f, g, of[0] - og[0], z))      # x_f - x_g = og - of  ->  label d = of - og: x_g = x_f + d
    return E, rigid


def inconsistent(E, skip=None):
    pot = {}
    adj = collections.defaultdict(list)
    for e, (f, g, d, z) in enumerate(E):
        if e == skip:
            continue
        adj[f].append((g, d)); adj[g].append((f, -d))
    for s in list(adj):
        if s in pot:
            continue
        pot[s] = 0
        st = [s]
        while st:
            u = st.pop()
            for w, d in adj[u]:
                if w not in pot:
                    pot[w] = pot[u] + d; st.append(w)
                elif pot[w] != pot[u] + d:
                    return True
    return False


def shortest_bad_cycle(E):
    """smallest k such that some k-subset of edges forms an inconsistent cycle (k <= 6), with its holonomy."""
    for k in range(2, 7):
        for sub in itertools.combinations(range(len(E)), k):
            es = [E[i] for i in sub]
            deg = collections.Counter()
            for f, g, _, _ in es:
                deg[f] += 1; deg[g] += 1
            if any(v != 2 for v in deg.values()):
                continue
            if inconsistent(es):
                f0, g0, d0, _ = es[0]
                adj = collections.defaultdict(list)
                for f, g, d, _ in es[1:]:
                    adj[f].append((g, d)); adj[g].append((f, -d))
                pot, stck = {f0: 0}, [f0]
                while stck:
                    u = stck.pop()
                    for w, d in adj[u]:
                        if w not in pot:
                            pot[w] = pot[u] + d; stck.append(w)
                h = pot[g0] - pot[f0] - d0
                return k, abs(h)
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--basis", default="Z")
    ap.add_argument("--list", required=True)
    ap.add_argument("--cycles", type=int, default=1)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    sch = Sched(load_spec(a.spec), code_mats(a.code), a.basis)
    cols, _ = sch.ext()
    if a.list.startswith("enum:"):
        L = enumerate_w(sch, cols, int(a.list[5:]))
    else:
        L = pickle.load(open(ROOT / a.list, "rb"))["keys"]
    st = collections.Counter()
    fails = []
    for i, S in enumerate(L):
        E, rigid = edges_of(S, cols, sch)
        hc = inconsistent(E)
        hc1 = hc and all(inconsistent(E, skip=e) for e in range(len(E)))
        st["HC"] += hc; st["HC1"] += hc1
        st[f"rigid={len(rigid)}"] += 1
        if not hc:
            fails.append(i)
        elif a.cycles:
            k, h = shortest_bad_cycle(E)
            st[f"cycle_len={k},|hol|={h}"] += 1
    res = {"spec": a.spec, "basis": a.basis, "list": a.list, "n": len(L), "w": len(L[0]) if L else 0,
           "stats": dict(sorted(st.items())), "HC_fail_first": fails[:10]}
    print(json.dumps(res))
    if a.out:
        with open(ROOT / a.out, "a") as f:
            f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
