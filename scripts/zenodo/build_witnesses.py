"""Build release/zenodo/witnesses/weight11_*.json.gz: explicit weight-11 undetected fault sets for Fig. 12
(all 4224 extended logicals per basis, R = 1, 2, 3) and for its four period-8 retimings (one per basis and
R = 1..6).  Uses only the package code (release/zenodo/code); verification by the package's verify_witnesses.py and,
for a sample, by the evaluator's distance.verify_faults.

    PYTHONPATH=.:tests:release/zenodo/code uv run python scripts/zenodo/build_witnesses.py
"""
import gzip
import json
import sys
import time

sys.path.insert(0, "release/zenodo/code")
import stim                                               # noqa: E402

from common_cli import circuit, load_code                 # noqa: E402
from gross12 import ext as E                              # noqa: E402
from gross12.faults import fault_from_location            # noqa: E402

code = load_code()
OUT = "release/zenodo/witnesses"


def tkey(targets):
    return tuple(sorted((("D" if t.is_relative_detector_id() else "L"), t.val) for t in targets
                        if t.is_relative_detector_id() or t.is_logical_observable_id()))


def witnesses(name, basis, R, which):
    spec = circuit(name)
    groups, st, aug, terms = E.dem_groups(spec, code, R, basis, with_terms=True)
    keys = E.ext_keys_from_file(code, basis)
    lists = E.load_w11(basis)
    chosen = []
    for i in which:
        S = [keys[j] for j in lists[i]]
        sol = E.lift(S, groups, want_solution=True)
        if sol is None:
            continue
        chosen.append((i, [terms[k][m] for k, m in zip(S, sol)]))
    uniq = {}
    for _, ts in chosen:
        for t in ts:
            uniq.setdefault(tkey(t.targets_copy()), t)
    filt = stim.DetectorErrorModel()
    for t in uniq.values():
        filt.append(t)
    ex = aug.explain_detector_error_model_errors(dem_filter=filt, reduce_to_one_representative_error=True)
    loc = {}
    for e in ex:
        k = tuple(sorted((("D" if x.dem_target.is_relative_detector_id() else "L"), x.dem_target.val)
                         for x in e.dem_error_terms))
        loc[k] = fault_from_location(e.circuit_error_locations[0])
    assert set(loc) == set(uniq), (len(loc), len(uniq))
    out = [{"logical": i, "faults": [loc[tkey(t.targets_copy())] for t in ts]} for i, ts in chosen]
    return out, st


cases = []
t0 = time.time()
for R in (1, 2, 3):
    for basis in "ZX":
        ws, st = witnesses("fig12", basis, R, range(4224))
        assert len(ws) == 4224, len(ws)
        cases.append({"circuit": "fig12", "basis": basis, "R": R, "witnesses": ws})
        print("fig12", basis, R, len(ws), round(time.time() - t0), flush=True)
json.dump({"description": "Fig. 12 of SBB: for every one of the 4224 weight-11 extended logicals per basis and "
                          "R = 1, 2, 3, eleven circuit faults realising it with no detector firing (format: "
                          "code/gross12/faults.py; 'logical' indexes data/logicals/weight11_logicals_<basis>_memory.json)",
           "cases": cases}, gzip.open(f"{OUT}/weight11_fig12.json.gz", "wt"), separators=(",", ":"))
cases = []
for k in range(4):
    name = f"fig12_retiming_{k}"
    for basis in "ZX":
        for R in range(1, 7):
            spec = circuit(name)
            # first lifting logical in list order
            groups, st = E.dem_groups(spec, code, R, basis)
            keys = E.ext_keys_from_file(code, basis)
            lists = E.load_w11(basis)
            i0 = next(i for i, S in enumerate(lists) if E.lift([keys[j] for j in S], groups))
            ws, _ = witnesses(name, basis, R, [i0])
            cases.append({"circuit": name, "basis": basis, "R": R, "witnesses": ws})
            print(name, basis, R, i0, round(time.time() - t0), flush=True)
json.dump({"description": "The four period-8 retimings of Fig. 12 that keep its CNOT orders (SM S9; retiming 0 is "
                          "Fig. 12 itself up to a global time shift): for each basis and R = 1..6 one set of eleven "
                          "circuit faults that fires no detector and flips a logical observable.",
           "cases": cases}, gzip.open(f"{OUT}/weight11_fig12_retimings.json.gz", "wt"), separators=(",", ":"))
print("done", round(time.time() - t0), "s")
