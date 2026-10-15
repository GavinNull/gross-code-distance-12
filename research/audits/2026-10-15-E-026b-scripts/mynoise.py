"""Auditor (E-026b): independent SD6-with-scaled-idle noise builder, written from the SD6 definition
(arXiv:2108.10457 Table 2, SD6 column) WITHOUT calling evaluators.noise.add_noise or e026b.rescale_idle:
  CX -> DEPOLARIZE2(p) after; R/RX -> X_ERROR/Z_ERROR(p) after; M/MX -> X_ERROR/Z_ERROR(p) before;
  every qubit not acted on in a TICK-layer -> DEPOLARIZE1(lam*p) (omitted if lam == 0).
Only the noiseless template (evaluators.candidate.memory_circuit via e026.common.noiseless) is shared."""
import os, sys
from pathlib import Path
os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np
import scipy.sparse as sp
import stim
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from search.experiments.e026.common import noiseless  # template only

ANN = {"DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS", "MPAD"}


def my_sd6_lam(nl: stim.Circuit, p: float, lam: float) -> stim.Circuit:
    layers = [[]]
    for inst in nl.flattened():
        if inst.name == "TICK":
            layers.append([])
        else:
            layers[-1].append(inst)
    allq = set()
    for L in layers:
        for i in L:
            if i.name not in ANN:
                allq |= {t.value for t in i.targets_copy() if t.is_qubit_target}
    out = stim.Circuit()
    for li, L in enumerate(layers):
        if li:
            out.append("TICK")
        used = set()
        for i in L:
            n = i.name
            if n in ANN:
                out.append(i); continue
            qs = [t.value for t in i.targets_copy() if t.is_qubit_target]
            assert not (used & set(qs)); used |= set(qs)
            if n == "CX":
                out.append(i); out.append("DEPOLARIZE2", qs, p)
            elif n == "R":
                out.append(i); out.append("X_ERROR", qs, p)
            elif n == "RX":
                out.append(i); out.append("Z_ERROR", qs, p)
            elif n == "M":
                out.append("X_ERROR", qs, p); out.append(i)
            elif n == "MX":
                out.append("Z_ERROR", qs, p); out.append(i)
            else:
                raise ValueError(n)
        idle = sorted(allq - used)
        if idle and lam > 0:
            out.append("DEPOLARIZE1", idle, lam * p)
    return out


def circuit(circ, basis, R, p, lam):
    return my_sd6_lam(noiseless(circ, basis, R), p, lam)


def build_dem(c: stim.Circuit):
    """own column merge: key (detectors, observables), XOR-combined priors."""
    dem = c.detector_error_model(decompose_errors=False)
    cols, colp = {}, []
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        pr = inst.args_copy()[0]
        ds = tuple(sorted(t.val for t in inst.targets_copy() if t.is_relative_detector_id()))
        ob = tuple(sorted(t.val for t in inst.targets_copy() if t.is_logical_observable_id()))
        k = (ds, ob)
        if k not in cols:
            cols[k] = len(colp); colp.append(0.0)
        j = cols[k]; colp[j] = colp[j] * (1 - pr) + pr * (1 - colp[j])
    H = sp.lil_matrix((dem.num_detectors, len(colp)), dtype=np.uint8)
    L = sp.lil_matrix((dem.num_observables, len(colp)), dtype=np.uint8)
    for (ds, ob), j in cols.items():
        for d in ds: H[d, j] = 1
        for o in ob: L[o, j] = 1
    return dem, H.tocsr(), L.tocsr(), np.array(colp), cols
