"""E-044 crossover of full-distance circuits vs IBM depth-8 under SD6 (lam = 1 and lam = 0).  experimenter.

Circuits (all through the evaluator template memory_circuit, read-only; noise e026b.noisy_from: lam1 == evaluator
sd6 byte for byte, lam0 = idle DEPOLARIZE1 removed):
  gross [[144,12,12]], R = 12:  g10 (search/experiments/e040/g10_d12_spec.json, period 10, d_circ 12, STATE 27)
                                u11 (search/experiments/e032/u11_spec.json, period 11, d_circ 12, STATE 16/18)
                                ibm (IBM depth 8 via e026.common.spec('ibm'), d_circ 10, STATE 23)
  [[90,8,10]], R = 10:          c11 (search/experiments/e030/c11_spec.json, period 11, d_circ 10, STATE 17)
                                ibm90 (IBM depth 8 via e030.common.spec('ibm'), d_circ 8)
Decoder: BP-OSD with IBM parameters (e026.common.IBM_BPOSD) through stimbposd, i.e. the same object sinter uses.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

os.environ.setdefault("OMP_NUM_THREADS", "1")

import stim

from search.experiments.e026 import common as c26
from search.experiments.e026b.common import noisy_from
from search.experiments.e030 import common as c30
from search.experiments.e033 import common as c33
from evaluators import candidate as cand

ROOT = c26.ROOT
OUT = ROOT / "results" / "E-044-crossover"
OUT.mkdir(parents=True, exist_ok=True)
G10 = "search/experiments/e040/g10_d12_spec.json"
CODEFAM = {"g10": "gross", "u11": "gross", "ibm": "gross", "c11": "bb90", "ibm90": "bb90"}
ROUNDS = {"gross": 12, "bb90": 10}
DCIRC = {"g10": 12, "u11": 12, "ibm": 10, "c11": 10, "ibm90": 8}
PERIOD = {"g10": 10, "u11": 11, "ibm": 8, "c11": 11, "ibm90": 8}
IBM_BPOSD = c26.IBM_BPOSD


@lru_cache(maxsize=None)
def spec(name: str):
    if name == "g10":
        s = cand.parse_schedule(json.loads((ROOT / G10).read_text())).canonical()
        assert not cand.validate_schedule(s, c26.code())
        assert s.period == 10
        return s
    if name in ("u11", "ibm"):
        return c33.spec(name)
    if name == "c11":
        return c30.spec("c11")
    if name == "ibm90":
        return c30.spec("ibm")
    raise ValueError(name)


def code(name: str):
    return c26.code() if CODEFAM[name] == "gross" else c30.code()


@lru_cache(maxsize=None)
def noiseless(name: str, basis: str, rounds: int) -> stim.Circuit:
    return cand.memory_circuit(spec(name), code(name), basis, rounds)


def noisy(name: str, basis: str, p: float, model: str = "lam1", rounds: int | None = None) -> stim.Circuit:
    R = rounds or ROUNDS[CODEFAM[name]]
    return noisy_from(noiseless(name, basis, R), model, p)


def sinter_dem(circ: stim.Circuit) -> stim.DetectorErrorModel:
    """exactly what sinter hands the decoder (sinter/_collection/_collection_worker_state.py)"""
    try:
        return circ.detector_error_model(decompose_errors=True, approximate_disjoint_errors=True)
    except ValueError:
        return circ.detector_error_model(approximate_disjoint_errors=True)


def jdump(rec, fname):
    s = json.dumps(rec)
    print(s, flush=True)
    with open(OUT / fname, "a") as f:
        f.write(s + "\n")
