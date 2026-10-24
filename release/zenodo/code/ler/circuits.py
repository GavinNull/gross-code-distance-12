"""The circuits of the logical-error-rate comparisons, by the names used in the sampling statistics.

family gross: u11 (data/circuits/u11.json), fig12 (fig12.json), ibm (ibm_gross_depth8.json);
family bb90:  c11, c12, c13, c16 (bb90_c1*.json), ibm and ibm90 (bb90_ibm_depth8.json).
Noiseless memory circuits: the template of code/gross12/schedule.py (data reset in layer 0, per round reset -> six
CNOTs -> measurement for every check, detectors of the memory basis, observables = rows of L of the memory basis).
"""
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gross12.paths import CIRCUITS                       # noqa: E402
from gross12.schedule import load_schedule, memory_circuit, validate_schedule   # noqa: E402

FILES = {"gross": {"u11": "u11.json", "fig12": "fig12.json", "ibm": "ibm_gross_depth8.json"},
         "bb90": {"c11": "bb90_c11.json", "c12": "bb90_c12.json", "c13": "bb90_c13.json", "c16": "bb90_c16.json",
                  "ibm": "bb90_ibm_depth8.json", "ibm90": "bb90_ibm_depth8.json"}}
GRID = {"gross": (12, 6), "bb90": (15, 3)}


@lru_cache(maxsize=None)
def code(fam):
    if fam == "gross":
        from gross12.code import load_code
        return load_code()
    from bb90 import bbcode
    return bbcode.load_code()


@lru_cache(maxsize=None)
def spec(fam, name):
    s = load_schedule(CIRCUITS / FILES[fam][name]).canonical()
    assert not validate_schedule(s, code(fam))
    return s


@lru_cache(maxsize=None)
def noiseless(fam, name, basis, rounds):
    return memory_circuit(spec(fam, name), code(fam), basis, rounds)
