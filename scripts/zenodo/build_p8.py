"""Build data/circuits/p8_colour_symmetric_944.json.gz (enumeration of the package's p8_family.py, cross-checked
against the 944 circuits of the original search) and witnesses/weight11_p8_colour_symmetric_944.json.gz (for every
circuit one weight-11 undetected fault set at R = 1, Z basis).
    PYTHONPATH=.:tests uv run python scripts/zenodo/build_p8.py
"""
import glob
import gzip
import json
import sys
import time

sys.path.insert(0, "release/zenodo/code")
import p8_family as P8                        # noqa: E402
from gross12.schedule import parse_schedule   # noqa: E402

t0 = time.time()
sols = P8.enumerate_family()
assert len(sols) == 944
mine = {P8.canon(P8.expand(e)) for e in sols}
theirs = {json.dumps(parse_schedule(json.load(open(f))).canonical().to_dict(), sort_keys=True)
          for f in glob.glob("results/E-021-gross-new-orders/p8class_H24_spec*.json")}
assert mine == theirs and len(theirs) == 944, (len(mine), len(theirs), len(mine & theirs))
print("enumeration == original 944", round(time.time() - t0), "s")
with gzip.open(P8.FILE, "wt") as f:
    json.dump({"description": "The 944 legal deterministic colour-symmetric period-8 circuits with CNOT orders in the "
                              "class of Fig. 12 (SM S10). Each entry: (variant, start) of the classes X0 X1 X2 Z0 Z1 "
                              "Z2; expansion rule in code/p8_family.py.", "circuits": sols}, f)
import stim                                               # noqa: E402
from common_cli import circuit, load_code                 # noqa: E402
from gross12 import ext as E                              # noqa: E402
from gross12.faults import fault_from_location            # noqa: E402

code = load_code()


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
keys = E.ext_keys_from_file(code, "Z")
lists = E.load_w11("Z")
for k in range(944):
    name = f"p8:{k}"
    groups, st = E.dem_groups(circuit(name), code, 1, "Z")
    i0 = next(i for i, S in enumerate(lists) if E.lift([keys[j] for j in S], groups))
    ws, _ = witnesses(name, "Z", 1, [i0])
    cases.append({"circuit": name, "basis": "Z", "R": 1, "witnesses": ws})
    if k % 100 == 0:
        print(k, round(time.time() - t0), flush=True)
json.dump({"description": "For each of the 944 period-8 colour-symmetric circuits (data/circuits/"
                          "p8_colour_symmetric_944.json.gz, circuit 'p8:k'), one weight-11 fault set that fires no "
                          "detector and flips a logical observable in the Z-basis memory with R = 1.",
           "cases": cases}, gzip.open("release/zenodo/witnesses/weight11_p8_colour_symmetric_944.json.gz", "wt"),
          separators=(",", ":"))
print("done", round(time.time() - t0), "s")
