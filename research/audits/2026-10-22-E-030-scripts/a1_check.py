"""A1: code, legality, determinism, DEM equality with the experimenter's pipeline, weight-10 injection, IBM spec identity.
    PYTHONPATH=.:tests uv run python research/audits/2026-10-22-E-030-scripts/a1_check.py
Only read-only comparisons use project code (evaluator code matrices, experimenter's noisy() for DEM comparison)."""
import json
import sys
from collections import defaultdict

sys.path.insert(0, "research/audits/2026-10-22-E-030-scripts")
import numpy as np
from mylib import *

SPECS = {"c11": "search/experiments/e030/c11_spec.json", "c12": "search/experiments/e030/c12_spec.json",
         "c13": "search/experiments/e030/c13_spec.json", "ibm": "search/experiments/e030/ibm90_spec.json"}
out = {}
HX, HZ, LX, LZ = code_with_logicals()
from evaluators.tasks import build_code, get_task
ec, _ = build_code(get_task("bb90-dcirc"), None)
out["code_equal_evaluator"] = bool((np.asarray(ec.HX) % 2 == HX).all() and (np.asarray(ec.HZ) % 2 == HZ).all())
out["k"] = int(N - rank(HX) - rank(HZ))

# IBM spec file == experimenter's in-memory baseline spec (canonical)
from search.experiments.e030 import common as EC
s_ibm = EC.spec("ibm")
d_ibm = json.load(open(SPECS["ibm"]))
def canon(d):
    return (d["period"], tuple((c["prep"], c["meas"], tuple(sorted(map(tuple, c["cnots"])))) for c in d["x_checks"]),
            tuple((c["prep"], c["meas"], tuple(sorted(map(tuple, c["cnots"])))) for c in d["z_checks"]))
mem = {"period": s_ibm.period,
       "x_checks": [{"prep": c.prep, "meas": c.meas, "cnots": [list(x) for x in c.cnots]} for c in s_ibm.x_checks],
       "z_checks": [{"prep": c.prep, "meas": c.meas, "cnots": [list(x) for x in c.cnots]} for c in s_ibm.z_checks]}
out["ibm_json_equals_baseline_spec"] = canon(mem) == canon(d_ibm)


def detmap(circ_or_dem_terms):
    m = defaultdict(float)
    for dm, om, pr in circ_or_dem_terms:
        m[dm] += pr
    return m


def dem_of_stim(circ):
    t, _, _ = dem_terms(circ)
    return t


for name, path in SPECS.items():
    d = load_spec(path)
    r = {}
    # determinism + legality (assertions inside unroll) for R = 1..6
    for R in range(1, 7):
        for b in "ZX":
            c = memory_circuit(d, b, R)
            c.detector_error_model(allow_gauge_detectors=False)
            smp = c.compile_detector_sampler().sample(64, append_observables=True)
            assert not smp.any(), (name, b, R)
    r["deterministic_R1_6"] = True
    # pair-parity rule: on overlapping X/Z checks, number of shared qubits where X-CNOT precedes Z-CNOT (within the
    # same period frame measured from the X prep) -- report raw layers per round and checks per layer
    D = d["period"]
    layers, st, info, _ = unroll(d, 3)
    r["starts"] = sorted(set(st.values()))
    r["dm"] = sorted(set(v[2] for v in info.values()))
    # DEM equality with the experimenter's pipeline (detector part, probability per detector set)
    for lam, model in ((1.0, "lam1"), (0.0, "lam0"), (0.1, "lam0.1")):
        for b in "ZX":
            R, p = 3, 3e-3
            mine = detmap(dem_of_stim(memory_circuit(d, b, R, p, lam)))
            theirs = detmap(dem_of_stim(EC.noisy(name, b, R, p, model)))
            same_keys = set(mine) == set(theirs)
            mx = max(abs(mine[k] - theirs.get(k, 0)) / mine[k] for k in mine) if same_keys else None
            r[f"dem_{model}_{b}"] = {"cols": len(mine), "same_detsets": same_keys, "max_rel_dprob": mx}
    # weight-10 injection (own minimum-weight logical search not needed: use any weight-10 logical found below)
    out[name] = r
    print(name, json.dumps(r), flush=True)


# weight-10 logicals: verify the experimenter's supports under the own code, then inject in all circuits
inj = json.load(open("results/E-030-bb90-period-ler/inject10_c11_spec.json"))
supZ, supX = inj["Z"]["support"], inj["X"]["support"]
vZ = np.zeros(N, np.uint8); vZ[supZ] = 1     # X error for Z memory: must commute with Z checks (HZ v = 0)
vX = np.zeros(N, np.uint8); vX[supX] = 1
okZ = not ((HZ.astype(int) @ vZ) % 2).any() and ((LZ.astype(int) @ vZ) % 2).any()
okX = not ((HX.astype(int) @ vX) % 2).any() and ((LX.astype(int) @ vX) % 2).any()
out["w10_supports_are_logicals"] = {"Z": bool(okZ), "X": bool(okX)}
for name, path in SPECS.items():
    d = load_spec(path)
    res = {}
    for R in (1, 2, 5, 11):
        for b, sup in (("Z", supZ), ("X", supX)):
            c = memory_circuit(d, b, R, inject=sup)
            s = c.compile_detector_sampler().sample(1, append_observables=True)[0]
            nd = c.num_detectors
            res[f"{b}{R}"] = (int(s[:nd].sum()), int(s[nd:].sum()))
    out[f"inject_{name}"] = res
    print(name, res, flush=True)
json.dump(out, open("results/E-030-audit/a1_check.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if not isinstance(v, dict) or k.startswith("w10")}))
