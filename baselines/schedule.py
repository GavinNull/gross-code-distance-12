"""Syndrome-extraction schedules as plain data, independent of circuit generation.

A `Schedule` describes ONE syndrome cycle as a list of layers (time steps). Each layer lists
  - cnots:   (control, target) qubit pairs
  - prep_x / prep_z:  check qubits initialised in |+> / |0>
  - meas_x / meas_z:  check qubits measured in X / Z basis
Any qubit not mentioned in a layer is idle in that layer.

Conventions enforced by `validate`:
  - X-check qubits are CNOT controls, Z-check qubits are CNOT targets, data are the other end;
  - within a layer every qubit appears at most once;
  - each check is prepared exactly once and measured exactly once per cycle;
  - reading the cycle cyclically from its prep layer, the check's CNOTs all happen after prep
    and before its measurement, and the data qubits they touch are exactly the check's support.
    (A check may be prepared *after* its measurement within the listed cycle, i.e. its prep is
    pipelined into the previous cycle — as for the Z checks of the IBM circuit. The circuit
    generator then inserts an initial prep layer before the first cycle.)
Commutation between X- and Z-check gate orders is NOT checked here; the circuit-level
determinism test in `baselines.circuit` catches invalid interleavings.

Search code should produce a `Schedule` (or term orders fed to `bb_term_schedule`) and hand it
to the circuit generator; nothing else needs to change.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict

import numpy as np

from baselines.bb_code import BBCode


@dataclass
class Layer:
    cnots: list[tuple[int, int]] = field(default_factory=list)
    prep_x: list[int] = field(default_factory=list)
    prep_z: list[int] = field(default_factory=list)
    meas_x: list[int] = field(default_factory=list)
    meas_z: list[int] = field(default_factory=list)

    def qubits(self) -> list[int]:
        q = [a for c in self.cnots for a in c]
        return q + self.prep_x + self.prep_z + self.meas_x + self.meas_z


@dataclass
class Schedule:
    name: str
    num_qubits: int
    data: list[int]            # data qubit ids, in code column order
    x_checks: list[int]        # X-check qubit ids, in HX row order
    z_checks: list[int]        # Z-check qubit ids, in HZ row order
    layers: list[Layer]

    @property
    def depth(self) -> int:
        return len(self.layers)

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(s: str) -> "Schedule":
        d = json.loads(s)
        d["layers"] = [Layer(cnots=[tuple(c) for c in L["cnots"]], prep_x=L["prep_x"], prep_z=L["prep_z"],
                             meas_x=L["meas_x"], meas_z=L["meas_z"]) for L in d["layers"]]
        return Schedule(**d)

    # ------------------------------------------------------------------ validation
    def validate(self, HX: np.ndarray, HZ: np.ndarray) -> None:
        data_col = {q: j for j, q in enumerate(self.data)}
        xset, zset = set(self.x_checks), set(self.z_checks)
        for t, L in enumerate(self.layers):
            qs = L.qubits()
            if len(qs) != len(set(qs)):
                raise ValueError(f"layer {t}: a qubit is used twice")
            for c, tg in L.cnots:
                ok = (c in xset and tg in data_col) or (c in data_col and tg in zset)
                if not ok:
                    raise ValueError(f"layer {t}: CNOT ({c},{tg}) violates control/target convention")
            if set(L.prep_x) - xset or set(L.meas_x) - xset or set(L.prep_z) - zset or set(L.meas_z) - zset:
                raise ValueError(f"layer {t}: prep/meas on wrong qubit type")

        for checks, H, is_x in ((self.x_checks, HX, True), (self.z_checks, HZ, False)):
            for row, q in enumerate(checks):
                preps = [t for t, L in enumerate(self.layers) if q in (L.prep_x if is_x else L.prep_z)]
                meas = [t for t, L in enumerate(self.layers) if q in (L.meas_x if is_x else L.meas_z)]
                if len(preps) != 1 or len(meas) != 1:
                    raise ValueError(f"check {q}: needs exactly one prep and one meas per cycle")
                tp, tm = preps[0], meas[0]
                D = self.depth
                # cyclic window strictly after prep, strictly before meas
                window = [(tp + s) % D for s in range(1, (tm - tp) % D)]
                touched = []
                for t, L in enumerate(self.layers):
                    for c, tg in L.cnots:
                        if q in (c, tg):
                            if t not in window:
                                raise ValueError(f"check {q}: CNOT in layer {t} outside prep..meas window")
                            touched.append(data_col[tg if is_x else c])
                if sorted(touched) != sorted(np.nonzero(H[row])[0].tolist()):
                    raise ValueError(f"check {q}: CNOT support != stabilizer support")

    def wrapped_checks(self) -> list[int]:
        """Checks whose prep layer comes after their meas layer (prep belongs to previous cycle)."""
        out = []
        for q in self.x_checks + self.z_checks:
            tp = next(t for t, L in enumerate(self.layers) if q in L.prep_x + L.prep_z)
            tm = next(t for t, L in enumerate(self.layers) if q in L.meas_x + L.meas_z)
            if tp > tm:
                out.append(q)
        return out


# ---------------------------------------------------------------------- BB layout + IBM schedule

def bb_layout(code: BBCode) -> dict[str, list[int]]:
    """Qubit ids: X checks 0..n2-1, L data n2..2n2-1, R data 2n2..3n2-1, Z checks 3n2..4n2-1."""
    n2 = code.n2
    return {
        "X": list(range(0, n2)),
        "L": list(range(n2, 2 * n2)),
        "R": list(range(2 * n2, 3 * n2)),
        "Z": list(range(3 * n2, 4 * n2)),
    }


# Term indices: 0,1,2 = A1,A2,A3 ; 3,4,5 = B1,B2,B3.
# IBM depth-8 cycle (arXiv:2308.07915 Table 5; identical to sX/sZ in github.com/sbravyi/BivariateBicycleCodes):
#   CNOT layer t=0..6 (paper rounds 1..7). None = that check type idles in that CNOT layer.
#   NB: the IBM repo indexes Z-check terms as [B1,B2,B3,A1,A2,A3] (sZ = [3,5,0,1,2,4,'idle']);
#   here BOTH check types use the uniform index [A1,A2,A3,B1,B2,B3], so sZ is re-expressed.
IBM_SX = [None, 1, 4, 3, 5, 0, 2]   # X checks: -, A2, B2, B1, B3, A1, A3
IBM_SZ = [0, 2, 3, 4, 5, 1, None]   # Z checks: A1^T, A3^T, B1^T, B2^T, B3^T, A2^T, -


def bb_term_schedule(code: BBCode, sX: list, sZ: list, name: str) -> Schedule:
    """Depth-8 BB cycle in the paper's format, parameterised by the 7-slot term orders sX, sZ.

    layer 0     : InitX on X checks, Z CNOT slot 0
    layers 1..5 : X CNOT slot t, Z CNOT slot t
    layer 6     : X CNOT slot 6, MeasZ on Z checks
    layer 7     : MeasX on X checks, InitZ on Z checks (Z checks are pipelined into next cycle)
    """
    if len(sX) != 7 or len(sZ) != 7:
        raise ValueError("sX, sZ must have 7 slots")
    lay = bb_layout(code)
    blk = {"L": lay["L"], "R": lay["R"]}
    layers = [Layer() for _ in range(8)]
    layers[0].prep_x = list(lay["X"])
    layers[6].meas_z = list(lay["Z"])
    layers[7].meas_x = list(lay["X"])
    layers[7].prep_z = list(lay["Z"])
    for t in range(7):
        if sX[t] is not None:
            for i, q in enumerate(lay["X"]):
                b, j = code.x_check_neighbor(sX[t], i)
                layers[t].cnots.append((q, blk[b][j]))
        if sZ[t] is not None:
            for i, q in enumerate(lay["Z"]):
                b, j = code.z_check_neighbor(sZ[t], i)
                layers[t].cnots.append((blk[b][j], q))
    return Schedule(name=name, num_qubits=4 * code.n2, data=lay["L"] + lay["R"],
                    x_checks=lay["X"], z_checks=lay["Z"], layers=layers)


def ibm_depth8(code: BBCode) -> Schedule:
    return bb_term_schedule(code, IBM_SX, IBM_SZ, name="ibm_depth8")


SCHEDULES = {"ibm_depth8": ibm_depth8}
