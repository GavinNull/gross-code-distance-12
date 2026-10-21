"""A3: own exact lift for weight <= 9 (own encoder incl. wrapping, own logicals, own extended code, per-S SAT).
Lists: complete weight-8 (585) / weight-9 (16830) extended-logical lists of the class A1A2A3B2B1B3 produced by the
E-028 AUDIT (own MITM, results/E-028-audit/ext_c16_<kind>.pkl), re-keyed by support under the own code and
re-verified; usable only if the circuit's own extended code has exactly the same column key set (asserted).
For each R, basis:
  - DEM (SD6, lam = 1) of the own circuit with image observables: 8 logicals, then rows of H, rows of L on the final
    data readout.  Each term: (detector mask, image key).  Assert: logical bits == L part of the image;
    every non-zero image is ONE column of the own extended code (Lemma 1); every column is realised.
  - telescoping identity asserted for every term.
  - counts: w8 = 8-sets lifting with one term per column and detector XOR = 0;  w8z = 8-sets + exactly one
    zero-image term;  w9 = 9-sets.  (Weight <= 7 impossible: d_ext = 8 and every fault image is 0 or one column;
    a weight-9 undetected logical is either a w9 or a w8z lift -- counting argument of the E-028 audit.)
Usage: a3_lift.py SPEC BASIS R1 R2 ... [--stop]"""
import json
import pickle
import sys
import time

sys.path.insert(0, "research/audits/2026-10-22-E-030-scripts")
import numpy as np
from pysat.solvers import Minisat22
from mylib import *

args = [a for a in sys.argv[1:] if not a.startswith("--")]
STOP = "--stop" in sys.argv
spec_path, basis = args[0], args[1]
Rs = [int(x) for x in args[2:]]
d = load_spec(spec_path)
HX, HZ, LX, LZ = code_with_logicals()
kind = "X" if basis == "Z" else "Z"         # error type seen by this memory basis
H, Lg = (HZ, LZ) if basis == "Z" else (HX, LX)
nH, k = H.shape[0], Lg.shape[0]


def key_of_sup(S):
    v = np.zeros(N, np.uint8); v[list(S)] = 1
    return tuple(int(x) for x in (H.astype(int) @ v) % 2) + tuple(int(x) for x in (Lg.astype(int) @ v) % 2)


# own extended code of this spec
chk = d["x_checks"] if kind == "X" else d["z_checks"]
sups = [(q,) for q in range(N)]
for c in chk:
    order = [a for a, t in sorted(c["cnots"], key=lambda x: (x[1] - c["prep"]) % d["period"])]
    for kk in range(1, 6):
        sups.append(tuple(sorted(order[kk:])))
mycols = {}
for S in sups:
    kk = key_of_sup(S)
    if any(kk):
        mycols.setdefault(kk, S)
# lists from the E-028 audit, re-keyed
E = pickle.load(open(f"results/E-028-audit/ext_c16_{kind}.pkl", "rb"))
rekey = [key_of_sup(E["cols"][kk][0]) for kk in E["keys"]]
for kk in E["keys"]:
    ks = {key_of_sup(s) for s in E["cols"][kk]}
    assert len(ks) == 1
assert set(rekey) == set(mycols), "extended code differs from the class of the lists"
colidx = {kk: j for j, kk in enumerate(rekey)}
lists = {8: [tuple(rekey[j] for j in S) for S in E["s8"]], 9: [tuple(rekey[j] for j in S) for S in E["s9"]]}
for w, L in lists.items():
    for S in L:
        tot = np.zeros(nH + k, np.int64)
        for kk in S:
            tot += np.array(kk)
        tot %= 2
        assert not tot[:nH].any() and tot[nH:].any() and len(set(S)) == w
res_all = []
for R in Rs:
    t0 = time.time()
    circ = memory_circuit(d, basis, R, 1e-3, 1.0, image_obs=True)
    terms, nd, no = dem_terms(circ)
    assert no == k + nH + k
    by_col, zero = {}, []
    for dm, om, _ in terms:
        logic = om & ((1 << k) - 1)
        img = tuple((om >> (k + r)) & 1 for r in range(nH + k))
        assert logic == sum(img[nH + r] << r for r in range(k)), "observable != L part of image"
        # telescoping: XOR over rounds of detectors of check c == H bit c of the image
        for c in range(nH):
            par = 0
            for j in range(R + 1):
                par ^= (dm >> (j * nH + c)) & 1
            assert par == img[c]
        if not any(img):
            assert dm, "detector-free zero-image term"
            zero.append(dm)
        else:
            assert img in colidx, "Lemma 1 violated: image is not a single extended-code column"
            by_col.setdefault(img, []).append(dm)
    assert set(by_col) == set(colidx), "some column not realised"
    cnt = {"w8": 0, "w8z": 0, "w9": 0}
    wit = []

    def lift(S, zcands):
        vid, var_det = {}, {}
        cl = []
        top = 0
        groups = []
        for kk in S:
            g = []
            for dm in by_col[kk]:
                top += 1; g.append(top); vid[top] = dm
            groups.append(g)
        for g in groups:
            cl.append(list(g))
            for a in range(len(g)):
                for b in range(a + 1, len(g)):
                    cl.append([-g[a], -g[b]])
        if zcands is not None:
            zg = []
            for dm in zcands:
                top += 1; zg.append(top); vid[top] = dm
            if not zg:
                return None
            cl.append(list(zg))
            for a in range(len(zg)):
                for b in range(a + 1, len(zg)):
                    cl.append([-zg[a], -zg[b]])
        for v, dm in vid.items():
            x = dm
            while x:
                low = x & -x
                var_det.setdefault(low.bit_length() - 1, []).append(v)
                x ^= low
        for det, vs in var_det.items():
            cur = vs[0]
            for v in vs[1:]:
                top += 1; y = top
                cl += [[-cur, -v, -y], [cur, v, -y], [cur, -v, y], [-cur, v, y]]
                cur = y
            cl.append([-cur])
        with Minisat22(bootstrap_with=cl) as s:
            if s.solve():
                m = set(x for x in s.get_model() if x > 0)
                return [vid[v] for v in vid if v in m]
        return None

    for w, mode in ((8, "w8"), (8, "w8z"), (9, "w9")):
        for S in lists[w]:
            zc = None
            if mode == "w8z":
                U = 0
                for kk in S:
                    for dm in by_col[kk]:
                        U |= dm
                zc = [z for z in zero if z & ~U == 0]
            sol = lift(S, zc)
            if sol is not None:
                x = 0
                for dm in sol:
                    x ^= dm
                assert x == 0
                cnt[mode] += 1
                if len(wit) < 3:
                    wit.append((mode, len(sol)))
                if STOP:
                    break
    r = {"spec": spec_path, "basis": basis, "R": R, "terms": len(terms), "zero_terms": len(zero),
         "cols": len(by_col), **cnt, "wit": wit, "sec": round(time.time() - t0, 1)}
    print(json.dumps(r), flush=True)
    with open("results/E-030-audit/a3_lift.jsonl", "a") as f:
        f.write(json.dumps(r) + "\n")
