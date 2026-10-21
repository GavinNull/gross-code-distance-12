"""A4: direct search on the full DEM (no extended code, no lists, no Lemma 1/2 needed for the conclusion).
Own circuit with image observables (evaluator L).  Column = DEM term: syndrome = detector set, logical = circuit
observables.  Translation symmetry is established term by term: detector permutation from the check permutation,
the image term must exist and carry the translated image (key of P e); zero image <-> zero image.  Then
mitmsearch (decide, look = 2) with symmetry root cases.
Usage: a4_direct.py SPEC BASIS R W [--norun]"""
import sys, json, time, subprocess, collections
sys.path.insert(0, "research/audits/2026-10-22-E-032-scripts")
import numpy as np
from alib32 import *
from extcode import ext_code

spec_path, basis, R, W = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
spec = load_spec(spec_path)
from evaluators.tasks import build_code, get_task
ec, _ = build_code(get_task("gross-dcirc"), None)
EL = ((np.asarray(ec.LZ) if basis == "Z" else np.asarray(ec.LX)) % 2).astype(np.uint8)
E = ext_code(spec, basis, Lover=EL)
kidx = {k: j for j, k in enumerate(E["cols"])}
HX, HZ, _, _ = code()
H = HZ if basis == "Z" else HX
nH, k = H.shape[0], EL.shape[0]
circ = memory_circuit(spec, basis, R, image_obs=True, Lover=EL)
t, nd, no = dem_terms(circ)
terms = []
for d, o in t:
    ob = o & ((1 << k) - 1)
    key = bytes(((o >> (k + r)) & 1) for r in range(nH + k))
    assert d or ob == 0, "detector-free term flips an observable"
    if d == 0:
        continue
    terms.append((d, ob, key))
dets = [d for d, _, _ in terms]
assert len(set(dets)) == len(dets), "two DEM terms share a detector set"
didx = {d: i for i, d in enumerate(dets)}
zero = bytes(nH + k)
# translation action
perms = []
for a in range(L_):
    for b in range(M_):
        P, p = translation(a, b)
        # check permutation: row i -> row pi(i) with H[pi(i)] = P(H[i])
        rows = {H[i].tobytes(): i for i in range(nH)}
        pi = []
        for i in range(nH):
            v = np.zeros(N, np.uint8); v[P[np.nonzero(H[i])[0]]] = 1
            pi.append(rows[v.tobytes()])
        def pd(d):
            out = 0
            while d:
                bb = d & -d; x = bb.bit_length() - 1; d ^= bb
                j, c = divmod(x, N2)
                out |= 1 << (j * N2 + pi[c])
            return out
        pm = []
        for d, ob, key in terms:
            d2 = pd(d)
            assert d2 in didx, "translated detector set is not a term"
            t2 = didx[d2]
            key2 = terms[t2][2]
            if key == zero:
                assert key2 == zero
            else:
                e = E["res"][kidx[key]]
                f = np.zeros(N, np.uint8); f[P[np.nonzero(e)[0]]] = 1
                want = (E["H"].astype(int) @ f % 2).astype(np.uint8).tobytes() + (E["L"].astype(int) @ f % 2).astype(np.uint8).tobytes()
                assert key2 == want, "image not equivariant"
            pm.append(t2)
        assert sorted(pm) == list(range(len(terms)))
        perms.append(pm)
orb = [-1] * len(terms); reps = []
for j in range(len(terms)):
    if orb[j] < 0:
        mem = sorted({pm[j] for pm in perms})
        for m in mem:
            orb[m] = len(reps)
        reps.append(max(mem))
tag = f"{spec_path.split('/')[-1].split('.')[0]}_{basis}_R{R}"
inst = f"results/E-032-audit/dem_{tag}.txt"
with open(inst, "w") as f:
    f.write(f"{len(terms)} {nd}\n")
    for d, ob, _ in terms:
        hs = [i for i in range(nd) if d >> i & 1]; ls = [i for i in range(k) if ob >> i & 1]
        f.write(f"{len(hs)} {' '.join(map(str, hs))} {len(ls)} {' '.join(map(str, ls))}\n")
    f.write(f"{len(reps)}\n{' '.join(map(str, orb))}\n{' '.join(map(str, reps))}\n")
info = {"spec": spec_path, "basis": basis, "R": R, "W": W, "terms": len(terms), "detectors": nd,
        "translations_verified": len(perms), "orbits": len(reps)}
print(json.dumps(info), flush=True)
if "--norun" in sys.argv:
    sys.exit(0)
t0 = time.time()
binp = "results/E-032-audit/mitmsearch_nw4"
r = subprocess.run([binp, str(W), "decide", "2"], stdin=open(inst), capture_output=True, text=True, check=True)
sols = [list(map(int, l.split()[2:])) for l in r.stdout.splitlines() if l.startswith("SOL")]
info.update(log=r.stderr.strip().splitlines()[-1], cases=[l for l in r.stderr.splitlines() if l.startswith("CASE")],
            sec=round(time.time() - t0, 1), solution=sols[0] if sols else None)
if sols:
    S = sols[0]
    dd = 0; oo = 0
    for j in S:
        dd ^= terms[j][0]; oo ^= terms[j][1]
    info["solution_check"] = {"weight": len(S), "distinct": len(set(S)) == len(S), "dets_zero": dd == 0, "obs": oo}
print(json.dumps(info), flush=True)
with open(f"results/E-032-audit/a4_direct.jsonl", "a") as f:
    f.write(json.dumps(info) + "\n")
