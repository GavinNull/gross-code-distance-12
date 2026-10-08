"""E-020 step 1 cross-check (independent of the SAT encoding in p8legal.py): exhaustive backtracking over the binary
CSP "s_c + k_c(q) != s_d + k_d(q) (mod 8) for every data qubit q and every two checks c, d on q", with forward
checking (domain bitmasks) and MRV variable choice; s of X check 0 fixed to its Fig. 12 value.  Check offsets are read
directly from the Fig. 12 ScheduleSpec (cnot time - prep, mod 8), not via p8legal.checks().

    PYTHONPATH=.:tests uv run python -m search.experiments.e020.p8dfs
"""
from __future__ import annotations

import json
import sys
import time

from search.experiments.e018.gen import SPEC0

D = 8


def main():
    chk = list(SPEC0.x_checks) + list(SPEC0.z_checks)
    n = len(chk)
    off = [{q: (t - c.prep) % D for q, t in c.cnots} for c in chk]
    assert all(sorted(o.values()) == [1, 2, 3, 4, 5, 6] for o in off)
    # binary constraints: for pair (c, d) a set of forbidden differences s_c - s_d
    forb = {}
    on = [[] for _ in range(144)]
    for c in range(n):
        for q in off[c]:
            on[q].append(c)
    for q in range(144):
        for c in on[q]:
            for d in on[q]:
                if c != d:
                    forb.setdefault(c, {}).setdefault(d, set()).add((off[d][q] - off[c][q]) % D)
    # forb[c][d] = set of delta with s_c - s_d = delta forbidden  (s_c + k_c = s_d + k_d <=> s_c - s_d = k_d - k_c)
    nb = {c: list(forb[c].items()) for c in range(n)}
    sols = []
    nodes = [0]
    sys.setrecursionlimit(10000)

    def rec(dom, assigned):
        nodes[0] += 1
        if len(assigned) == n:
            sols.append([assigned[c] for c in range(n)])
            return
        # MRV
        best, bc = None, 99
        for c in range(n):
            if c not in assigned:
                k = bin(dom[c]).count("1")
                if k < bc:
                    best, bc = c, k
                    if k <= 1:
                        break
        if bc == 0:
            return
        c = best
        for v in range(D):
            if not dom[c] >> v & 1:
                continue
            nd = dom[:]
            ok = True
            for d, fs in nb[c]:
                if d in assigned:
                    continue
                mask = nd[d]
                for delta in fs:          # s_c - s_d = delta forbidden -> s_d != v - delta
                    mask &= ~(1 << ((v - delta) % D))
                nd[d] = mask
                if not mask:
                    ok = False
                    break
            if ok:
                assigned[c] = v
                nd[c] = 1 << v
                rec(nd, assigned)
                del assigned[c]

    t0 = time.time()
    dom = [(1 << D) - 1] * n
    dom[0] = 1 << chk[0].prep
    # apply the fixed value
    assigned = {}
    v = chk[0].prep
    for d, fs in nb[0]:
        for delta in fs:
            dom[d] &= ~(1 << ((v - delta) % D))
    assigned[0] = v
    rec(dom, assigned)
    print(f"DFS: {len(sols)} legal assignments, {nodes[0]} nodes, {time.time() - t0:.1f}s")
    ref = json.load(open("results/E-020-gross-perchk-pipeline/p8_legal.json"))
    same = sorted(map(tuple, sols)) == sorted(map(tuple, ref["sols"]))
    print("identical to SAT enumeration:", same)
    json.dump({"n": len(sols), "nodes": nodes[0], "identical_to_sat": same},
              open("results/E-020-gross-perchk-pipeline/p8_dfs.json", "w"))


if __name__ == "__main__":
    main()
