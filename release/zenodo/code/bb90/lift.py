"""Extended lift for [[90,8,10]] (d_ext = 8): no undetected logical of weight <= 9 for R = 1..12, both bases.

For a circuit, a memory basis and R rounds: build the SD6 detector error model augmented with one observable per row
of H and of L on the final data readout, and check for every mechanism that its image is 0 or one column of the
extended code (data/extended_code/bb90_extended_code_*), that the per-check detector parity equals the H part of
the image and the logical effect equals the L part, and that every column is realised.  Then, with d_ext = 8
(code/bb90/lists.py: no extended logical of weight <= 7), an undetected logical of weight <= 9 is one of
  w8   eight faults with distinct images forming a weight-8 extended logical             (585-entry list)
  w8z  the same plus one fault of zero image (case b; in c16 exactly the ancilla readout flips)
  w9   nine faults with distinct images forming a weight-9 extended logical             (16830-entry list, case a)
and each list entry is decided exactly (SAT, ext.lift).  Weight <= 7 is impossible (images would form an extended
logical of weight <= 7).  All entries are tested (no early stop); expected 0 / 0 / 0 for c16.

    python code/bb90/lift.py --circuit c16 --basis Z X --R 1-12        # expect 0 lifting at every R
    python code/bb90/lift.py --circuit u16 --basis Z --R 1 --expect lifts   # control: weight-9 lifts exist
Writes one JSON line per (basis, R) to stdout (and to --out if given); exit code 1 on any unexpected result.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_cli import Verdict, parse_range         # noqa: E402
from bb90 import bbcode, ext as E                   # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--circuit", default="c16")
ap.add_argument("--basis", nargs="+", default=["Z", "X"])
ap.add_argument("--R", default="1-3")
ap.add_argument("--expect", choices=["none", "lifts"], default=None)
ap.add_argument("--out", default=None)
a = ap.parse_args()
expect = a.expect or ("lifts" if a.circuit in ("u16", "s16") else "none")
code = bbcode.load_code()
spec = E.circuit(a.circuit)
V = Verdict()
out = open(a.out, "a") if a.out else None
for basis in a.basis:
    keys = E.ext_keys_from_file(code, basis)
    kc, _, _ = E.ext_columns(code, basis, spec)
    assert set(kc) == set(keys), "extended code of this circuit differs from the data file"
    l8, l9 = E.load_list(8, basis), E.load_list(9, basis)
    assert len(l8) == 585 and len(l9) == 16830
    for R in parse_range(a.R):
        t0 = time.time()
        groups, zeros, st = E.dem_terms(spec, code, R, basis, keys)
        lemma1 = (st["image_not_a_column"] == 0 and st["unrealised_columns"] == 0 and st["telescoping_bad"] == 0
                  and st["bad_obs"] == 0)
        res = E.lift_counts(groups, zeros, l8, l9)
        rec = {"circuit": a.circuit, "basis": basis, "R": R, "w8": res["w8"], "w8z": res["w8z"], "w9": res["w9"],
               "first_hits": res["hits"], **st, "sec": round(time.time() - t0, 1)}
        print(json.dumps(rec), flush=True)
        if out:
            out.write(json.dumps(rec) + "\n"); out.flush()
        tot = res["w8"] + res["w8z"] + res["w9"]
        ok = lemma1 and (tot == 0 if expect == "none" else tot > 0)
        V(ok, f"lift {a.circuit} basis {basis} R={R}: lifting w8 {res['w8']}/585, w8+zero-image {res['w8z']}/585, "
              f"w9 {res['w9']}/16830 (expected {'0' if expect == 'none' else '> 0'}); every one of "
              f"{st['mechanisms']} mechanisms has image 0 or one of the 225 columns, all realised, template identity "
              f"holds; zero-image mechanisms with detectors: {st['zero_image_with_detectors']} "
              f"({st['zero_image_readout_pattern']} of readout-flip pattern) ({rec['sec']} s)")
V.exit()
