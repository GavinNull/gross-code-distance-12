"""Auditor's own OPB encoder for "exists x: Hc x = 0, some translate of an L row odd on x, |x| <= W, no blocked set".

    uv run python myenc.py SOURCE BASIS W OUT.opb [LIST.json ...]
SOURCE: bb90 (columns from release/zenodo/data/circuits/bb90_c16.json, numbered as the release extended code)
        u11  (columns from search/experiments/e032/u11_spec.json, numbered in construction order; L = release LX/LZ)
Written independently of search/experiments/e031/build.py, in the same textual conventions (variable names, row
order = H rows then translated L rows in group order x L-row order, digit counts = minimal) so that the files can
be compared byte by byte; a semantic comparison is done separately by semcheck.py.
"""
import json
import math
import sys

import numpy as np

sys.path.insert(0, __import__("os").path.dirname(__file__))
from alib import DATA, ROOT, col_vec, ext_code  # noqa: E402

SRC = {"bb90": ("bb90", DATA / "circuits/bb90_c16.json", lambda b: DATA / f"extended_code/bb90_extended_code_{b}_memory.json"),
       "u11": ("gross", ROOT / "search/experiments/e032/u11_spec.json", lambda b: None)}


def instance(source, basis):
    code, spec, rel = SRC[source]
    E = ext_code(code, spec, basis, rel(basis))
    rows_c = [np.flatnonzero(E["Hc"][i]).tolist() for i in range(E["Hc"].shape[0])]
    lv, seen = [], set()
    for dp in E["dperms"]:
        for r in E["L"]:
            t = np.zeros(E["n"], dtype=np.uint8); t[dp[np.flatnonzero(r)]] = 1
            v = col_vec(E, t)
            if v.any() and v.tobytes() not in seen:
                seen.add(v.tobytes()); lv.append(v)
    rows_l = [np.flatnonzero(v).tolist() for v in lv]
    return E, rows_c, rows_l


def digits(maxsum):
    k = 1
    while 2 * (2 ** k - 1) < maxsum:
        k += 1
    return k


def encode(source, basis, W, lists=()):
    E, rc, rl = instance(source, basis)
    blocks = sorted({tuple(sorted(e["columns"])) for f in lists for e in json.load(open(f))["logicals"]})
    KC = digits(max(map(len, rc)))
    KL = digits(max(map(len, rl)) + 1)
    out = []
    for i, r in enumerate(rc):
        out.append(" ".join([f"1 x{j + 1}" for j in r] + [f"-{2 ** (k + 1)} a{i + 1}_{k}" for k in range(KC)]) + " = 0 ;")
    for i, r in enumerate(rl):
        out.append(" ".join([f"1 x{j + 1}" for j in r] + [f"1 q{i + 1}"] + [f"-{2 ** (k + 1)} b{i + 1}_{k}" for k in range(KL)]) + " = 0 ;")
    out.append(" ".join(f"-1 x{j + 1}" for j in range(E["N"])) + f" >= -{W} ;")
    out.append(" ".join(f"1 q{i + 1}" for i in range(len(rl))) + " >= 1 ;")
    for b in blocks:
        out.append(" ".join(f"1 ~x{j + 1}" for j in b) + " >= 1 ;")
    nv = E["N"] + len(rl) + len(rc) * KC + len(rl) * KL
    return f"* #variable= {nv} #constraint= {len(out)}\n" + "\n".join(out) + "\n", E, rc, rl, blocks


if __name__ == "__main__":
    src, basis, W, out = sys.argv[1:5]
    txt = encode(src, basis, int(W), sys.argv[5:])[0]
    open(out, "w").write(txt)
