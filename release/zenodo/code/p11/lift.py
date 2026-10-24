"""Extended lift (generalised Lemma 2) for the period-11 circuits and their relatives.

Lemma 2 (End Matter): with z faults of zero image and c pairs of faults with equal images, the remaining images of an
undetected logical of weight w form an extended logical of weight w - z - 2c >= d_ext.  So for w = d_ext the images
are d_ext distinct columns forming an extended logical, and for w = d_ext + 1 either d_ext + 1 distinct columns, or
d_ext distinct columns forming an extended logical plus one fault of zero image.  With the complete lists of the
extended logicals of weight d_ext and d_ext + 1, "no list entry lifts at R" <=> "no undetected logical of weight
<= d_ext + 1 at R" for that memory basis (weight < d_ext is excluded by Lemma 1 and d_ext).

  family gross (u11, controls):  d_ext = 10, lists of 144 (weight 10) and 7344 (weight 11) per basis
  family bb90  (c11, c12, c13, c16, controls u16, s16):  d_ext = 8, lists of 585 and 16830 per basis

For a circuit, a memory basis and R rounds the script builds the SD6 detector error model augmented with one
observable per row of H and of L on the final data readout and asserts, for every mechanism, that its image is 0 or
one column of the family's extended code, that the per-check detector parity equals the H part of the image and the
logical effect equals the L part (template identity, Lemma 1), and that every column is realised.  Then every list
entry is decided exactly by SAT (code/bb90/ext.py: CaDiCaL 1.5.3 via python-sat): one mechanism per column, in case
"+z" at most one additional zero-image mechanism (every zero-image mechanism of the DEM whose detectors lie in the
union of the groups' detectors is a candidate; in these circuits they are the ancilla readout flips), all detector
sums 0.  All entries are tested (no early stop).

    python code/p11/lift.py --circuit u11 --basis Z X --R 1-31          # expect 0 / 0 / 0 at every R (Theorem 1)
    python code/p11/lift.py --circuit c11 --basis Z X --R 1-25          # expect 0 / 0 / 0 at every R (Theorem 2)
    python code/p11/lift.py --circuit u11_control_p10 --R 1-2           # control: weight-11 lifts exist
Writes one JSON line per (basis, R) to stdout (and to --out); exit code 1 on any unexpected result.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_cli import Verdict, parse_range         # noqa: E402
from p11 import common as C                          # noqa: E402
from bb90 import ext as BE                           # noqa: E402

CONTROLS = {"u11_control_p10", "u11_control_segmented", "u16", "s16"}
ap = argparse.ArgumentParser()
ap.add_argument("--circuit", default="u11")
ap.add_argument("--basis", nargs="+", default=["Z", "X"])
ap.add_argument("--R", default="1-3")
ap.add_argument("--expect", choices=["none", "lifts"], default=None)
ap.add_argument("--out", default=None)
a = ap.parse_args()
expect = a.expect or ("lifts" if a.circuit in CONTROLS else "none")
fam = C.family_of(a.circuit)
D = C.FAMILY[fam]["dext"]
code = C.load_code(fam)
spec = C.circuit(a.circuit)
V = Verdict()
out = open(a.out, "a") if a.out else None
for basis in a.basis:
    keys = C.ext_keys_from_file(code, fam, basis)
    kc, _, _ = C.ext_columns(code, basis, spec)
    assert set(kc) == set(keys), "extended code of this circuit differs from the data file"
    lA, lB = C.load_list(fam, D, basis), C.load_list(fam, D + 1, basis)
    for R in parse_range(a.R):
        t0 = time.time()
        groups, zeros, st = BE.dem_terms(spec, code, R, basis, keys)
        lemma1 = (st["image_not_a_column"] == 0 and st["unrealised_columns"] == 0 and st["telescoping_bad"] == 0
                  and st["bad_obs"] == 0)
        res = BE.lift_counts(groups, zeros, lA, lB)
        nA, nAz, nB = res["w8"], res["w8z"], res["w9"]
        rec = {"circuit": a.circuit, "basis": basis, "R": R, "d_ext": D, f"w{D}": nA, f"w{D}z": nAz, f"w{D + 1}": nB,
               "first_hits": {f"w{D}": res["hits"]["w8"], f"w{D}z": res["hits"]["w8z"], f"w{D + 1}": res["hits"]["w9"]},
               **st, "sec": round(time.time() - t0, 1)}
        print(json.dumps(rec), flush=True)
        if out:
            out.write(json.dumps(rec) + "\n"); out.flush()
        tot = nA + nAz + nB
        ok = lemma1 and (tot == 0 if expect == "none" else tot > 0)
        V(ok, f"lift {a.circuit} basis {basis} R={R}: lifting w{D} {nA}/{len(lA)}, w{D}+zero-image {nAz}/{len(lA)}, "
              f"w{D + 1} {nB}/{len(lB)} (expected {'0' if expect == 'none' else '> 0'}); every one of "
              f"{st['mechanisms']} mechanisms has image 0 or one of the {len(keys)} columns, all realised, template "
              f"identity holds; zero-image mechanisms with detectors: {st['zero_image_with_detectors']} "
              f"({st['zero_image_readout_pattern']} of readout-flip pattern) ({rec['sec']} s)")
V.exit()
