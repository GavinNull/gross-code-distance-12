"""E-040: per (code, kind, order) the extended-logical list of the order's type, reduced to translation-orbit
representatives (lifting is translation invariant because the schedule is), smallest first."""
from __future__ import annotations

import pickle
from functools import lru_cache

from search.experiments.e040.codes import MOD, OUT


@lru_cache(maxsize=None)
def type_rep(code, order):
    C = MOD[code]
    k = C.type_key(tuple(order))
    for o in C.all_types():
        if C.type_key(o) == k:
            return o
    raise KeyError(order)


@lru_cache(maxsize=None)
def orbit_reps(code, kind, trep, tag="list"):
    C = MOD[code]
    nm = C.name(trep)
    L = pickle.load(open(OUT / f"{tag}_{code}_{kind}_{nm}.pkl", "rb"))
    E = C.ext_general(kind, [trep] * C.N2)
    k2j = {E["He"][:, j].tobytes() + E["Le"][:, j].tobytes(): j for j in range(E["N"])}
    j2k = {j: k for k, j in k2j.items()}
    seen, reps = set(), []
    for x in L["keys"]:
        s = tuple(sorted(k2j[k] for k in x))
        if s in seen:
            continue
        orb = {tuple(sorted(int(Pm[j]) for j in s)) for Pm in E["perms"]}
        seen |= orb
        reps.append([j2k[j] for j in s])
    return L["meta"]["dext"], reps
