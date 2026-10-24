"""SM S13 (lift computation for circuits A, B, C): exact lift test of the weight-11 extended logicals.

For a circuit, a memory basis and a number of rounds R, build the SD6 detector error model augmented with one
observable per row of H and of L (so every mechanism carries its image = extended-code column), check the template
identity (per-check detector parity = H part of the image, logical effect = L part) and that the set of nonzero
images equals the 360 columns of the extended code; then, for each of the 4224 weight-11 logicals, ask CP-SAT for one
mechanism per column such that every detector sum vanishes.  'lifting = 0' at R means no weight-11 undetected
logical exists at R (with d_ext = 11, Lemma 1 excludes weight <= 10).

    python code/lift.py --circuit A --basis Z X --R 1-32            # SM S13 (expect lifting 0 at every R)
    python code/lift.py --circuit fig12 --basis Z X --R 1 --expect all   # positive control (expect 4224)
Writes one JSON line per (basis, R) to stdout (and to --out if given); exit code 1 on any unexpected result.
"""
import argparse
import json
import time

from common_cli import Verdict, circuit, load_code, parse_range
from gross12 import ext as E

ap = argparse.ArgumentParser()
ap.add_argument("--circuit", default="A", help="A, B, C, fig12, fig12_retiming_k")
ap.add_argument("--basis", nargs="+", default=["Z", "X"])
ap.add_argument("--R", default="1-3", help="e.g. 1-32 or 1,3,5")
ap.add_argument("--expect", choices=["none", "all"], default=None,
                help="none: no logical lifts (default for A, B, C); all: every logical lifts (default for fig12)")
ap.add_argument("--out", default=None)
a = ap.parse_args()
expect = a.expect or ("all" if a.circuit.startswith("fig12") else "none")
code = load_code()
spec = circuit(a.circuit)
V = Verdict()
out = open(a.out, "a") if a.out else None
for basis in a.basis:
    keys = E.ext_keys_from_file(code, basis)
    lists = [[keys[j] for j in S] for S in E.load_w11(basis)]
    assert len(lists) == 4224
    kc, _, _ = E.ext_columns(code, basis, spec)
    assert set(kc) == set(keys), "extended code of this circuit differs from the data file"
    for R in parse_range(a.R):
        t0 = time.time()
        groups, st = E.dem_groups(spec, code, R, basis)
        hits = [i for i, S in enumerate(lists) if E.lift(S, groups)]
        rec = {"circuit": a.circuit, "basis": basis, "R": R, "lifting": len(hits), "of": len(lists), **st,
               "image_set_equals_extended_code": set(groups) == set(keys), "sec": round(time.time() - t0, 1),
               "first_lifting": hits[:10]}
        print(json.dumps(rec), flush=True)
        if out:
            out.write(json.dumps(rec) + "\n"); out.flush()
        want = 0 if expect == "none" else len(lists)
        V(rec["lifting"] == want and rec["telescoping_bad"] == 0 and rec["bad_obs"] == 0
          and rec["image_set_equals_extended_code"],
          f"lift circuit {a.circuit} basis {basis} R={R}: {rec['lifting']}/{rec['of']} weight-11 logicals lift "
          f"(expected {want}); template identity holds for all {rec['mechanisms']} mechanisms; image set = "
          f"{rec['image_keys']} extended columns ({rec['sec']} s)")
V.exit()
