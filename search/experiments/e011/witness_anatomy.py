"""E-011：三色着色下 BB108 X 侧权重 ≤9 见证的构成（哪些校验的残余拼成短逻辑错误）。lead。

    PYTHONPATH=. uv run python -m search.experiments.e011.witness_anatomy
"""
import collections
import json

from search.noninterleaved.colour_search import homomorphisms, order_terms
from search.noninterleaved.ext import extended_matrices, residual_supports
from search.noninterleaved.heur import heur_min
from search.noninterleaved.run import HL, OUT, get_code, neighbours

code, css = get_code("[[108,8,10]]")
H, L = HL(css, "X")
m = 6
HM = {f"{h['alpha']},{h['beta']}": h["colour"] for h in homomorphisms(code)}


def analyse(hkey, triple, seeds=(1, 2, 3)):
    col = HM[hkey]
    obc = {c: order_terms("X", tuple(b[0]), tuple(b[1])) for c, b in enumerate(triple)}
    sups, owner = [], {}
    for i in range(code.n2):
        for s in residual_supports([neighbours(code, "X", i, t) for t in obc[col[i]]]):
            sups.append(s)
            owner.setdefault(tuple(s), i)
    He, Le, lab = extended_matrices(H, L, sups)
    for sd in seeds:
        w, x, _ = heur_min(He, Le, trials=1000, seed=sd, lns_starts=16, stop_at=9)
        if w is not None and w <= 9:
            break
    parts = [lab[j] for j in x]
    data = [p[1] for p in parts if p[0] == "q"]
    res = [owner[tuple(p[1])] for p in parts if p[0] == "r"]
    checks = [(i, (i // m, i % m), col[i], len(next(p[1] for p in parts if p[0] == "r" and owner[tuple(p[1])] == i)))
              for i in res]
    return {"h": hkey, "weight": w, "n_data": len(data), "n_residual": len(res),
            "residual_checks": checks}


out = []
triples = [json.loads(l) for l in open(OUT / "colourscreen_heur_108_8_10_X_T10.jsonl")]
pick = [t["key"] for t in triples if t["key"][0] == "1,0"][:6] + [t["key"] for t in triples if t["key"][0] != "1,0"][:2]
for hkey, tr in pick:
    r = analyse(hkey, tr)
    r["triple"] = tr
    out.append(r)
    print(json.dumps(r), flush=True)
(OUT / "e011_witness_anatomy.json").write_text(json.dumps(out, indent=1))
