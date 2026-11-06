"""witnesses/persistence_R1.json (version 3.0): the R = 1 undetected logicals of g9, b9, b10 and IBM's depth-8 circuits
used for the upper bounds of Table I, as located physical faults (from the audit's stim persistence check,
results/E-043-audit/persist.jsonl).  Asserts that the package's noiseless circuits equal the evaluator's memory circuits
(flattened, R = 1..3, both bases), so that the TICK boundaries refer to the same layers.

    PYTHONPATH=.:tests:release/zenodo/code uv run python scripts/zenodo/build_v3_witnesses.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "tests")
sys.path.insert(0, "release/zenodo/code")
from evaluators import candidate as cand                     # noqa: E402
from evaluators.tasks import build_code, get_task            # noqa: E402
from gross12 import schedule as PS                           # noqa: E402
from p11 import common as P                                  # noqa: E402

REL = Path("release/zenodo")
NAME = {"ibmg": ("ibm_gross_depth8", "gross"), "ibm90": ("bb90_ibm_depth8", "bb90"), "g9": ("g9", "gross"),
        "b9": ("bb90_b9", "bb90"), "b10": ("bb90_b10", "bb90")}
codes = {"gross": P.load_code("gross"), "bb90": P.load_code("bb90")}
ev = {"gross": build_code(get_task("gross-dcirc"), None)[0], "bb90": build_code(get_task("bb90-dcirc"), None)[0]}
for tag, (name, fam) in NAME.items():
    d = json.load(open(REL / "data" / "circuits" / f"{name}.json"))
    sp = PS.parse_schedule(d)
    se = cand.parse_schedule({k: v for k, v in d.items() if k != "name"})
    for R in (1, 2, 3):
        cp = PS.build_circuits(sp.canonical(), codes[fam], R)
        for b in "ZX":
            assert str(cp[b].flattened()) == str(cand.memory_circuit(se, ev[fam], b, R).flattened()), (name, R, b)
out = []
for l in open("results/E-043-audit/persist.jsonl"):
    r = json.loads(l)
    name, fam = NAME[r["name"]]
    assert r["all_ok"] and r["R0"] == 1
    out.append({"circuit": name, "basis": r["basis"], "R0": 1, "weight": r["weight"], "observables": r["obs"],
                "faults": r["faults"],
                "replayed": sorted({(x["R"], x["shift_rounds"]) for x in r["runs"]})})
json.dump({"description": "Undetected logicals of the one-round memory circuit (R = 1) of g9, b9, b10 and IBM's "
                          "depth-8 circuits, one per memory basis, found by an exhaustive search of the SD6 detector "
                          "error model (weights 11, 9, 9, 10, 8 = the upper bounds of Table I). Each fault: [TICK "
                          "boundary b of the one-round noiseless circuit (0 = before the first layer), {qubit: Pauli}, "
                          "noise channel the representative fault comes from]. 'observables' = flipped rows of L of "
                          "the memory basis. Replayed by code/tclass/persist.py for R up to 30, at the start and "
                          "shifted by two rounds.", "witnesses": out}, open(REL / "witnesses" / "persistence_R1.json", "w"),
          indent=1)
print(len(out), "witnesses; package circuits == evaluator memory circuits")
