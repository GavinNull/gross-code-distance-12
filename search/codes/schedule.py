"""Default syndrome-extraction schedules for enumerated codes (interface for code+circuit co-design).

`GroupAlgebraCode` exposes `n2`, `x_check_neighbor(t, i)` and `z_check_neighbor(t, i)` with the
same meaning as baselines.bb_code.BBCode (term t in [A1, A2, A3, B1, B2, B3]), so the E-002
generator baselines.schedule.bb_term_schedule(code, sX, sZ, name) works unchanged on it — for BB
codes with arbitrary monomials and for 2BGA codes over any group.  The default is IBM's depth-8
order (arXiv:2308.07915 Table 5): IBM_SX / IBM_SZ.

Validity: for abelian groups all six term matrices commute, which is what the IBM order relies on;
for a non-abelian 2BGA code L(a_i) and L(a_j) need not commute, so the IBM order may produce
non-deterministic detectors.  `check_schedule` therefore always runs (1) Schedule.validate and
(2) a noiseless stim memory circuit (both detector types) through baselines.circuit.check_deterministic.
Term order matters: the IBM order refers to A1, A2, A3 / B1, B2, B3 as listed in the code's a / b.
"""
from __future__ import annotations

from baselines.schedule import IBM_SX, IBM_SZ, Schedule, bb_term_schedule


def default_schedule(code, sX=None, sZ=None, name: str = "ibm_depth8") -> Schedule:
    return bb_term_schedule(code, IBM_SX if sX is None else sX, IBM_SZ if sZ is None else sZ, name)


def check_schedule(code, sched: Schedule, rounds=(1, 2), shots: int = 16) -> dict:
    """Structural validation + noiseless determinism in both memory bases."""
    from baselines.circuit import check_deterministic, memory_circuit
    css = code.to_css()
    out = {"valid_structure": False, "deterministic": False}
    try:
        sched.validate(css.HX, css.HZ)
        out["valid_structure"] = True
    except ValueError as e:
        out["error"] = str(e)
        return out
    ok = True
    for basis, L in (("Z", css.LZ), ("X", css.LX)):
        for r in rounds:
            c = memory_circuit(sched, css.HX, css.HZ, L, r, basis, 0.0, "both")
            try:
                res = check_deterministic(c, shots=shots)
                ok &= res["detector_flips"] == 0 and res["observable_flips"] == 0
            except Exception as e:   # stim raises on non-deterministic detectors
                ok = False
                out["error"] = f"{basis} r={r}: {type(e).__name__}: {str(e)[:200]}"
    out["deterministic"] = bool(ok)
    out["depth"] = sched.depth
    out["cnots_per_cycle"] = sum(len(L.cnots) for L in sched.layers)
    return out
