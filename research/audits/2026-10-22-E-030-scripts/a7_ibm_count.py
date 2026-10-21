"""A7: independent count of minimum-weight undetected logicals of the IBM [[90,8,10]] depth-8 circuit (claim 4),
by a different algorithm than ccsearch: own extended code of the IBM orders -> complete low-weight extended-logical
lists by meet-in-the-middle (E-028 AUDIT tool results/E-028-audit/mitm, with own keys and own orbit split) -> on the
own DEM with image observables (Lemma 1 asserted), enumerate ALL lifts (all SAT models, blocking clauses), map to
plain-DEM signatures (detector set, logical-observable set), dedupe, count.
Weight-8 undetected logicals decompose (counting argument) as: e ext-logical columns (distinct images, each one
term) + z zero-image terms + c pairs of terms with equal non-zero image, e + z + 2c = 8, e >= d_ext.  This script
handles the cases allowed by the computed d_ext (asserts d_ext >= 8 => only e = 8, z = c = 0; otherwise stops).
    uv run python research/audits/2026-10-22-E-030-scripts/a7_ibm_count.py BASIS R1 R2 ..."""
import json
import subprocess
import sys

sys.path.insert(0, "research/audits/2026-10-22-E-030-scripts")
import numpy as np
from pysat.solvers import Minisat22
from mylib import *

basis = sys.argv[1]
Rs = [int(x) for x in sys.argv[2:]]
d = load_spec("search/experiments/e030/ibm90_spec.json")
HX, HZ, LX, LZ = code_with_logicals()
kind = "X" if basis == "Z" else "Z"
H, Lg = (HZ, LZ) if basis == "Z" else (HX, LX)
nH, k = H.shape[0], Lg.shape[0]


def key_of_sup(S):
    v = np.zeros(N, np.uint8); v[list(S)] = 1
    return tuple(int(x) for x in (H.astype(int) @ v) % 2) + tuple(int(x) for x in (Lg.astype(int) @ v) % 2)


chk = d["x_checks"] if kind == "X" else d["z_checks"]
sups = [(q,) for q in range(N)]
for c in chk:
    order = [a for a, t in sorted(c["cnots"], key=lambda x: (x[1] - c["prep"]) % d["period"])]
    for kk in range(1, 6):
        sups.append(tuple(sorted(order[kk:])))
cols = {}
for S in sups:
    kk = key_of_sup(S)
    if any(kk):
        cols.setdefault(kk, S)
keys = list(cols)
n = len(keys)
kidx = {kk: j for j, kk in enumerate(keys)}


def qperm(ga, gb):
    p = np.zeros(N, int)
    for blk in (0, N2):
        for i in range(N2):
            a, b = divmod(i, M_)
            p[blk + i] = blk + ((a + ga) % L_) * M_ + (b + gb) % M_
    return p


perms = []
for ga in range(L_):
    for gb in range(M_):
        p = qperm(ga, gb)
        P = [kidx[key_of_sup([p[q] for q in cols[kk]])] for kk in keys]
        assert sorted(P) == list(range(n))
        perms.append(P)
orb = [-1] * n
reps = []
for j in range(n):
    if orb[j] < 0:
        for P in perms:
            orb[P[j]] = len(reps)
        reps.append(j)
ikey = [sum(b << i for i, b in enumerate(kk)) for kk in keys]
lists = {}
for w in range(1, 9):
    found = set()
    for o, r in enumerate(reps):
        A = [j for j in range(n) if orb[j] >= o and j != r]
        inp = f"{n} {w} {nH}\n" + " ".join(map(str, ikey)) + f"\n{r} {len(A)} " + " ".join(map(str, A)) + "\n"
        pr = subprocess.run(["results/E-028-audit/mitm"], input=inp, capture_output=True, text=True, check=True)
        for line in pr.stdout.splitlines():
            S = tuple(sorted(int(x) for x in line.split()[1:]))
            for P in perms:
                found.add(tuple(sorted(P[j] for j in S)))
    for S in found:
        tot = 0
        for j in S:
            tot ^= ikey[j]
        assert tot & ((1 << nH) - 1) == 0 and tot >> nH and len(set(S)) == w
    lists[w] = sorted(found)
    print(basis, "ext", n, "cols", len(reps), "orbits, w", w, len(found), flush=True)
dext = min([w for w in lists if lists[w]] or [99])
print("d_ext", dext, flush=True)
assert dext >= 7, "d_ext < 7: mixtures with two zero-image terms / repeated images not implemented"
cases = [(8, False)] + ([(7, True)] if dext == 7 else [])
res = {"basis": basis, "n_cols": n, "d_ext": dext, "ext_counts": {w: len(lists[w]) for w in lists}}
for R in Rs:
    circ = memory_circuit(d, basis, R, 1e-3, 1.0, image_obs=True)
    terms, nd, no = dem_terms(circ)
    by_col, zero, zl = {}, 0, []
    for dm, om, _ in terms:
        logic = om & ((1 << k) - 1)
        img = tuple((om >> (k + r)) & 1 for r in range(nH + k))
        assert logic == sum(img[nH + r] << r for r in range(k))
        if not any(img):
            zero += 1; zl.append((dm, logic))
            continue
        assert img in kidx, "Lemma 1 violated"
        by_col.setdefault(kidx[img], []).append((dm, logic))
    plain = set()
    nlift = 0
    for w, withz in cases:
      for S in lists[w]:
          vid, top, cl, groups = {}, 0, [], []
          for j in S:
              g = []
              for t in by_col[j]:
                  top += 1; g.append(top); vid[top] = t
              groups.append(g)
          if withz:
              U = 0
              for j in S:
                  for t in by_col[j]:
                      U |= t[0]
              zg = []
              for t in zl:
                  if t[0] & ~U == 0:
                      top += 1; zg.append(top); vid[top] = t
              if not zg:
                  continue
              groups.append(zg)
          for g in groups:
              cl.append(list(g))
              for a in range(len(g)):
                  for b in range(a + 1, len(g)):
                      cl.append([-g[a], -g[b]])
          var_det = {}
          for v, (dm, _) in vid.items():
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
          nv = len(vid)
          with Minisat22(bootstrap_with=cl) as s:
              while s.solve():
                  m = s.get_model()
                  chosen = [v for v in range(1, nv + 1) if m[v - 1] > 0]
                  nlift += 1
                  plain.add(frozenset(vid[v] for v in chosen))
                  s.add_clause([-v for v in chosen])
    assert all(len(F) == 8 for F in plain)
    res[f"R{R}"] = {"terms": len(terms), "zero_terms": zero, "aug_lifts": nlift, "plain_logicals": len(plain)}
    print(json.dumps(res[f"R{R}"]), flush=True)
json.dump(res, open(f"results/E-030-audit/a7_ibm_count_{basis}.json", "w"), indent=1)
