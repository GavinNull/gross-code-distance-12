"""E-004 candidate (code, circuit) pairs.

Each candidate gives: CSSCode, a factory circuits(basis, rounds) -> noiseless memory circuit (L0/L2 convention),
data qubit ids, and metadata (n, k, code distance d, Q = 2n/k, pipelined flag).

Read-only use of search.codes (code construction, default_schedule) and baselines (schedules, circuit generators).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import stim

from baselines.circuit import memory_circuit, pipelined_memory_circuit
from baselines.schedule import IBM_SX, IBM_SZ, Schedule
from search.codes.construct import bb_code, coprime_bb_code
from search.codes.schedule import default_schedule


@dataclass
class Candidate:
    name: str
    code_name: str
    n: int
    k: int
    d: int                 # code distance (exact, MILP-proved in results/codes-screen-pilot)
    d_source: str
    schedule_name: str
    pipelined: bool
    sX: list | None = None
    sZ: list | None = None
    notes: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def Q(self) -> float:
        return 2 * self.n / self.k

    @property
    def kd2_n(self) -> float:
        return self.k * self.d ** 2 / self.n


# ----------------------------------------------------------------------------- codes
def _code(code_name: str):
    if code_name == "[[72,12,6]]":
        return bb_code(6, 6, "x^3+y+y^2", "y^3+x+x^2", name=code_name)
    if code_name == "[[90,8,10]]":
        return bb_code(15, 3, "x^9+y+y^2", "1+x^2+x^7", name=code_name)
    if code_name == "[[108,8,10]]":
        return bb_code(9, 6, "x^3+y+y^2", "y^3+x+x^2", name=code_name)
    if code_name == "[[144,12,12]]":
        return bb_code(12, 6, "x^3+y+y^2", "y^3+x+x^2", name=code_name)
    if code_name == "WMc[[126,12,10]]":
        return coprime_bb_code(7, 9, (0, 1, 58), (0, 13, 41), name=code_name)
    if code_name == "[[120,8,12]]":
        return bb_code(20, 3, "1+x^3y^2+x^7y^2", "1+x^16y+x^9y", name=code_name)
    raise KeyError(code_name)


CODE_META = {  # n, k, d, source of d
    "[[72,12,6]]": (72, 12, 6, "arXiv:2308.07915 Table 3; MILP exact in results/codes-screen-pilot/ibm_table3_check"),
    "[[90,8,10]]": (90, 8, 10, "arXiv:2308.07915 Table 3; MILP exact (pilot)"),
    "[[108,8,10]]": (108, 8, 10, "arXiv:2308.07915 Table 3; MILP exact (pilot)"),
    "[[144,12,12]]": (144, 12, 12, "arXiv:2308.07915 Table 3; MILP exact (pilot)"),
    "WMc[[126,12,10]]": (126, 12, 10, "arXiv:2408.10001 Table 2; MILP exact (pilot top20 #3)"),
    "[[120,8,12]]": (120, 8, 12, "pilot top20 #2, MILP exact; not in literature catalogue"),
}


@lru_cache(maxsize=None)
def code_obj(code_name: str):
    return _code(code_name)


# ----------------------------------------------------------------------------- candidates
# Deliberately degraded schedules: filled in by search/proxy/bad_schedules.py (term-order permutations of the
# IBM depth-8 cycle that stay deterministic but lose circuit distance).  See results/E-004-proxy-fidelity/bad_schedules.json
BAD = {}


def candidate_list() -> list[Candidate]:
    out = []
    for cn, tag in [("[[72,12,6]]", "BB72"), ("[[90,8,10]]", "BB90"), ("[[108,8,10]]", "BB108"),
                    ("WMc[[126,12,10]]", "CP126"), ("[[120,8,12]]", "BB120"), ("[[144,12,12]]", "G")]:
        n, k, d, src = CODE_META[cn]
        out.append(Candidate(f"{tag}-ibm", cn, n, k, d, src, "ibm_depth8", False))
    n, k, d, src = CODE_META["[[144,12,12]]"]
    out.append(Candidate("G-strikis", "[[144,12,12]]", n, k, d, src, "strikis_fig12", True,
                         notes="arXiv:2603.05481 Fig.12, pipelined across rounds (E-003)"))
    for name, (cn, sX, sZ, note) in BAD.items():
        n, k, d, src = CODE_META[cn]
        out.append(Candidate(name, cn, n, k, d, src, "perm", False, sX=list(sX), sZ=list(sZ), notes=note))
    return out


def load_bad(path) -> None:
    import json
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return
    for r in json.loads(p.read_text())["chosen"]:
        BAD[r["name"]] = (r["code"], r["sX"], r["sZ"], r.get("note", ""))


def get(name: str) -> Candidate:
    for c in candidate_list():
        if c.name == name:
            return c
    raise KeyError(name)


@lru_cache(maxsize=None)
def _schedule(name: str) -> Schedule:
    c = get(name)
    if c.schedule_name == "strikis_fig12":
        from baselines.bb_code import gross_code
        from baselines.strikis import strikis_fig12
        sched, _ = strikis_fig12(gross_code())
        return sched
    code = code_obj(c.code_name)
    if c.schedule_name == "ibm_depth8":
        return default_schedule(code)
    return default_schedule(code, c.sX, c.sZ, name=c.name)


def build(name: str):
    """-> (CSSCode, circuits(basis, rounds) -> noiseless stim.Circuit, data_qubits, Candidate)."""
    c = get(name)
    sched = _schedule(name)
    if c.schedule_name == "strikis_fig12":
        from baselines.bb_code import gross_code
        from evaluators.codes import CSSCode
        bb = gross_code()
        css = CSSCode.from_checks(bb.HX, bb.HZ, name="gross[[144,12,12]]")
        HX, HZ = bb.HX, bb.HZ
        Ls = {"Z": bb.logical_z(), "X": bb.logical_x()}
    else:
        css = code_obj(c.code_name).to_css()
        HX, HZ = css.HX, css.HZ
        Ls = {"Z": css.LZ, "X": css.LX}
    gen = pipelined_memory_circuit if c.pipelined else memory_circuit

    def circuits(basis: str, rounds: int) -> stim.Circuit:
        return gen(sched, HX, HZ, Ls[basis], rounds, basis, 0.0)

    return css, circuits, list(sched.data), c
