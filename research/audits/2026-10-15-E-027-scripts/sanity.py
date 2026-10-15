"""(i) the 4224 listed weight-11 objects are extended-code logicals (11 distinct columns, H sum 0, L sum != 0), recomputed
from column supports; (ii) template identity on the auditor's own fault propagation: per-check detector parity of every
fault equals the H part of its image (detector -> check from the template's DETECTOR coordinates)."""
import json, sys
import numpy as np
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import indep_lift as IL
from gross12.schedule import build_circuits
from common_cli import circuit, load_code
code = load_code()
for basis in "ZX":
    H, L = (code.HZ, code.LZ) if basis == "Z" else (code.HX, code.LX)
    d = json.load(open(IL.PKG / "data/extended_code" / f"extended_code_{basis}_memory.json"))
    sup = [c["support"] for c in d["columns"]]
    lists = json.load(open(IL.PKG / "data/logicals" / f"weight11_logicals_{basis}_memory.json"))["logicals"]
    bad = 0
    seen = set()
    for e in lists:
        cs = e["columns"]
        v = np.zeros(code.n, np.int64)
        for j in cs:
            v[sup[j]] ^= 1
        ok = len(set(cs)) == 11 and not ((H @ v) % 2).any() and ((L @ v) % 2).any()
        bad += not ok
        seen.add(tuple(sorted(cs)))
    print(basis, "listed:", len(lists), "distinct:", len(seen), "not a weight-11 logical:", bad)
for circ, basis, R in [("A", "Z", 3), ("A", "X", 2), ("C", "Z", 4), ("fig12", "X", 2)]:
    eff = IL.faults_and_effects(circ, R, basis)
    c = build_circuits(circuit(circ).canonical(), code, R)[basis]
    coords = c.get_detector_coordinates()
    chk = np.array([int(coords[i][0]) for i in range(eff["ndet"])])
    nH = eff["Hi"].shape[0]
    P = np.zeros((nH, eff["D"].shape[1]), bool)
    for i in range(eff["ndet"]):
        P[chk[i]] ^= eff["D"][i]
    print(circ, basis, R, "faults", eff["F"], "template identity violations:", int((P != eff["Hi"]).any(axis=0).sum()))
