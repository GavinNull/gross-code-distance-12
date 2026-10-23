"""E-035 common: circuits (read-only reuse of E-026 / E-030 / E-033 specs and the evaluator template)."""
from __future__ import annotations
import os
from functools import lru_cache

os.environ.setdefault("OMP_NUM_THREADS", "1")

from search.experiments.e026 import common as c26
from search.experiments.e030 import common as c30
from search.experiments.e033 import common as c33
from evaluators import candidate as cand

ROOT = c26.ROOT
OUT = ROOT / "results" / "E-035-neutral-atom-ler"
CIRCS = ("u11", "ibm", "fig12", "c11", "ibm90")
CODE = {"u11": "gross", "ibm": "gross", "fig12": "gross", "c11": "bb90", "ibm90": "bb90"}
PERIOD = {"u11": 11, "ibm": 8, "fig12": 8, "c11": 11, "ibm90": 8}


def code_of(name):
    return c26.code() if CODE[name] == "gross" else c30.code()


def grid(name):
    # (l, m, n/2): gross l=12, m=6 (2308.07915); [[90]] l=15, m=3
    return (12, 6, 72) if CODE[name] == "gross" else (15, 3, 45)


@lru_cache(maxsize=None)
def spec(name):
    if CODE[name] == "gross":
        return c33.spec(name)
    return c30.spec("ibm" if name == "ibm90" else name)


@lru_cache(maxsize=None)
def noiseless(name, basis, rounds):
    return cand.memory_circuit(spec(name), code_of(name), basis, rounds)


def roles(name):
    from search.experiments.e035.na_noise import Roles
    c = code_of(name)
    l, m, _ = grid(name)
    return Roles(c.n, c.HX.shape[0], c.HZ.shape[0], l, m)


ROUNDS = {"gross": 12, "bb90": 10}


def rounds_of(name):
    return ROUNDS[CODE[name]]


def na_noisy(name, basis, rounds, tag):
    from search.experiments.e035.na_noise import apply, get_params
    return apply(noiseless(name, basis, rounds), get_params(tag), roles(name))
