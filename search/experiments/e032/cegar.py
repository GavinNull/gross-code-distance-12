"""E-032: list loader (from e028/cegar.load_class)."""
from __future__ import annotations

import pickle

from search.experiments.e032 import common as C
from search.experiments.e032.wlist import tag_of


def load_class(kind, sub, orders_s, w):
    d = pickle.load(open(C.OUT / f"{tag_of(kind, sub, orders_s, w)}.pkl", "rb"))
    return d["keys"], frozenset(d["colset"])
