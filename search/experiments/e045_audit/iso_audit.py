"""E-045 audit: is the projected Tesseract DEM (my projection, tess_audit.py) column-isomorphic to the evaluator SD6 DEM
of IBM's depth-8 gross circuit at R = 12 (built by the E-037 audit's independent mydem.sd6)?  auditor.

Test family: detector (u, v, t) -> (su * u + a, sv * v + b, t) with u = x // 2, v = y // 2 from the Tesseract detector
coordinates and the SD6 check index i = 6 u + v (also tried: i = u + 12 v, i.e. the other convention).  For each map:
  (1) it is a bijection of detectors; (2) the image of every Tesseract detector set is an SD6 column's detector set and
  the induced column map is a bijection (column D-sets are distinct on both sides, checked); (3) logical predicate:
  span(D rows, transported Tesseract L rows) = span(D rows, SD6 L rows), with rank(D) and rank(D;L) reported.
Then "undetectable and flips some observable" is the same predicate on both column sets, so the weight-<= W questions
coincide.

  uv run python -m search.experiments.e045_audit.iso_audit
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from search.experiments.e037_audit import mydem  # noqa: E402

OUT = ROOT / "results/E-045-audit"


def rank(vs):
    piv, r = {}, 0
    for v in vs:
        while v:
            b = v.bit_length() - 1
            if b not in piv:
                piv[b] = v; r += 1
                break
            v ^= piv[b]
    return r


def rows(sets, n):
    out = [0] * n
    for j, s in enumerate(sets):
        for x in s:
            out[x] |= 1 << j
    return out


def run(basis):
    T = json.loads((OUT / f"tess_proj_{basis}.json").read_text())
    S = mydem.sd6("gross", basis, 12)
    TD = [tuple(c[0]) for c in T["cols"]]; TL = [tuple(c[1]) for c in T["cols"]]
    assert len(set(TD)) == len(TD) and len(set(S["D"])) == len(S["D"])
    sidx = {frozenset(d): j for j, d in enumerate(S["D"])}
    skey = {tuple(c): k for k, c in enumerate(S["coords"])}
    tuvt = [(int(c[0]) // 2, int(c[1]) // 2, int(round(c[2]))) for c in T["coords"]]
    assert len(set(tuvt)) == len(tuvt)
    SD = rows(S["D"], S["ndet"]); SL = rows(S["L"], S["nobs"])
    rD = rank(SD); rS = rank(SD + SL)
    found = []
    for conv in ("6u+v", "u+12v"):
        for su in (1, -1):
            for sv in (1, -1):
                for a in range(12):
                    for b in range(6):
                        def idx(u, v):
                            u, v = (su * u + a) % 12, (sv * v + b) % 6
                            return 6 * u + v if conv == "6u+v" else u + 12 * v
                        dm = [skey.get((idx(u, v), t)) for u, v, t in tuvt]
                        if None in dm or len(set(dm)) != len(dm):
                            continue
                        P = []
                        for d in TD:
                            j = sidx.get(frozenset(dm[x] for x in d))
                            if j is None:
                                break
                            P.append(j)
                        if len(P) != len(TD) or len(set(P)) != len(P):
                            continue
                        TLrows = [0] * T["nobs"]
                        for j, os_ in enumerate(TL):
                            for o in os_:
                                TLrows[o] |= 1 << P[j]
                        rT = rank(SD + TLrows); rB = rank(SD + SL + TLrows)
                        found.append(dict(conv=conv, su=su, sv=sv, a=a, b=b, rank_D=rD, rank_DL_sd6=rS, rank_DL_tess=rT,
                                          rank_all=rB, same=(rS == rT == rB)))
    summ = dict(basis=basis, ncols=len(TD), ndet=S["ndet"], n_maps=len(found), n_same=sum(f["same"] for f in found),
                kinds=sorted({(f["conv"], f["su"], f["sv"]) for f in found}), rank_D=rD, rank_DL=rS,
                example=found[0] if found else None)
    print(json.dumps(summ), flush=True)
    return summ, found


if __name__ == "__main__":
    res = {}
    for b in ("Z", "X"):
        res[b] = run(b)
    (OUT / "iso_audit.json").write_text(json.dumps(res, indent=1))
