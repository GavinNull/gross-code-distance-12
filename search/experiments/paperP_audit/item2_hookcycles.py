"""Item 2: hook-only cycle certificates, recomputed with the audited bulk model (search/theory/B_audit).

For a listed extended logical S (tuple of column keys):
  rigid hook columns = columns whose only realisation is a hook;
  an edge f--g for every reader z touched (over all realisations of all columns of S) only by rigid hook columns
  f != g, each giving exactly one item at z: constraint x_g - x_f = o_f(z) - o_g(z);
  certificate (no flip)   <=> this difference-equality system is inconsistent (a nonzero-holonomy cycle);
  certificate (one flip)  <=> it stays inconsistent after shifting any single edge by +-1.
Also reports the shortest inconsistent cycle length (2 = two-hook) via the cycle basis of a BFS tree.

  uv run python search/experiments/paperP_audit/item2_hookcycles.py <code> <spec> <basis> <list.pkl>
"""
import json, pickle, sys
from collections import Counter, defaultdict, deque
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from search.theory.B_audit.common import Bulk, get_code, load_spec_dict
from search.theory.B_audit.lift import bulk_columns


def edges_of(S, cols):
    touch = defaultdict(set)
    for ci, k in enumerate(S):
        for _, _, items in cols[k]:
            for z, _ in items:
                touch[z].add(ci)
    rigid = {ci for ci, k in enumerate(S) if len(cols[k]) == 1 and cols[k][0][0] == "h"}
    E = []
    for z, cs in touch.items():
        if len(cs) == 2 and cs <= rigid:
            f, g = sorted(cs)
            vf = [v for zz, v in cols[S[f]][0][2] if zz == z]
            vg = [v for zz, v in cols[S[g]][0][2] if zz == z]
            if len(vf) == 1 and len(vg) == 1:
                E.append((f, g, vf[0] - vg[0], z))
    return E


def consistent(E, shift=None):
    adj = defaultdict(list)
    for i, (f, g, w, _) in enumerate(E):
        w = w + (shift[1] if shift and shift[0] == i else 0)
        adj[f].append((g, w)); adj[g].append((f, -w))
    pot = {}
    for s in adj:
        if s in pot:
            continue
        pot[s] = 0; dq = deque([s])
        while dq:
            u = dq.popleft()
            for v, w in adj[u]:
                if v not in pot:
                    pot[v] = pot[u] + w; dq.append(v)
                elif pot[v] != pot[u] + w:
                    return False
    return True


def shortest_bad_cycle(E):
    # brute force over small cycles: length 2 (parallel edges), then BFS-tree fundamental cycles (upper bound)
    by = defaultdict(list)
    for f, g, w, _ in E:
        by[(f, g)].append(w)
    if any(len(set(ws)) > 1 for ws in by.values()):
        return 2
    for L in (3, 4, 5, 6):
        verts = sorted({f for f, g, _, _ in E} | {g for f, g, _, _ in E})
        W = {}
        for (f, g), ws in by.items():
            W[(f, g)] = ws[0]; W[(g, f)] = -ws[0]
        nb = defaultdict(list)
        for (a, b) in W:
            nb[a].append(b)
        def dfs(path, tot):
            u = path[-1]
            if len(path) == L:
                return path[0] in nb[u] and tot + W[(u, path[0])] != 0
            for v in nb[u]:
                if v > path[0] and v not in path and dfs(path + [v], tot + W[(u, v)]):
                    return True
            return False
        if any(dfs([s], 0) for s in verts):
            return L
    return ">6"


def main():
    code, sp, basis, lp = sys.argv[1:5]
    B = Bulk(load_spec_dict(sp), get_code(code), basis)
    cols, zero = bulk_columns(B)
    L = pickle.load(open(ROOT / lp, "rb"))["keys"]
    n0 = n1 = 0; lens = Counter(); lens1 = Counter()
    for S in L:
        E = edges_of(S, cols)
        if consistent(E):
            continue
        n0 += 1
        sl = shortest_bad_cycle(E); lens[sl] += 1
        if all(not consistent(E, (i, s)) for i in range(len(E)) for s in (1, -1)):
            n1 += 1; lens1[sl] += 1
    print(json.dumps({"code": code, "spec": sp, "basis": basis, "list": lp, "n": len(L), "zero_image_hooks": len(zero),
                      "cert_noflip": n0, "cert_oneflip": n1, "shortest_cycle_hist": {str(k): v for k, v in lens.items()},
                      "shortest_cycle_hist_oneflip": {str(k): v for k, v in lens1.items()}}))


if __name__ == "__main__":
    main()
