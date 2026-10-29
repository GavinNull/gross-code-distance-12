"""Cor. 7 spot check: count listed logicals that have a two-hook certificate (two rigid single-realisation hook
columns f, g and two readers z, z' that no other column of S can touch in any realisation, each receiving exactly one
item from f and one from g, with holonomy h = [o_f(z)-o_g(z)] - [o_f(z')-o_g(z')] != 0; |h| >= 2 survives one flip).

  uv run python -m search.theory.B_audit.twohook gross search/experiments/e032/u11_spec.json Z <list.pkl>
"""
import json
import pickle
import sys
from collections import Counter, defaultdict

from search.theory.B_audit.common import ROOT, Bulk, get_code, load_spec_dict
from search.theory.B_audit.lift import bulk_columns


def main():
    name, sp, basis, lp = sys.argv[1:5]
    B = Bulk(load_spec_dict(sp), get_code(name), basis)
    cols, _ = bulk_columns(B)
    L = pickle.load(open(ROOT / lp, "rb"))["keys"]
    hol = Counter()
    example = None
    for si, S in enumerate(L):
        touch = defaultdict(set)
        for ci, k in enumerate(S):
            for _, _, items in cols[k]:
                for z, _ in items:
                    touch[z].add(ci)
        rigid = [ci for ci, k in enumerate(S) if len(cols[k]) == 1 and cols[k][0][0] == "h"]
        best = 0
        for a in range(len(rigid)):
            for b in range(a + 1, len(rigid)):
                f, g = rigid[a], rigid[b]
                itf = defaultdict(list); itg = defaultdict(list)
                for z, v in cols[S[f]][0][2]:
                    itf[z].append(v)
                for z, v in cols[S[g]][0][2]:
                    itg[z].append(v)
                diffs = [itf[z][0] - itg[z][0] for z in touch if touch[z] == {f, g}
                         and len(itf[z]) == 1 and len(itg[z]) == 1]
                if len(diffs) >= 2:
                    h = max(diffs) - min(diffs)
                    if h > best:
                        best = h
                        if si == 0:
                            example = {"f": cols[S[f]][0][1], "g": cols[S[g]][0][1], "holonomy": h}
        hol[best] += 1
    print(json.dumps({"spec": sp, "basis": basis, "list": lp, "n": len(L),
                      "max_two_hook_holonomy_histogram": dict(sorted(hol.items())), "example_list0": example}))


if __name__ == "__main__":
    main()
