"""E-037 audit: empirical soundness test of the constraints added outside the proof.

  uv run python search/experiments/e037_audit/sat_test.py OPB SOLS.json

OPB = a certified W = d-1 instance; SOLS = all weight-d undetectable logicals of the same DEM (run_mincc --save, my
independent search; d is the true minimum there).  Every one of them is a minimum-weight solution, so by the argument
in the audit every one must satisfy every cardinality and blocking constraint of the OPB, and at least one member of
every translation class must satisfy the symmetry-breaking clauses (contains the representative of the first class
it meets).  A violation would be a counterexample to the E-037 argument (or to its implementation).
"""
import json
import re
import sys
from collections import defaultdict

TOK = re.compile(r"(-?\d+)\s+(~?)([a-z]+)(\d+)")


def main():
    opb, solf = sys.argv[1], sys.argv[2]
    S = json.load(open(solf))
    D = [tuple(d) for d in S["D"]]
    idx = {d: j for j, d in enumerate(D)}
    coldet = defaultdict(list)
    cards, blocks, h1, sb = [], [], {}, {}
    for ln in open(opb):
        if ln.startswith("*"):
            continue
        body, rel, rhs = re.match(r"^(.*?)\s*(=|>=)\s*(-?\d+)\s*;$", ln.strip()).groups()
        t = [(int(c), n == "~", v, int(i)) for c, n, v, i in TOK.findall(body)]
        a_ids = re.findall(r"a(\d+)_0", body)
        if rel == "=" and a_ids:
            r = int(a_ids[0]) - 1
            for c, ng, v, i in t:
                if v == "x":
                    coldet[i].append(r)
            continue
        if rel != ">=":
            continue
        vs = {v for _, _, v, _ in t}
        if vs == {"x"} and all(c == -1 for c, *_ in t) and len(t) < len(D):
            cards.append((-int(rhs), [i for *_, i in t]))
        elif vs == {"x"} and all(ng for _, ng, _, _ in t):
            blocks.append([i for *_, i in t])
        elif vs == {"x", "h"} and len(t) == 2 and any(v == "x" and ng for _, ng, v, _ in t):
            h1[[i for _, _, v, i in t if v == "x"][0]] = [i for _, _, v, i in t if v == "h"][0]
        elif "h" in vs and any(v == "h" and ng for _, ng, v, _ in t) and "x" in vs:
            o = [i for _, ng, v, i in t if v == "h" and ng][0]
            sb[o] = [i for _, _, v, i in t if v == "x"][0]
    mp = {x: idx[tuple(sorted(ds))] for x, ds in coldet.items()}
    inv = {j: x for x, j in mp.items()}
    sols = [frozenset(inv[j] for j in s) for s in S["sols"]]      # in OPB variable ids
    viol_c = sum(1 for s in sols for b, T in cards if len(s.intersection(T)) > b)
    viol_b = sum(1 for s in sols for T in blocks if s.issuperset(T))
    nsb = 0
    for s in sols:
        first = min(h1[x] for x in s)
        if sb[first] in s:
            nsb += 1
    # classes of solutions under the group: members of a class share the multiset of class labels; a coarse but
    # sufficient check is that the SB-satisfying solutions exist and every class label pattern is represented
    pat = defaultdict(lambda: [0, 0])
    for s in sols:
        key = tuple(sorted(h1[x] for x in s))
        first = min(key)
        pat[key][0] += 1
        pat[key][1] += sb[first] in s
    unrep = sum(1 for k, (a, b) in pat.items() if b == 0)
    out = dict(opb=opb, nsols=len(sols), minw=S["minw"], ncards=len(cards), nblocks=len(blocks),
               card_violations=viol_c, block_violations=viol_b, sb_satisfying=nsb, orbit_patterns=len(pat),
               patterns_without_sb_member=unrep,
               verdict="OK" if viol_c == 0 and viol_b == 0 and unrep == 0 and nsb > 0 else "COUNTEREXAMPLE")
    print(json.dumps(out))


if __name__ == "__main__":
    main()
