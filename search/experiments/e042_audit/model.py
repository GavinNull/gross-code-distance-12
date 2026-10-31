"""E-042 audit (auditor, 2026-11-01): own step-index model parsed from the noiseless stim circuit.

Independent of search/experiments/e042 (never imported) and of evaluators.candidate.unroll: the instance times are
read off the circuit that the evaluator's public entry `memory_circuit` produces, layer by layer.

Conventions (memory basis b; Z basis: errors of X type):
  readers  = ancillas measured in basis b (M for Z, MX for X); writers = the other ancillas.
  read time of reader r on data q in instance t = layer of the CX between r and q in that instance.
  finite index of a deposit at time u (half-integer, or a CX layer of another ancilla) on q for reader r
      = #{finite instances t : read_t(r, q) < u}  (R = final data readout)
  bulk index = same count over the periodic extension read_t = read_0 + tP, t in Z, measured from instance 0
      = floor((u - read_0) / P) + 1.
  a detector = (row of reader in layout order, index); the readout flip of instance t = {(row, t), (row, t+1)}.
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
for p in (str(ROOT), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

SPECS = {
    "g10": ("gross", "search/experiments/e040/g10_d12_spec.json"),
    "u11": ("gross", "search/experiments/e032/u11_spec.json"),
    "ctl_p10": ("gross", "search/experiments/e032/ctl_p10_spec.json"),
    "segctl": ("gross", "results/E-032-audit/segctl_spec.json"),
    "u16": ("bb90", "search/experiments/e028/u16_spec.json"),
    "c11": ("bb90", "search/experiments/e030/c11_spec.json"),
    "kunlun": ("kunlun-bb18", "results/theoryB/specs/kunlun_bb18.json"),
    "segctl_g10": ("gross", "results/E-042-g10-cert/lift/ctl/segctl_g10.json"),
}


def get_code(name):
    from search.theory.B_audit.common import get_code as g
    return g(name)


def circuit(cname, R, basis):
    from evaluators import candidate as cand
    codename, sp = SPECS[cname]
    code = get_code(codename)
    spec = cand.parse_schedule(json.loads((ROOT / sp).read_text()))
    assert not cand.validate_schedule(spec, code)
    return code, cand.memory_circuit(spec, code, basis, R), cand.layout_for(code)


def red(items):
    c = Counter(items)
    return frozenset(it for it, m in c.items() if m % 2)


class Model:
    def __init__(self, cname, R, basis):
        self.cname, self.R, self.basis = cname, R, basis
        code, circ, lay = circuit(cname, R, basis)
        self.code, self.circ = code, circ
        n = self.n = code.n
        t = 0
        inst = defaultdict(list)
        mgate = {}
        for op in circ.flattened():
            nm = op.name
            if nm == "TICK":
                t += 1
                continue
            qs = [x.value for x in op.targets_copy() if x.is_qubit_target]
            if nm in ("R", "RX"):
                for q in qs:
                    if q >= n:
                        inst[q].append({"prep": t, "cx": [], "meas": None})
            elif nm == "CX":
                for a, b in zip(qs[::2], qs[1::2]):
                    if a >= n and b < n:
                        inst[a][-1]["cx"].append((t, b))
                    elif b >= n and a < n:
                        inst[b][-1]["cx"].append((t, a))
                    else:
                        raise AssertionError("CX between two data or two ancillas")
            elif nm in ("M", "MX"):
                for q in qs:
                    if q >= n:
                        inst[q][-1]["meas"] = t
                        mgate[q] = nm
            elif nm in ("DETECTOR", "OBSERVABLE_INCLUDE"):
                pass
            else:
                raise AssertionError(nm)
        self.nlay = t                       # layers 0..t-1; final data readout after layer t-1
        self.last = t - 1
        rg = "M" if basis == "Z" else "MX"
        ranc = list(lay.z_anc if basis == "Z" else lay.x_anc)
        wanc = list(lay.x_anc if basis == "Z" else lay.z_anc)
        assert all(mgate[a] == rg for a in ranc) and all(mgate[a] != rg for a in wanc)
        self.row = {a: i for i, a in enumerate(ranc)}
        H = np.asarray(code.HZ if basis == "Z" else code.HX) % 2
        L = np.asarray(code.LZ if basis == "Z" else code.LX) % 2
        self.H, self.L = H.astype(np.uint8), L.astype(np.uint8)
        # period: from instance prep times (all ancillas, all consecutive instances)
        diffs = {I2["prep"] - I1["prep"] for a in inst for I1, I2 in zip(inst[a], inst[a][1:])}
        assert len(diffs) <= 1
        self.P = int(json.loads((ROOT / SPECS[cname][1]).read_text())["period"])
        assert not diffs or diffs == {self.P}, "instance spacing != spec period"
        for a in inst:
            assert len(inst[a]) == R
            for I in inst[a]:
                assert len(I["cx"]) == 6 and I["prep"] < min(x for x, _ in I["cx"]) and \
                    max(x for x, _ in I["cx"]) < I["meas"]
        # readers: q -> [(row, [read times of instance 0..R-1])]
        self.reads = defaultdict(list)
        for a in ranc:
            per = defaultdict(list)
            for I in inst[a]:
                for tt, q in I["cx"]:
                    per[q].append(tt)
            assert sorted(per) == np.flatnonzero(H[self.row[a]]).tolist()
            for q, ts in per.items():
                if self.P is not None:
                    assert all(y - x == self.P for x, y in zip(ts, ts[1:])), "reads not periodic"
                self.reads[q].append((self.row[a], ts))
        # writers: list of instances, each a time-sorted [(t, q)]
        self.writers = [[sorted(I["cx"]) for I in inst[a]] for a in wanc]
        self.nreaders = len(ranc)

    # ----- indices
    def fin(self, q, u):
        return [(r, sum(1 for x in ts if x < u)) for r, ts in self.reads[q]]

    def bulk(self, q, u):
        P = self.P
        return [(r, math.floor((u - ts[0]) / P) + 1) for r, ts in self.reads[q]]

    def image(self, qs):
        v = np.zeros(self.n, np.uint8)
        for q in qs:
            v[q] ^= 1
        return (self.H.astype(np.int64) @ v % 2).astype(np.uint8).tobytes() + \
            (self.L.astype(np.int64) @ v % 2).astype(np.uint8).tobytes()

    def lobs(self, qs):
        v = np.zeros(self.n, np.uint8)
        for q in qs:
            v[q] ^= 1
        return frozenset(np.flatnonzero(self.L.astype(np.int64) @ v % 2).tolist())

    # ----- finite single faults: (kind, ident, items(frozenset), residual data qubits)
    def finite_faults(self):
        out = []
        for q in range(self.n):
            for u2 in range(1, 2 * (self.last + 1) + 1, 2):
                u = u2 / 2
                out.append(("d", (q, u), red(self.fin(q, u)), (q,)))
        for c, insts in enumerate(self.writers):
            for j, cx in enumerate(insts):
                for k in range(1, 7):
                    suf = cx[k - 1:]
                    its = []
                    for tt, q in suf:
                        its += self.fin(q, tt)
                    out.append(("h", (c, j, k), red(its), tuple(q for _, q in suf)))
        for r in range(self.nreaders):
            for t in range(self.R):
                out.append(("f", (r, t), frozenset({(r, t), (r, t + 1)}), ()))
        return out


def dem_sigs(circ, p=1e-3):
    """set of (detectors as (row, index), L-observables) of the evaluator's SD6 DEM, and per-term index spans."""
    from evaluators.noise import add_noise
    noisy = add_noise(circ, "sd6", p)
    coords = noisy.get_detector_coordinates()
    d = noisy.detector_error_model(approximate_disjoint_errors=True, flatten_loops=True)
    out = set()
    for e in d.flattened():
        if e.type != "error":
            continue
        ds, os_ = set(), set()
        for t in e.targets_copy():
            if t.is_relative_detector_id():
                c = coords[t.val]
                ds ^= {(int(c[0]), int(c[1]))}
            elif t.is_logical_observable_id():
                os_ ^= {t.val}
        if ds or os_:
            out.add((frozenset(ds), frozenset(os_)))
    return out
