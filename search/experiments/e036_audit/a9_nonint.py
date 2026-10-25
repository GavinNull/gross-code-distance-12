"""Audit claim 2: non-interleaved single-ancilla circuits (all X CNOTs in layers 1-6, all Z CNOTs in 7-12, uniform
per-type order).  bb18: every one of 720 x 720 should have d_circ <= 3 (pair argument); q1863: is d_circ = 3 reachable
(i.e. d_ext = 3 achievable)?  Exhaustive over the 720 X orders x 720 Z orders would be 518k; X and Z hooks decouple in
a non-interleaved circuit, so we scan X orders with a fixed Z order and vice versa, then confirm one combination."""
import itertools, json, random
from search.experiments.e036_audit.core import Sym, checks, legal, min_weight_le

def T_of(variant, px, pz):
    T = {}
    for k in checks(variant):
        p = px if k[0] == "X" else pz
        off = 0 if k[0] == "X" else 6
        t = [None]*6
        for s, term in enumerate(p): t[term] = off + s + 1
        T[k] = t
    return T

def dc(T, variant, wmax=3, Rs=(1,2,3)):
    best = None
    for R in Rs:
        for b in ("Z","X"):
            w,_ = min_weight_le(Sym(variant,b,T,R).mechs(), wmax)
            if w is not None and (best is None or w < best): best = w
    return best

out = {}
perms = list(itertools.permutations(range(6)))
for variant in ("bb18","q1863"):
    ident = tuple(range(6))
    # Z memory sees X hooks (X order); X memory sees Z hooks (Z order)
    hx = {}; goodx = []
    for px in perms:
        T = T_of(variant, px, ident)
        ws = [min_weight_le(Sym(variant,"Z",T,R).mechs(),3)[0] for R in (1,2,3)]
        w = min([x for x in ws if x is not None], default=">3")
        hx[str(w)] = hx.get(str(w),0)+1
        if w == 3 or w == ">3": goodx.append(px)
    hz = {}; goodz = []
    for pz in perms:
        T = T_of(variant, ident, pz)
        ws = [min_weight_le(Sym(variant,"X",T,R).mechs(),3)[0] for R in (1,2,3)]
        w = min([x for x in ws if x is not None], default=">3")
        hz[str(w)] = hz.get(str(w),0)+1
        if w == 3 or w == ">3": goodz.append(pz)
    rec = {"Zmem_hist_over_X_orders": hx, "Xmem_hist_over_Z_orders": hz}
    if goodx and goodz:
        T = T_of(variant, goodx[0], goodz[0]); assert legal(T, variant, 12)[0]
        rec["combined_example"] = [goodx[0], goodz[0], dc(T, variant)]
    out[variant] = rec
    print(variant, json.dumps(rec))
json.dump(out, open("results/E-036-audit/a9_nonint.json","w"), indent=1)
