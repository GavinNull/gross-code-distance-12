"""E-030 LER comparison on [[90,8,10]] (bb90-dcirc code, IBM 2308.07915 Table 3).  experimenter.

Every circuit goes through the SAME evaluator template (evaluators.candidate.memory_circuit, read-only use): data reset
at layer 0, each check reset -> 6 CX -> measure per round, explicit LOCAL detectors (round j vs j-1, final data readout
vs last round), observables = evaluator's k = 8 logicals of the memory basis.  Noise: e026b.noisy_from (SD6 with the
idle DEPOLARIZE1 rescaled to lam*p; lam1 == evaluators sd6 byte-for-byte), decoders e026 (BP-OSD IBM parameters,
Relay-BP relay5), identical for all circuits.

Circuits:
  c11 : search/experiments/e030/c11_spec.json  (E-030, period 11, wrapping Z prep; d_circ = 10 if certified)
  c12 : search/experiments/e030/c12_spec.json  (E-030, period 12, non-wrapping)
  c13 : search/experiments/e030/c13_spec.json  (c16 with its 3 empty layers removed)
  c16 : search/experiments/e028/c16_spec.json  (E-028, d_circ = 10 proven)
  ibm : baselines.schedule.ibm_depth8 on BBCode(15, 3, [x^9, y, y^2], [1, x^2, x^7]) -> from_baseline (period 8;
        d_circ = 8, 2503.10988 App. D MaxSAT; E-004 upper bound 8)
"""
from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import stim

ROOT = Path(__file__).resolve().parents[3]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from evaluators import candidate as cand  # noqa: E402
from evaluators.tasks import build_code, get_task  # noqa: E402
from search.experiments.e026b.common import noisy_from  # noqa: E402

OUT = ROOT / "results" / "E-030-bb90-period-ler"
SPECS = {"c11": "search/experiments/e030/c11_spec.json", "c12": "search/experiments/e030/c12_spec.json",
         "c13": "search/experiments/e030/c13_spec.json", "c16": "search/experiments/e028/c16_spec.json"}
PERIOD = {"c11": 11, "c12": 12, "c13": 13, "c16": 16, "ibm": 8}
DCIRC = {"c11": 10, "c12": 10, "c13": 10, "c16": 10, "ibm": 8}
K = 8


@lru_cache(maxsize=None)
def code():
    c, _ = build_code(get_task("bb90-dcirc"), None)
    assert c.n == 90 and c.k == K
    return c


@lru_cache(maxsize=None)
def spec(name: str):
    if name == "ibm":
        from schedule_helpers import from_baseline
        from baselines.bb_code import BBCode
        from baselines.schedule import ibm_depth8
        bb = BBCode(15, 3, ["x^9", "y", "y^2"], ["x^0", "x^2", "x^7"])
        c = code()
        assert (bb.HX % 2 == np.asarray(c.HX) % 2).all() and (bb.HZ % 2 == np.asarray(c.HZ) % 2).all()
        s = from_baseline(ibm_depth8(bb))
    else:
        s = cand.parse_schedule(json.loads((ROOT / SPECS[name]).read_text()))
    s = s.canonical()
    probs = cand.validate_schedule(s, code())
    assert not probs, probs
    assert s.period == PERIOD[name]
    return s


@lru_cache(maxsize=None)
def noiseless(name: str, basis: str, rounds: int) -> stim.Circuit:
    return cand.memory_circuit(spec(name), code(), basis, rounds)


def noisy(name: str, basis: str, rounds: int, p: float, model: str = "lam1") -> stim.Circuit:
    return noisy_from(noiseless(name, basis, rounds), model, p)


def per_round(P: float, R: int) -> float:
    return 1 - (1 - P) ** (1 / R)
