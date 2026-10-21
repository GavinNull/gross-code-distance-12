"""E-033 gross [[144,12,12]] LER: u11 (E-032, period 11, d_circ = 12 audited) vs SBB Fig. 12 (period 8, d_circ = 11)
vs IBM depth 8 (2308.07915, period 8, d_circ <= 10).  experimenter.

Reuse (read-only): e026.common for fig12 / ibm specs and the gross code (evaluator template memory_circuit = data
reset layer 0, per round reset -> 6 CX -> measure, explicit LOCAL detectors, the evaluator's 12 logicals);
e026b.common.noisy_from for SD6 with ONLY the idle DEPOLARIZE1 rescaled to lam*p (lam1 == evaluator sd6 byte for
byte); e026.decoders (BP-OSD IBM parameters, Relay-BP relay5), identical for every circuit.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

os.environ.setdefault("OMP_NUM_THREADS", "1")

import stim

from search.experiments.e026 import common as c26
from search.experiments.e026b.common import noisy_from
from evaluators import candidate as cand

ROOT = c26.ROOT
OUT = ROOT / "results" / "E-033-gross-u11-ler"
U11 = "search/experiments/e032/u11_spec.json"
PERIOD = {"u11": 11, "fig12": 8, "ibm": 8}
DCIRC = {"u11": 12, "fig12": 11, "ibm": 10}
SPECFILE = {"u11": U11}


@lru_cache(maxsize=None)
def spec(name: str):
    if name != "u11":
        return c26.spec(name)
    s = cand.parse_schedule(json.loads((ROOT / U11).read_text())).canonical()
    probs = cand.validate_schedule(s, c26.code())
    assert not probs, probs
    assert s.period == 11
    return s


@lru_cache(maxsize=None)
def noiseless(name: str, basis: str, rounds: int) -> stim.Circuit:
    return cand.memory_circuit(spec(name), c26.code(), basis, rounds)


def noisy(name: str, basis: str, rounds: int, p: float, model: str = "lam1") -> stim.Circuit:
    return noisy_from(noiseless(name, basis, rounds), model, p)
