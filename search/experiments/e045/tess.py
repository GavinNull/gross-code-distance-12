"""E-045 Part A: the Tesseract CZ-compiled gross circuits (Crocker's data), read as DATA only.  experimenter.

Input: the two circuit text files circuits/tesseract/bb144_{Z,X}.stim from Crocker's release_circ_gross.zip, copied
into results/E-045-crocker/data/ after their sha256 was checked.  Nothing from the zip is executed or imported; the
logic of the zip's code/dem_canon.py and code/build/restrict.py was read as text and is reimplemented here.

  * dem(basis)          stim DEM (decompose_errors=False, flattened), our own call
  * fingerprint(dem)    reimplementation of dem_canon.py: sha256 over the sorted SET of (detector tuple | observable
                        tuple) lines "E d1 d2 .. | o1 ..\n", then the sorted (detector id, coords) lines
                        "D k c1 c2 ..\n" with %g formatting; errors = number of distinct mechanisms
  * project(dem)        CSS projection onto the memory-basis detectors.  Type A = the coordinate parity class of the
                        first-round detectors (only the memory basis has first-round detectors).  Columns =
                        distinct (A-part, observables), empty ones dropped.
  * hypothesis_H        every full mechanism whose A-part or observable set is nonempty and which has B detectors has
                        its projection (A-part, obs) also as a full mechanism with NO B detectors; no full mechanism
                        flips an observable with no detector.  Under H the projected columns are exactly the full
                        mechanisms without B detectors, so a projected solution is a full-DEM solution as it stands.
    The lower bound does not need H: projecting an undetectable logical of the full DEM gives an undetectable
    logical of the projected DEM with at most as many columns (merged columns cancel in pairs), so "no logical of
    weight <= W after projection" implies the same for the full DEM.
  * source(basis)       E-037 dem_inst source dict: coords (check index, round) with check index = (x // 2) * 6 +
                        (y // 2) from the detector coordinates (x, y, t, colour); translations (a, b) act as
                        x -> x + 2a mod 24, y -> y + 2b mod 12.  dem_inst.build keeps a translation only if it maps
                        every column onto a column; we require all 72.

    uv run python -m search.experiments.e045.tess summary
"""
from __future__ import annotations

import collections
import hashlib
import json
import sys
from pathlib import Path

import stim

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "results" / "E-045-crocker" / "data"
SHA = {"Z": "9df52f6c08fba11f3ac049537e762d97f4dfc0d9fcc9c3b0ce9a5b7967d541df",
       "X": "0fb85d45348b399f6ea71f289992559edc059213c7f2bd8ccafeb48efe4decb2"}
CROCKER_FP = {"Z": ("0a221c464f7d801b04ed38010f0eea7f8ae4106b7a539a44d66a46009e5e9bbd", 67752, 1728),
              "X": ("ed1c91921d741b7e3406b034cc8ef40a8f656e0c11b0373442e6988f49049177", 67824, 1728)}


def path(basis):
    return DATA / f"bb144_{basis}.stim"


def circuit(basis):
    p = path(basis)
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    assert h == SHA[basis], ("circuit sha256 mismatch", basis, h)
    return stim.Circuit.from_file(str(p))


def dem(basis):
    return circuit(basis).detector_error_model(decompose_errors=False, flatten_loops=True).flattened()


def mechanisms(dm):
    """list of (detector tuple, observable tuple) per error instruction (XOR-reduced), detector coords dict"""
    errs, coords = [], {}
    for inst in dm:
        if inst.type == "error":
            d, o = set(), set()
            for t in inst.targets_copy():
                if t.is_relative_detector_id():
                    d ^= {t.val}
                elif t.is_logical_observable_id():
                    o ^= {t.val}
                elif t.is_separator():
                    raise SystemExit("decomposed DEM")
            errs.append((tuple(sorted(d)), tuple(sorted(o))))
        elif inst.type == "detector":
            for t in inst.targets_copy():
                coords[t.val] = tuple(inst.args_copy())
    return errs, coords


