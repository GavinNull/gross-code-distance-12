"""E-006 shared helpers: circuits, joint DEM, per-sector decoding matrices, fault sampling.

Read-only use of evaluators/ (template circuits, sd6 noise, joint X/Z circuit, split_dem) and baselines/ (IBM schedule).

Conventions (identical to evaluators.l2 / E-002):
  * circuit = evaluator template memory circuit of the IBM depth-8 schedule (surface code: stim's standard order),
    sd6 noise, boundary="paper", joint X/Z sampling circuit (`l2.build_joint_circuit`).
  * Each joint-DEM mechanism j is restricted to the Z and X sectors; mechanisms with identical sector symptom
    (dets, obs) are merged into one sector column with XOR-combined prior (exactly `l2.split_dem`).
    Columns without detectors are dropped from the decoding matrix H (as in `l2._SectorDecoder`), but kept in
    the "truth" (their observable flips count): they are tracked as `Lfree`.
  * A shot = a set of fired joint mechanisms (stim DEM sampler with return_errors, or our fixed-weight sampler).
    Sector error vector e_s = (fired joint mechanisms mapped to sector columns) mod 2.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import scipy.sparse as sp
import stim

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluators import candidate as cand  # noqa: E402
from evaluators.l2 import build_joint_circuit, _xor_set  # noqa: E402
from evaluators.tasks import build_code, get_task  # noqa: E402

RESULTS = ROOT / "results" / "E-006-decoder-headroom"
RESULTS.mkdir(parents=True, exist_ok=True)

IBM_BPOSD = dict(max_iter=10000, bp_method="min_sum", ms_scaling_factor=0, osd_method="osd_cs", osd_order=7,
                 schedule="parallel")

# name -> (task id for the code matrices, (l, m, A, B) for the baseline IBM schedule, code distance, d_circ (IBM, ub))
BB = {
    "bb72": ("bb72-dcirc", (6, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"]), 6, 6),
    "bb90": ("bb90-dcirc", (15, 3, ["x^9", "y", "y^2"], ["y^0", "x^2", "x^7"]), 10, 8),
    "gross": ("gross-dcirc", (12, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"]), 12, 10),
}
CODE_DIST = {"bb72": 6, "bb90": 10, "gross": 12, "surf3": 3, "surf5": 5}
DEFAULT_ROUNDS = {"bb72": 6, "bb90": 10, "gross": 12, "surf3": 3, "surf5": 5}


@lru_cache(maxsize=None)
def code_and_schedule(name: str):
    if name.startswith("surf"):
        sys.path.insert(0, str(ROOT))
        from tests.schedule_helpers import surface_schedule
        return surface_schedule(int(name[4:]))
    tid, (l, m, A, B), _, _ = BB[name]
    code, _ = build_code(get_task(tid), None)
    from baselines.bb_code import BBCode
    from baselines.schedule import ibm_depth8
    from tests.schedule_helpers import from_baseline
    bb = BBCode(l, m, list(A), list(B))
    assert (bb.HX == code.HX).all() and (bb.HZ == code.HZ).all(), "baseline BBCode != evaluator code"
    spec = from_baseline(ibm_depth8(bb))
    probs = cand.validate_schedule(spec, code)
    assert not probs, probs
    return code, spec


@dataclass
class Sector:
    name: str
    H: sp.csc_matrix          # detectors x columns (columns with >=1 detector)
    L: sp.csr_matrix          # observables x columns
    priors: np.ndarray
    weights: np.ndarray       # log((1-p)/p)
    j2c: np.ndarray           # joint mechanism -> column index, -1 if none / detector-free
    j2free: np.ndarray        # joint mechanism -> detector-free observable flip (bitmask over observables), 0 if none
    num_det: int
    num_obs: int

    def errors(self, E: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """E: (shots, Nj) bool fired joint mechanisms -> (e (shots, ncols) uint8, free obs flips (shots, nobs) bool)."""
        ncol = self.H.shape[1]
        sel = self.j2c >= 0
        M = sp.csr_matrix((np.ones(sel.sum(), np.int32), (np.flatnonzero(sel), self.j2c[sel])),
                          shape=(len(self.j2c), ncol))
        e = (sp.csr_matrix(E.astype(np.int32)) @ M).toarray() % 2
        free = np.zeros((E.shape[0], self.num_obs), dtype=bool)
        fr = np.flatnonzero(self.j2free)
        for j in fr:
            bits = [(self.j2free[j] >> o) & 1 for o in range(self.num_obs)]
            free ^= E[:, j:j + 1] & np.array(bits, dtype=bool)[None, :]
        return e.astype(np.uint8), free

    def syndrome(self, e: np.ndarray) -> np.ndarray:
        return (sp.csr_matrix(e.astype(np.int32)) @ self.H.T.tocsr()).toarray() % 2

    def obs(self, e: np.ndarray) -> np.ndarray:
        return (sp.csr_matrix(e.astype(np.int32)) @ self.L.T.tocsr()).toarray() % 2


@dataclass
class Model:
    name: str
    p: float
    rounds: int
    circuit: stim.Circuit        # joint noisy circuit
    dem: stim.DetectorErrorModel  # joint DEM (no decomposition)
    priors: np.ndarray           # joint mechanism priors
    sectors: dict                # "Z"/"X" -> Sector
    nz: int
    oz: int
    joint_dets: list             # joint mechanism -> detector ids (joint numbering)


def build_model(name: str, p: float, rounds: int | None = None, boundary: str = "paper") -> Model:
    rounds = DEFAULT_ROUNDS[name] if rounds is None else rounds
    code, spec = code_and_schedule(name)
    circs = cand.build_circuits(spec.canonical(), code, rounds)
    lay = cand.layout_for(code)
    jc = build_joint_circuit(code, circs, list(lay.data), noise_model="sd6", p=p, boundary=boundary)
    dem = jc.circuit.detector_error_model(allow_gauge_detectors=False)
    nz, oz = jc.num_detectors_z, jc.num_observables_z
    nd, no = jc.circuit.num_detectors, jc.circuit.num_observables
    pri, keys, jdets = [], {"Z": [], "X": []}, []
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        pr = inst.args_copy()[0]
        parts = {"Z": ([], []), "X": ([], [])}
        dl = []
        for t in inst.targets_copy():
            if t.is_separator():
                continue
            if t.is_relative_detector_id():
                v = t.val
                dl.append(v)
                (parts["Z"] if v < nz else parts["X"])[0].append(v if v < nz else v - nz)
            elif t.is_logical_observable_id():
                v = t.val
                (parts["Z"] if v < oz else parts["X"])[1].append(v if v < oz else v - oz)
        for s in "ZX":
            d, o = parts[s]
            keys[s].append((tuple(sorted(_xor_set(d))), tuple(sorted(_xor_set(o)))))
        pri.append(pr)
        jdets.append(tuple(sorted(dl)))
    pri = np.array(pri)
    sectors = {}
    for s in "ZX":
        ndet = nz if s == "Z" else nd - nz
        nobs = oz if s == "Z" else no - oz
        merged: dict = {}
        order: list = []
        for j, key in enumerate(keys[s]):
            if not key[0] and not key[1]:
                continue
            if key not in merged:
                merged[key] = 0.0
                order.append(key)
            q = merged[key]
            merged[key] = q * (1 - pri[j]) + pri[j] * (1 - q)
        cols = [k for k in order if k[0]]
        cidx = {k: i for i, k in enumerate(cols)}
        j2c = np.full(len(pri), -1, dtype=np.int64)
        j2free = np.zeros(len(pri), dtype=np.int64)
        for j, key in enumerate(keys[s]):
            if key in cidx:
                j2c[j] = cidx[key]
            elif key[1] and not key[0]:
                j2free[j] = sum(1 << o for o in key[1])
        rows, ci, orows, oci = [], [], [], []
        for i, (d, o) in enumerate(cols):
            rows += d; ci += [i] * len(d)
            orows += o; oci += [i] * len(o)
        H = sp.csc_matrix((np.ones(len(rows), np.uint8), (rows, ci)), shape=(ndet, len(cols)))
        L = sp.csr_matrix((np.ones(len(orows), np.uint8), (orows, oci)), shape=(nobs, len(cols)))
        pr_s = np.array([merged[k] for k in cols])
        sectors[s] = Sector(s, H, L, pr_s, np.log((1 - pr_s) / pr_s), j2c, j2free, ndet, nobs)
    return Model(name, p, rounds, jc.circuit, dem, pri, sectors, nz, oz, jdets)


def sample_dem(model: Model, shots: int, seed: int):
    """Returns dets (shots, nd) bool, obs (shots, no) bool, E (shots, Nj) bool (fired joint mechanisms)."""
    sampler = model.dem.compile_sampler(seed=seed)
    dets, obs, E = sampler.sample(shots, return_errors=True)
    return dets, obs, E


def sector_truth(model: Model, s: str, dets, obs, E, check: bool = True):
    """Sector views of a batch: syndrome (shots, ndet_s) uint8, true observable flips (shots, nobs_s) bool, e_true."""
    sec = model.sectors[s]
    e, free = sec.errors(E)
    syn = sec.syndrome(e).astype(np.uint8)
    ob = (sec.obs(e).astype(bool)) ^ free
    if check:
        if s == "Z":
            d0, o0 = dets[:, :model.nz], obs[:, :model.oz]
        else:
            d0, o0 = dets[:, model.nz:], obs[:, model.oz:]
        assert np.array_equal(syn.astype(bool), d0), "sector syndrome mismatch"
        assert np.array_equal(ob, o0), "sector observable mismatch"
    return syn, ob, e


# ---------------------------------------------------------------------------
# Fixed-weight fault sampling (conditional Bernoulli)
# ---------------------------------------------------------------------------

def weight_distribution(priors: np.ndarray, wmax: int) -> np.ndarray:
    """P(exactly w of the independent joint mechanisms fire), w = 0..wmax (Poisson-binomial, exact DP)."""
    P = np.zeros(wmax + 1)
    P[0] = 1.0
    for q in priors:
        P[1:] = P[1:] * (1 - q) + P[:-1] * q
        P[0] *= (1 - q)
    return P


def sample_fixed_weight(priors: np.ndarray, w: int, n: int, rng: np.random.Generator) -> np.ndarray:
    """n sets of exactly w joint mechanisms, distributed as the DEM conditioned on |E| = w:
    P(S | |S|=w) ∝ prod_{i in S} r_i, r_i = q_i/(1-q_i).  Exact rejection sampler: independent Bernoulli with
    odds lam*r_i (lam chosen so the mean count is w) conditioned on count == w has the same distribution for any lam.
    Returns (n, w) int array of mechanism indices."""
    r = priors / (1 - priors)
    lo, hi = 1e-12, 1e12
    for _ in range(200):
        lam = np.sqrt(lo * hi)
        m = (lam * r / (1 + lam * r)).sum()
        if m > w:
            hi = lam
        else:
            lo = lam
    q = lam * r / (1 + lam * r)
    out = []
    while len(out) < n:
        B = rng.random((64, len(q))) < q[None, :]
        cnt = B.sum(1)
        for row in np.flatnonzero(cnt == w):
            out.append(np.flatnonzero(B[row]))
            if len(out) == n:
                break
    return np.array(out, dtype=np.int64).reshape(n, w)


def sets_to_E(sets: np.ndarray, Nj: int) -> np.ndarray:
    E = np.zeros((len(sets), Nj), dtype=bool)
    for i, s in enumerate(sets):
        E[i, s] = True
    return E
