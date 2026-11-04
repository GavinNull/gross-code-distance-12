"""E-045 Part A side question: is the projected Tesseract DEM (CZ + H compiled, SI1000 noise) the same detector error
model as our SD6 DEM of IBM's depth-8 circuit (E-037, sd6:gross:BASIS:12) up to relabelling the checks?
experimenter.

We search over check maps of the form  (u, v) -> (s_u * u + a, s_v * v + b)  on Z_12 x Z_6 (u = x // 2, v = y // 2 from
the Tesseract detector coordinates, and the evaluator's check index i = 6 u + v for SD6, rounds kept), s in {+1, -1}.
A map is an isomorphism of the column structure if it maps the set of detector sets onto the set of detector sets;
the observables are then compared modulo detectors: the two observable row spaces, transported, must span the same
space together with the detector rows (so "undetectable and flips some logical" is the same predicate).

    uv run python -m search.experiments.e045.iso
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "search/experiments/e037"))
import dem_inst  # noqa: E402
from search.experiments.e045 import tess  # noqa: E402


def span_rank(vs):
    piv = {}
    r = 0
    for v in vs:
        while v:
            b = v.bit_length() - 1
            if b not in piv:
                piv[b] = v
                r += 1
                break
            v ^= piv[b]
    return r


def rows(cols, n):
    out = [0] * n
    for j, c in enumerate(cols):
        for x in c:
            out[x] |= 1 << j
    return out


def compare(basis):
    T = tess.source(basis)
    S = dem_inst.load_source(f"sd6:gross:{basis}:12")
    assert len(T["D"]) == len(S["D"]) and T["ndet"] == S["ndet"]
    skey = {c: i for i, c in enumerate(S["coords"])}
    sindex = {tuple(d): j for j, d in enumerate(S["D"])}
    found = []
    for su in (1, -1):
        for sv in (1, -1):
            for a in range(12):
                for b in range(6):
                    def f(c):
                        u, v = divmod(c[0], 6)
                        return skey[(((su * u + a) % 12) * 6 + (sv * v + b) % 6, c[1])]
                    dm = [f(c) for c in T["coords"]]
                    P = []
                    for d in T["D"]:
                        j = sindex.get(tuple(sorted(dm[x] for x in d)))
                        if j is None:
                            break
                        P.append(j)
                    if len(P) != len(T["D"]):
                        continue
                    assert sorted(P) == list(range(len(P)))
                    # observables modulo detectors: transport T's observable rows to S's column indices
                    TL = rows(T["L"], T["nobs"])
                    TLt = []
                    for v in TL:
                        w, vv = 0, v
                        while vv:
                            bb = vv & -vv
                            w |= 1 << P[bb.bit_length() - 1]
                            vv ^= bb
                        TLt.append(w)
                    SD = rows(S["D"], S["ndet"])
                    SL = rows(S["L"], S["nobs"])
                    r0 = span_rank(SD)
                    rS = span_rank(SD + SL)
                    rT = span_rank(SD + TLt)
                    rB = span_rank(SD + SL + TLt)
                    found.append(dict(su=su, sv=sv, a=a, b=b, rank_D=r0, rank_DL_sd6=rS, rank_DL_tess=rT,
                                      rank_both=rB, same_logical_space=(rS == rT == rB == r0 + 12)))
    return found


def main():
    out = {}
    for basis in ("Z", "X"):
        out[basis] = compare(basis)
        print(basis, json.dumps(out[basis][:4]), "n_maps", len(out[basis]), flush=True)
    (ROOT / "results/E-045-crocker/iso.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