def fingerprint(dm):
    errs, coords = mechanisms(dm)
    es = set(errs)
    h = hashlib.sha256()
    for d, o in sorted(es):
        h.update(("E %s | %s\n" % (" ".join(map(str, d)), " ".join(map(str, o)))).encode())
    for k, c in sorted(coords.items()):
        h.update(("D %d %s\n" % (k, " ".join("%g" % x for x in c))).encode())
    return h.hexdigest(), len(es), len(coords), len(errs)


def project(dm):
    errs, coords = mechanisms(dm)
    nd = dm.num_detectors
    assert sorted(coords) == list(range(nd))
    first = [k for k in range(nd) if coords[k][2] == 0]
    par = {(int(coords[k][0]) % 2, int(coords[k][1]) % 2) for k in first}
    assert len(par) == 1, par
    par0 = par.pop()
    isA = [(int(coords[k][0]) % 2, int(coords[k][1]) % 2) == par0 for k in range(nd)]
    full = set(errs)
    nob = sum(1 for d, o in full if not d and o)
    bad, ok, pureB = 0, 0, 0
    restricted = set()
    allproj = set()
    for d, o in full:
        a = tuple(x for x in d if isA[x])
        b = tuple(x for x in d if not isA[x])
        if not a and not o:
            pureB += 1
            continue
        allproj.add((a, o))
        if b:
            if (a, o) in full:
                ok += 1
            else:
                bad += 1
        else:
            restricted.add((a, o))
    Aidx = [k for k in range(nd) if isA[k]]
    amap = {k: i for i, k in enumerate(Aidx)}
    cols = sorted((tuple(amap[x] for x in a), o) for a, o in allproj)
    H = dict(H_bad=bad, H_ok=ok, pureB=pureB, undetected_flip=nob, restricted=len(restricted), projected=len(allproj),
             equal=(restricted == allproj))
    return dict(cols=cols, Aidx=Aidx, coords=[coords[k] for k in Aidx], nA=len(Aidx), nB=nd - len(Aidx), H=H,
                nobs=dm.num_observables, isA=isA, full=full)


def source(basis):
    """E-037 dem_inst source for the projected DEM"""
    P = project(dem(basis))
    D = [c[0] for c in P["cols"]]
    L = [c[1] for c in P["cols"]]
    co = [(int(c[0]) // 2 * 6 + int(c[1]) // 2, int(round(c[2]))) for c in P["coords"]]
    assert len(set(co)) == len(co)
    # columns in time order (dem_inst orders orbits by first column index): sort by (min round, D)
    order = sorted(range(len(D)), key=lambda j: (min(co[x][1] for x in D[j]) if D[j] else -1, D[j], L[j]))
    D = [D[j] for j in order]
    L = [L[j] for j in order]
    return dict(D=D, L=L, ndet=P["nA"], nobs=P["nobs"], coords=co, l=12, m=6, desc=f"tess:gross:{basis}")


def summary():
    out = {}
    for b in ("Z", "X"):
        dm = dem(b)
        fp, ne, nd, nraw = fingerprint(dm)
        P = project(dm)
        rounds = collections.Counter(int(round(c[2])) for c in P["coords"])
        out[b] = dict(circuit_sha256=SHA[b], fingerprint=fp, crocker_fingerprint=CROCKER_FP[b][0],
                      fingerprint_match=fp == CROCKER_FP[b][0], errors_distinct=ne, error_instructions=nraw,
                      detectors=nd, crocker_counts=CROCKER_FP[b][1:], counts_match=(ne, nd) == CROCKER_FP[b][1:],
                      observables=dm.num_observables, projected_columns=len(P["cols"]), memory_detectors=P["nA"],
                      other_detectors=P["nB"], hypothesis=P["H"], memory_detectors_per_round=dict(sorted(rounds.items())))
        print(b, json.dumps(out[b]), flush=True)
    (ROOT / "results/E-045-crocker/tess_summary.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "summary":
        summary()
