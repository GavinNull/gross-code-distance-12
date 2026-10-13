"""E-011 续：六色着色下仍出现的权重 8 见证的构成。lead。"""
import json

from search.noninterleaved.colour_search import order_terms
from search.noninterleaved.ext import extended_matrices, residual_supports
from search.noninterleaved.heur import heur_min
from search.noninterleaved.run import OUT, neighbours
from search.noninterleaved.six_colour import KIND, M, ctx

c = ctx()
recs = [json.loads(l) for l in open(OUT / "e012_screen.jsonl")]
eights = [tuple(r["state"]) for r in recs if r.get("stage") == "screen" and r["w"] == 8][:4]
for st in eights:
    obc = {k: order_terms(KIND, *c["ok"][s]) for k, s in enumerate(st)}
    sups, owner = [], {}
    for i in range(c["code"].n2):
        for s in residual_supports([neighbours(c["code"], KIND, i, t) for t in obc[c["colour"][i]]]):
            sups.append(s)
            owner.setdefault(tuple(s), i)
    He, Le, lab = extended_matrices(c["H"], c["L"], sups)
    for sd in (0, 1, 2, 3):
        w, x, _ = heur_min(He, Le, trials=300, seed=sd, stop_at=8)
        if w is not None and w <= 8:
            break
    parts = [lab[j] for j in x]
    res = [(owner[tuple(p[1])], len(p[1])) for p in parts if p[0] == "r"]
    print(st, "w", w, "data", sum(p[0] == "q" for p in parts),
          "resid (xy, colour, len):", [((i // M, i % M), c["colour"][i], ln) for i, ln in res], flush=True)
