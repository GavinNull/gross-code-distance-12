"""Meet-in-the-middle enumeration of all extended-code logicals of weight w (distinct merged columns, H-sum 0,
L-sum != 0) for small codes.  Output: pickle {"keys": [[key bytes]*w], "colset": [...], "meta": {...}} in the format of
the E-032 lists.

  uv run python -m search.theory.B.enum --code bb72 --spec results/theoryB/bb72_u11_spec.json --basis Z --w 4 \
      --out results/theoryB/bb72_u11_w4_Z.pkl
"""
from __future__ import annotations

import argparse
import itertools
import json
import pickle
import time
from collections import defaultdict

import numpy as np

from search.theory.B.bulk import ROOT, Sched, code_mats, load_spec


def enumerate_w(sch, cols, w):
    keys = sorted(cols)
    nh = sch.H.shape[0]
    V = [np.frombuffer(k, np.uint8) for k in keys]
    Hs = [v[:nh] for v in V]
    a = w // 2
    b = w - a
    tab = defaultdict(list)
    for S in itertools.combinations(range(len(keys)), a):
        h = np.bitwise_xor.reduce([Hs[i] for i in S]) if S else np.zeros(nh, np.uint8)
        tab[h.tobytes()].append(S)
    found = set()
    for T in itertools.combinations(range(len(keys)), b):
        h = np.bitwise_xor.reduce([Hs[i] for i in T])
        for S in tab.get(h.tobytes(), ()):
            if set(S) & set(T):
                continue
            U = tuple(sorted(S + T))
            if U in found:
                continue
            lv = np.bitwise_xor.reduce([V[i][nh:] for i in U])
            if lv.any():
                found.add(U)
    return [[keys[i] for i in U] for U in sorted(found)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--basis", default="Z")
    ap.add_argument("--w", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sch = Sched(load_spec(a.spec), code_mats(a.code), a.basis)
    cols, zero = sch.ext()
    t0 = time.time()
    L = enumerate_w(sch, cols, a.w)
    meta = {"code": a.code, "spec": a.spec, "basis": a.basis, "w": a.w, "ncols": len(cols), "n": len(L),
            "zero_image_hooks": len(zero), "sec": round(time.time() - t0, 1)}
    pickle.dump({"keys": L, "colset": sorted(cols), "meta": meta}, open(ROOT / a.out, "wb"))
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
