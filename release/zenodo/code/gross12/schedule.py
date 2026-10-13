"""Circuit specification format "qec-schedule/v1" and the memory-circuit template.

Format (JSON)
-------------
    {
      "format": "qec-schedule/v1",
      "period": P,                                     # time steps per period
      "x_checks": [ {"prep": s, "meas": m, "cnots": [[q, t], ...]}, ... ],   # one entry per row of HX, in row order
      "z_checks": [ ... one entry per row of HZ ... ],
      "name": "optional free text"
    }

All times are integers in 0..P-1 and are read cyclically: the offset of a time t is (t - prep) mod P.  A check
applies exactly one CNOT to every data qubit q of its row support, at the listed time step; the order of its six
CNOTs is the order of their offsets.  Required: 0 < offset(cnot) < offset(meas) < P, distinct CNOT offsets per check,
and at most one CNOT per data qubit per time step (mod P).  Windows may cross the period boundary (pipelining).

Template (one dedicated ancilla per check)
------------------------------------------
Qubits: data 0..143 (column j of the code = qubit j), X ancillas 144..215 (HX row order), Z ancillas 216..287.
X check: RX reset, CX(ancilla -> data), MX.  Z check: R reset, CX(data -> ancilla), M.
Unrolling: instance j of check c is reset at start_c + P*j, its CNOTs at reset + offset, its measurement at
reset + offset(meas), j = 0..R-1.  Layer 0 resets all data qubits (in the memory basis); no data CNOT before layer 1.
A global shift sigma in 0..P-1 is chosen to minimise the number of layers (ties: smallest sigma); every check takes
the earliest start compatible with sigma.  After the last ancilla measurement, one extra layer reads out all data
qubits in the memory basis.
Detectors (memory basis b): for every b-type check, its first measurement (deterministic), every comparison of
consecutive measurements, and the comparison of the last measurement with the parity of the final readout on its
support.  Observables: the 12 rows of L_b on the final readout.

This is the template used for every statement in the paper.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import stim

from .code import Code

FORMAT = "qec-schedule/v1"


@dataclass(frozen=True)
class CheckTiming:
    prep: int
    meas: int
    cnots: tuple[tuple[int, int], ...]   # (data qubit, time step), sorted by data qubit

    def offsets(self, P: int):
        dm = (self.meas - self.prep) % P
        return dm, tuple(sorted(((t - self.prep) % P, c) for c, t in self.cnots))


@dataclass(frozen=True)
class Schedule:
    period: int
    x_checks: tuple[CheckTiming, ...]
    z_checks: tuple[CheckTiming, ...]

    def to_dict(self) -> dict:
        ck = lambda c: {"prep": c.prep, "meas": c.meas, "cnots": [[a, t] for a, t in c.cnots]}  # noqa: E731
        return {"format": FORMAT, "period": self.period,
                "x_checks": [ck(c) for c in self.x_checks], "z_checks": [ck(c) for c in self.z_checks]}

    def shifted(self, s: int) -> "Schedule":
        P = self.period
        sh = lambda c: CheckTiming((c.prep + s) % P, (c.meas + s) % P,  # noqa: E731
                                   tuple((a, (t + s) % P) for a, t in c.cnots))
        return Schedule(P, tuple(sh(c) for c in self.x_checks), tuple(sh(c) for c in self.z_checks))

    def canonical(self) -> "Schedule":
        """global time shifts do not change the unrolled circuit up to sigma; pick the lexicographically smallest."""
        best = None
        for s in range(self.period):
            sh = self.shifted(s)
            key = json.dumps(sh.to_dict(), sort_keys=True, separators=(",", ":"))
            if best is None or key < best[0]:
                best = (key, sh)
        return best[1]

    def orders(self) -> tuple[list[list[int]], list[list[int]]]:
        """CNOT order (list of data qubits) of every X check and every Z check."""
        f = lambda c: [q for _, q in c.offsets(self.period)[1]]  # noqa: E731
        return [f(c) for c in self.x_checks], [f(c) for c in self.z_checks]


def parse_schedule(obj) -> Schedule:
    if isinstance(obj, (str, bytes)):
        obj = json.loads(obj)
    if hasattr(obj, "read"):
        obj = json.load(obj)
    assert obj["format"] == FORMAT, obj["format"]
    assert set(obj) <= {"format", "period", "x_checks", "z_checks", "name"}, sorted(obj)
    P = int(obj["period"])
    assert 2 <= P <= 64
    out = {}
    for key in ("x_checks", "z_checks"):
        cs = []
        for c in obj[key]:
            assert set(c) == {"prep", "meas", "cnots"}
            assert 0 <= c["prep"] < P and 0 <= c["meas"] < P
            pairs = tuple(sorted((int(a), int(t)) for a, t in c["cnots"]))
            assert all(0 <= t < P and a >= 0 for a, t in pairs)
            cs.append(CheckTiming(int(c["prep"]), int(c["meas"]), pairs))
        out[key] = tuple(cs)
    return Schedule(P, out["x_checks"], out["z_checks"])


def load_schedule(path) -> Schedule:
    return parse_schedule(json.load(open(path)))


def validate_schedule(spec: Schedule, code: Code) -> list[str]:
    """template constraints; returns a list of problems (empty = legal)."""
    problems = []
    P = spec.period
    for typ, H, checks in (("X", code.HX, spec.x_checks), ("Z", code.HZ, spec.z_checks)):
        if len(checks) != H.shape[0]:
            problems.append(f"{typ}: {len(checks)} checks for {H.shape[0]} rows")
            continue
        for i, c in enumerate(checks):
            supp = set(np.flatnonzero(H[i]).tolist())
            cols = [a for a, _ in c.cnots]
            if len(cols) != len(set(cols)) or set(cols) != supp:
                problems.append(f"{typ}{i}: CNOT targets {sorted(cols)} != row support {sorted(supp)}")
            dm, offs = c.offsets(P)
            if dm == 0:
                problems.append(f"{typ}{i}: prep and meas in the same step")
                continue
            if not all(0 < o < dm for o, _ in offs):
                problems.append(f"{typ}{i}: CNOT outside the window")
            if len({o for o, _ in offs}) != len(offs):
                problems.append(f"{typ}{i}: two CNOTs of the ancilla in one step")
    if problems:
        return problems
    use = {}
    for typ, checks in (("X", spec.x_checks), ("Z", spec.z_checks)):
        for i, c in enumerate(checks):
            for a, t in c.cnots:
                use.setdefault((t, a), []).append(f"{typ}{i}")
    problems += [f"data qubit {a} has CNOTs of {w} in step {t}" for (t, a), w in sorted(use.items()) if len(w) > 1]
    return problems


@dataclass(frozen=True)
class Layout:
    n: int
    x_anc: tuple[int, ...]
    z_anc: tuple[int, ...]


def layout_for(code: Code) -> Layout:
    n, mx, mz = code.n, code.HX.shape[0], code.HZ.shape[0]
    return Layout(n, tuple(range(n, n + mx)), tuple(range(n + mx, n + mx + mz)))


@dataclass(frozen=True)
class Unrolled:
    num_layers: int
    sigma: int
    start: dict      # ancilla -> layer of its round-0 reset
    preps: dict      # layer -> [(ancilla, type)]
    cnots: dict      # layer -> [(control, target)]
    meas: dict       # layer -> [(ancilla, type, round)]


def unroll(spec: Schedule, code: Code, rounds: int) -> Unrolled:
    assert rounds >= 1
    pr = validate_schedule(spec, code)
    assert not pr, pr[:5]
    P = spec.period
    lay = layout_for(code)
    info = {}
    for typ, checks, anc in (("X", spec.x_checks, lay.x_anc), ("Z", spec.z_checks, lay.z_anc)):
        for c, q in zip(checks, anc):
            dm, offs = c.offsets(P)
            info[q] = (typ, c.prep, dm, offs)
    best = None
    for sigma in range(P):
        start = {}
        for q, (_, tp, dm, offs) in info.items():
            s = sigma + tp - P
            if s < 0:
                s += P
            if s + offs[0][0] < 1:
                s += P
            start[q] = s
        end = max(start[q] + P * (rounds - 1) + info[q][2] for q in info)
        if best is None or end < best[0]:
            best = (end, sigma, start)
    end, sigma, start = best
    preps, cnots, meas = {}, {}, {}
    for q, (typ, _, dm, offs) in info.items():
        for j in range(rounds):
            s = start[q] + P * j
            preps.setdefault(s, []).append((q, typ))
            for o, col in offs:
                cnots.setdefault(s + o, []).append((q, col) if typ == "X" else (col, q))
            meas.setdefault(s + dm, []).append((q, typ, j))
    for t in range(end + 1):
        qs = [a for p_ in cnots.get(t, []) for a in p_] + [q for q, _ in preps.get(t, [])] + \
             [q for q, _, _ in meas.get(t, [])] + (list(range(lay.n)) if t == 0 else [])
        assert len(qs) == len(set(qs)), f"layer {t}: a qubit is used twice"
    return Unrolled(end + 1, sigma, dict(start), preps, cnots, meas)


def memory_circuit(spec: Schedule, code: Code, basis: str, rounds: int) -> stim.Circuit:
    """noiseless memory circuit in basis "Z" or "X" (see the module docstring)."""
    assert basis in ("X", "Z")
    U = unroll(spec, code, rounds)
    lay = layout_for(code)
    c = stim.Circuit()
    nmeas = 0
    rec = {}
    for t in range(U.num_layers):
        if t == 0:
            c.append("R" if basis == "Z" else "RX", list(range(lay.n)))
        px = sorted(q for q, typ in U.preps.get(t, []) if typ == "X")
        pz = sorted(q for q, typ in U.preps.get(t, []) if typ == "Z")
        if px:
            c.append("RX", px)
        if pz:
            c.append("R", pz)
        cn = sorted(U.cnots.get(t, []))
        if cn:
            c.append("CX", [a for p_ in cn for a in p_])
        for typ, gate in (("Z", "M"), ("X", "MX")):
            ms = sorted((q, j) for q, ty, j in U.meas.get(t, []) if ty == typ)
            if ms:
                c.append(gate, [q for q, _ in ms])
                for q, j in ms:
                    rec[(q, j)] = nmeas
                    nmeas += 1
        c.append("TICK")
    checks = {"X": lay.x_anc, "Z": lay.z_anc}
    for j in range(rounds):
        for i, q in enumerate(checks[basis]):
            cur = rec[(q, j)] - nmeas
            tg = [stim.target_rec(cur)] if j == 0 else [stim.target_rec(cur), stim.target_rec(rec[(q, j - 1)] - nmeas)]
            c.append("DETECTOR", tg, [i, j, 0 if basis == "X" else 1])
    c.append("M" if basis == "Z" else "MX", list(range(lay.n)))
    data_rec = {j: nmeas + j for j in range(lay.n)}
    nmeas += lay.n
    H = code.HZ if basis == "Z" else code.HX
    for i, q in enumerate(checks[basis]):
        tg = [stim.target_rec(data_rec[col] - nmeas) for col in np.flatnonzero(H[i])]
        tg.append(stim.target_rec(rec[(q, rounds - 1)] - nmeas))
        c.append("DETECTOR", tg, [i, rounds, 0 if basis == "X" else 1])
    L = code.LZ if basis == "Z" else code.LX
    for k, row in enumerate(L):
        c.append("OBSERVABLE_INCLUDE", [stim.target_rec(data_rec[col] - nmeas) for col in np.flatnonzero(row)], k)
    return c


def build_circuits(spec: Schedule, code: Code, rounds: int) -> dict[str, stim.Circuit]:
    return {b: memory_circuit(spec, code, b, rounds) for b in ("Z", "X")}
