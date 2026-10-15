"""Auditor (E-029 part 2): expand enum SOL lines on the ext instance by the 24 translations and compare with the
published 4224 list.  Own code: translation action computed from the column supports and the code matrices in
release/zenodo/data/code/gross_code.json; columns matched to the published extended code by (H, L) image.

    uv run python research/audits/2026-10-15-E-029-scripts/extcompare.py BASIS SOLFILE INSTMETA
"""
import json
import sys

import numpy as np

REL = "release/zenodo/data"
basis, solf, metaf = sys.argv[1], sys.argv[2], sys.argv[3]
code = json.load(open(f"{REL}/code/gross_code.json"))
n = code["n"]


def mat(rows):
    A = np.zeros((len(rows), n), np.uint8)
    for i, r in enumerate(rows):
        A[i, r] = 1
    return A


H, L = (mat(code["HZ"]), mat(code["LZ"])) if basis == "Z" else (mat(code["HX"]), mat(code["LX"]))


def key(sup):
    v = np.zeros(n, np.uint8)
    v[list(sup)] = 1
    return tuple(np.nonzero(H @ v % 2)[0]), tuple(np.nonzero(L @ v % 2)[0])


pub = json.load(open(f"{REL}/extended_code/extended_code_{basis}_memory.json"))
pkey = {(tuple(c["H"]), tuple(c["L"])): c["index"] for c in pub["columns"]}
assert len(pkey) == len(pub["columns"])
meta = json.load(open(metaf))
mycols = meta["columns"]
# column map experimenter-instance -> published index (by image)
cmap = [pkey[(tuple(c["H"]), tuple(c["L"]))] for c in mycols]
assert len(set(cmap)) == len(cmap) == len(pub["columns"]), "column sets differ"
# check images agree with code matrices
assert all(key(c["support"]) == (tuple(c["H"]), tuple(c["L"])) for c in mycols)


def tq(q, a, b):
    blk, i = divmod(q, 72)
    x, y = divmod(i, 6)
    return blk * 72 + ((x + a) % 12) * 6 + (y + b) % 6


group = [tuple(g) for g in pub["translation_group"]]
act = {}
for g in group:
    act[g] = [pkey[key([tq(q, *g) for q in c["support"]])] for c in mycols]
sols = set()
nlines = 0
for ln in open(solf):
    if ln.startswith("SOL"):
        nlines += 1
        ids = [int(x) for x in ln.split(":")[1].split()]
        for g in group:
            sols.add(frozenset(act[g][j] for j in ids))
lst = json.load(open(f"{REL}/logicals/weight11_logicals_{basis}_memory.json"))
pubset = {frozenset(e["columns"]) for e in lst["logicals"]}
# re-verify every expanded solution against the published matrices
pc = {c["index"]: c for c in pub["columns"]}
bad = 0
for s in sols:
    h, l = set(), set()
    for j in s:
        h ^= set(pc[j]["H"]); l ^= set(pc[j]["L"])
    bad += bool(h) or not l or len(s) != 11
print(json.dumps(dict(basis=basis, sol_lines=nlines, expanded=len(sols), published=len(pubset),
                      only_search=len(sols - pubset), only_published=len(pubset - sols), invalid=bad)))
