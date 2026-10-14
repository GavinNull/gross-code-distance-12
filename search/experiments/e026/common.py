"""E-026: gross [[144,12,12]] LER comparison: new period-18 circuit (d_circ = 12) vs SBB Fig. 12 (11, period 8)
vs IBM depth-8 (<= 10).  experimenter.

All three circuits go through the SAME evaluator template (evaluators.candidate.memory_circuit, read-only use):
data reset at layer 0, each check reset -> 6 CX -> measure per round, explicit LOCAL detectors (check round j vs
round j-1, final data readout vs last round), observables = the evaluator's k = 12 logicals of the memory basis.
Noise: evaluators.noise.add_noise(model="sd6") = CX DEPOLARIZE2(p), reset flip p, pre-measure flip p,
DEPOLARIZE1(p) on every qubit not acted on in a layer (idle noise incl. ancillas).

Circuits:
  p18  : search/experiments/e024a/cs_P18_H24.json   (E-024a, d_circ = 12 proven, period 18)
  fig12: baselines.strikis.strikis_fig12 -> tests/schedule_helpers.from_baseline (period 8, d_circ = 11 proven)
  ibm  : baselines.schedule.ibm_depth8 -> from_baseline (period 8, d_circ <= 10)
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
from evaluators.noise import add_noise  # noqa: E402
from evaluators.tasks import build_code, get_task  # noqa: E402

OUT = ROOT / "results" / "E-026-gross-ler"
CIRCS = ("p18", "fig12", "ibm")
PERIOD = {"p18": 18, "fig12": 8, "ibm": 8}
DCIRC = {"p18": 12, "fig12": 11, "ibm": 10}  # ibm: upper bound (witness weight 10, E-002)
K = 12

IBM_BPOSD = dict(max_bp_iters=10000, bp_method="min_sum", ms_scaling_factor=0, osd_method="osd_cs", osd_order=7)
RELAY5 = dict(gamma0=0.1, pre_iter=80, num_sets=300, set_max_iter=60, gamma_dist_interval=(-0.24, 0.66),
              stop_nconv=5)


@lru_cache(maxsize=None)
def code():
    c, _ = build_code(get_task("gross-dcirc"), None)
    return c


@lru_cache(maxsize=None)
def spec(name: str):
    from schedule_helpers import from_baseline
    from baselines.bb_code import gross_code
    if name == "p18":
        s = cand.parse_schedule(json.loads((ROOT / "search/experiments/e024a/cs_P18_H24.json").read_text()))
    elif name == "fig12":
        from baselines.strikis import strikis_fig12
        s = from_baseline(strikis_fig12(gross_code())[0])
    elif name == "ibm":
        from baselines.schedule import ibm_depth8
        s = from_baseline(ibm_depth8(gross_code()))
    else:
        raise ValueError(name)
    s = s.canonical()
    probs = cand.validate_schedule(s, code())
    assert not probs, probs
    assert s.period == PERIOD[name]
    return s


@lru_cache(maxsize=None)
def noiseless(name: str, basis: str, rounds: int) -> stim.Circuit:
    return cand.memory_circuit(spec(name), code(), basis, rounds)


def noisy(name: str, basis: str, rounds: int, p: float) -> stim.Circuit:
    return add_noise(noiseless(name, basis, rounds), "sd6", p)


def per_round(P: float, R: int) -> float:
    return 1 - (1 - P) ** (1 / R)
