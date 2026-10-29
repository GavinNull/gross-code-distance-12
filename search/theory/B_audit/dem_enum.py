"""Item 6 (direct): exhaustive search for undetectable logical errors of weight <= W directly on the evaluator's SD6
DEM, with the auditor's C DFS (enum.c: lowest unsatisfied detector branching, sibling exclusion).  Seeds = orbit
representatives of the spatial translation group acting on DEM mechanisms (detector (row, round) -> (g row, round));
each job bans the mechanisms of smaller orbits.  A minimum-weight logical is irreducible (no proper zero-syndrome
subset), so the DFS (which stops at zero syndrome) finds one iff d_circ <= W.

  uv run python -m search.theory.B_audit.dem_enum bb108 results/theoryB/specs/bb108_u11tpl.json Z 1 9
"""
import json
import subprocess
import sys
import time

from search.theory.B_audit.common import ROOT, Bulk, get_code, load_spec_dict
from search.theory.B_audit.enum_driver import translations


def main():
    name, sp, basis, R, W = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
    from evaluators import candidate as cand
    from evaluators.noise import add_noise
    code = get_code(name)
    spec = load_spec_dict(sp)
    circ = add_noise(cand.memory_circuit(cand.parse_schedule(spec), code, basis, R), "sd6", 1e-3)
    coords = circ.get_detector_coordinates()
    dem = circ.detector_error_model(approximate_disjoint_errors=True, flatten_loops=True)
    errs = {}
    for e in dem.flattened():
        if e.type != "error":
            continue
        ds, os_ = set(), set()
        for t in e.targets_copy():
            if t.is_relative_detector_id():
                ds ^= {t.val}
            elif t.is_logical_observable_id():
                os_ ^= {t.val}
        if ds or os_:
            assert ds, "weight-1 logical"
            k = frozenset(ds)
            assert errs.get(k, frozenset(os_)) == frozenset(os_), "two mechanisms, same detectors, different obs"
            errs[k] = frozenset(os_)
    keys = sorted(errs, key=sorted)
    kid = {k: i for i, k in enumerate(keys)}
    det_of = {(int(c[0]), int(c[1])): d for d, c in coords.items()}
    B = Bulk(spec, code, basis)
    perms = translations(name, B, spec)
    colperm = []
    for qp, cp in perms:
        dmap = {d: det_of[(cp[int(c[0])], int(c[1]))] for d, c in coords.items()}
        colperm.append([kid[frozenset(dmap[x] for x in k)] for k in keys])
    orbit = [-1] * len(keys)
    reps = []
    for j in range(len(keys)):
        if orbit[j] < 0:
            reps.append(j)
            for pm in colperm:
                orbit[pm[j]] = len(reps) - 1
    nd = dem.num_detectors
    lines = [f"{len(k)} {' '.join(map(str, sorted(k)))} {sum(1 << o for o in errs[k])}" for k in keys]
    jobs = [f"{r} {sum(1 for j in range(len(keys)) if orbit[j] < oi)} " +
            " ".join(str(j) for j in range(len(keys)) if orbit[j] < oi) for oi, r in enumerate(reps)]
    inp = f"{len(keys)} {nd} {dem.num_observables} {W}\n" + "\n".join(lines) + f"\n{len(jobs)}\n" + "\n".join(jobs) + "\n"
    assert nd <= 256
    exe = "enum" if nd <= 128 else "enum256"
    t0 = time.time()
    pr = subprocess.run([str(ROOT / "results/theoryB_audit" / exe)], input=inp, capture_output=True, text=True, check=True)
    found = [ln for ln in pr.stdout.splitlines() if ln.startswith("S")]
    minw = min((int(ln.split()[1]) for ln in found), default=None)
    print(json.dumps({"code": name, "spec": sp, "basis": basis, "R": R, "W<=": W, "n_mech": len(keys), "n_det": nd,
                      "orbits": len(reps), "group": len(perms), "logicals_found": len(found), "min_weight_found": minw,
                      "sec": round(time.time() - t0, 1), "stderr_tail": pr.stderr.strip().splitlines()[-1:],
                      "example": found[:1]}), flush=True)


if __name__ == "__main__":
    main()
