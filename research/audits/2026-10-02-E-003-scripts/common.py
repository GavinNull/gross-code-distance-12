"""E-003 audit helpers (auditor). Read-only use of baselines/ and evaluators/."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import stim

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from baselines.bb_code import BBCode  # noqa: E402
from baselines.circuit import memory_circuit, pipelined_memory_circuit  # noqa: E402
from baselines.gross import parse_poly  # noqa: E402
from baselines.schedule import ibm_depth8  # noqa: E402
from baselines.strikis import strikis_fig12  # noqa: E402

OUT = ROOT / "results" / "E-003-audit"
OUT.mkdir(parents=True, exist_ok=True)


def code_and_scheds():
    code = BBCode(12, 6, parse_poly(["x^3", "y", "y^2"]), parse_poly(["y^3", "x", "x^2"]))
    s, _ = strikis_fig12(code)
    return code, {"strikis": s, "ibm": ibm_depth8(code)}


def memory(code, sched, name, rounds, basis, p, detectors="basis"):
    """E-003 / E-002 circuits exactly as used in the experiments."""
    L = code.logical_z() if basis == "Z" else code.logical_x()
    if name == "ibm":
        return memory_circuit(sched, code.HX, code.HZ, L, rounds, basis, p, detectors)
    return pipelined_memory_circuit(sched, code.HX, code.HZ, L, rounds, basis, p, detectors)


def dem_matrices(c: stim.Circuit):
    from stimbposd.dem_to_matrices import detector_error_model_to_check_matrices
    mm = detector_error_model_to_check_matrices(c.detector_error_model(), allow_undecomposed_hyperedges=True)
    return (mm.check_matrix.tocsr().astype(np.uint8), mm.observables_matrix.tocsr().astype(np.uint8),
            np.asarray(mm.priors, dtype=float))
