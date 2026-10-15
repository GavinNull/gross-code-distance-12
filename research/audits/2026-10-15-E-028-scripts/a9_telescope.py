"""A9: telescoping identity on every augmented DEM term: XOR over rounds of check c's detectors = bit c of the H-part
of the term's image.  With it, an undetected fault set has H x_end = 0, so its image sum is an extended codeword whose
L-part equals the observable flip -> the lift case analysis is pure linear algebra given Table I and d_ext = 8."""
import sys, json
sys.path.insert(0, "research/audits/2026-10-15-E-028-scripts")
from alib import *
from a5_lift import augmented_terms
spec = load_spec(sys.argv[1]); out = {}
for basis in "ZX":
    for R in (1, 2, 3, 5):
        terms, nd = augmented_terms(spec, basis, R)
        bad = 0
        for d, (hb, lb) in terms:
            par = [0] * N2
            for x in d: par[x % N2] ^= 1
            bad += par != list(hb)
        out[f"{basis}R{R}"] = {"terms": len(terms), "telescoping_bad": bad}
print(json.dumps(out))
