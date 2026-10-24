"""Direct search on the full SD6 detector error model (SM S5, "Period-11 circuits"): no extended code, no lists, no
Lemma 1 or 2.  Second implementation of the search (code/p11/mitm.c, meet-in-the-middle terminal; the first is
code/dcirc/ccsearch.c).

Instance: the columns are the mechanisms of the SD6 DEM of the memory circuit (both detector-carrying and readout-flip
mechanisms; mechanisms without detectors must not flip an observable, asserted), syndrome = detector set, logical part
= observables of the memory basis.  A set of distinct mechanisms with zero detector sum and nonzero observable sum is
an undetected logical.  The translation symmetry used for the root cases is established term by term: the check
permutation of each translation maps every mechanism's detector set onto the detector set of a mechanism whose image
(the (H, L) column of its residual data error, from an augmented DEM) is the translated image (zero image <-> zero
image); the orbits of the verified group give the root cases (representative = largest index of the orbit).

    python code/p11/direct.py selftest                         # 60 random instances against brute force
    python code/p11/direct.py run u11 Z 1 11 --workers 4       # expect NONE (u11, R = 1, weight <= 11), ~20 CPU min
    python code/p11/direct.py run u11 X 1 11 --workers 4       # expect NONE
    python code/p11/direct.py run u11_control_p10 Z 1 11       # control: a weight-11 solution is FOUND and verified
Options: --expect none|found (default: found for controls, none otherwise), --out DIR (default p11_direct_run).
"""
import argparse
import itertools
import json
import random
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import stim

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_cli import Verdict                       # noqa: E402
from p11 import common as C                          # noqa: E402
from bb90.ext import noisy_circuit                   # noqa: E402

HERE = Path(__file__).resolve().parent


def build_bin(out: Path, nw: int) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    b = out / f"mitm_nw{nw}"
    if not b.exists():
        subprocess.run(["cc", "-O3", f"-DNW={nw}", "-o", str(b), str(HERE / "mitm.c")], check=True)
    return b


def instance(name, basis, R):
    fam = C.family_of(name)
    code = C.load_code(fam)
    spec = C.circuit(name)
    H, L = C.hl(code, basis)
    nH, k = H.shape[0], L.shape[0]
    c = noisy_circuit(spec, code, R, basis)
    n = code.n
    last = [op for op in c if op.name in ("M", "MX")][-1]
    assert [t.value for t in last.targets_copy()] == list(range(n))
    k0 = c.num_observables
    assert k0 == k
    aug = c.copy()
    for r, row in enumerate(list(H) + list(L)):
        aug.append("OBSERVABLE_INCLUDE", [stim.target_rec(int(q) - n) for q in np.nonzero(row)[0]], k0 + r)
    dem = aug.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    nd = dem.num_detectors
    terms = []
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        d = o = 0
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                d ^= 1 << t.val
            elif t.is_logical_observable_id():
                o ^= 1 << t.val
        ob = o & ((1 << k) - 1)
        key = bytes(((o >> (k + r)) & 1) for r in range(nH + k))
        assert d or ob == 0, "a mechanism without detectors flips an observable"
        if d:
            terms.append((d, ob, key))
    dets = [d for d, _, _ in terms]
    assert len(set(dets)) == len(dets), "two DEM mechanisms share a detector set"
    didx = {d: i for i, d in enumerate(dets)}
    keys, sups, _ = C.ext_columns(code, basis, spec)
    rep_of = {kk: s for kk, s in zip(keys, sups)}
    zero = bytes(nH + k)
    nchk = nH
    coords = dem.get_detector_coordinates()
    detpos = {(int(coords[i][1]), int(coords[i][0])): i for i in range(nd)}
    assert len(detpos) == nd
    perms = []
    for a in range(C.FAMILY[fam]["l"]):
        for b in range(C.FAMILY[fam]["m"]):
            pq = C.translation(fam, a, b)
            pi = pq[:nchk]
            pm = []
            for d, ob, key in terms:
                d2 = 0
                x = d
                while x:
                    low = x & -x; i = low.bit_length() - 1; x ^= low
                    j, cc = int(coords[i][1]), int(coords[i][0])
                    d2 |= 1 << detpos[(j, pi[cc])]
                if d2 not in didx:
                    break
                t2 = didx[d2]
                key2 = terms[t2][2]
                if key == zero:
                    if key2 != zero:
                        break
                else:
                    v = np.zeros(n, np.uint8); v[[pq[q] for q in rep_of[key]]] = 1
                    want = ((H @ v) % 2).astype(np.uint8).tobytes() + ((L @ v) % 2).astype(np.uint8).tobytes()
                    if key2 != want:
                        break
                pm.append(t2)
            else:
                assert sorted(pm) == list(range(len(terms)))
                perms.append(pm)
    orb = [-1] * len(terms); reps = []
    for j in range(len(terms)):
        if orb[j] < 0:
            mem = sorted({pm[j] for pm in perms})
            for m in mem:
                orb[m] = len(reps)
            reps.append(max(mem))
    txt = [f"{len(terms)} {nd}"]
    for d, ob, _ in terms:
        hs = [i for i in range(nd) if d >> i & 1]; ls = [i for i in range(k) if ob >> i & 1]
        txt.append(f"{len(hs)} {' '.join(map(str, hs))} {len(ls)} {' '.join(map(str, ls))}")
    txt.append(f"{len(reps)}\n{' '.join(map(str, orb))}\n{' '.join(map(str, reps))}")
    return "\n".join(txt) + "\n", terms, nd, len(perms), C.FAMILY[fam]["n_group"]


def selftest(binp):
    random.seed(7)
    bad = 0
    for trial in range(60):
        n, nb, nl = random.randint(10, 22), random.randint(5, 10), random.randint(1, 3)
        cols = set()
        while len(cols) < n:
            h = tuple(sorted(random.sample(range(nb), random.randint(1, 3)))) if random.random() > 0.1 else ()
            lo = tuple(sorted(random.sample(range(nl), random.randint(0, nl))))
            if h or lo:
                cols.add((h, lo))
        cols = sorted(cols)
        W = random.randint(3, 6); look = random.randint(1, 3)
        txt = f"{n} {nb}\n" + "".join(f"{len(h)} {' '.join(map(str, h))} {len(lo)} {' '.join(map(str, lo))}\n"
                                      for h, lo in cols)
        txt += f"{n}\n{' '.join(map(str, range(n)))}\n{' '.join(map(str, range(n)))}\n"
        r = subprocess.run([str(binp), str(W), "enum", str(look)], input=txt, capture_output=True, text=True)
        got = [frozenset(map(int, l_.split()[2:])) for l_ in r.stdout.splitlines() if l_.startswith("SOL")]

        def syn(S):
            s, lg = set(), set()
            for j in S:
                s ^= set(cols[j][0]); lg ^= set(cols[j][1])
            return s, lg
        minimal = set()
        for w in range(1, W + 1):
            for S in itertools.combinations(range(n), w):
                s, lg = syn(S)
                if s or not lg:
                    continue
                if any(not syn(T)[0] for kk in range(1, w) for T in itertools.combinations(S, kk)):
                    continue
                minimal.add(frozenset(S))
        ok = len(got) == len(set(got)) and all(not syn(S)[0] and syn(S)[1] for S in got) and minimal <= set(got)
        bad += not ok
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["selftest", "run"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--expect", choices=["none", "found"], default=None)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out", default="p11_direct_run")
    a = ap.parse_args()
    out = Path(a.out)
    V = Verdict()
    if a.cmd == "selftest":
        bad = selftest(build_bin(out, 1))
        V(bad == 0, f"mitm selftest: 60 random instances, every minimal solution reported, every reported set valid, "
                    f"no duplicates ({bad} failures)")
        V.exit()
    name, basis, R, W = a.args[0], a.args[1], int(a.args[2]), int(a.args[3])
    expect = a.expect or ("found" if "control" in name or name in ("u16", "s16") else "none")
    t0 = time.time()
    txt, terms, nd, ng, nfull = instance(name, basis, R)
    nw = (nd + 63) // 64
    binp = build_bin(out, nw)
    inst = out / f"dem_{name}_{basis}_R{R}.txt"
    inst.write_text(txt)
    norb = int(txt.splitlines()[len(terms) + 1])
    # one process per root case, at most `workers` at a time
    sols, logs, running, pending = [], [], [], list(range(norb))
    while pending or running:
        while pending and len(running) < a.workers:
            o = pending.pop(0)
            running.append(subprocess.Popen([str(binp), str(W), "decide", "2", str(o), str(o)], stdin=open(inst),
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        p = running.pop(0)
        so, se = p.communicate()
        sols += [list(map(int, l_.split()[2:])) for l_ in so.splitlines() if l_.startswith("SOL")]
        logs += [l_ for l_ in se.splitlines() if l_.startswith("CASE")]
        if sols and expect == "found":
            for q in running:
                q.kill(); q.wait()     # explicit children of this script
            running, pending = [], []
    nodes = sum(int(l_.split("nodes=")[1].split()[0]) for l_ in logs)
    ok_sol = True
    if sols:
        S = sols[0]
        dd = oo = 0
        for j in S:
            dd ^= terms[j][0]; oo ^= terms[j][1]
        ok_sol = len(set(S)) == len(S) <= W and dd == 0 and oo != 0
    found = bool(sols)
    rec = {"circuit": name, "basis": basis, "R": R, "W": W, "terms": len(terms), "detectors": nd,
           "translations_verified": ng, "root_cases": norb, "cases_run": len(logs), "nodes": nodes,
           "result": "FOUND" if found else "NONE", "solution": sols[0] if sols else None,
           "sec": round(time.time() - t0, 1)}
    print(json.dumps(rec), flush=True)
    V(ng == nfull and ok_sol and (found == (expect == "found")) and (found or len(logs) == norb),
      f"direct DEM search {name} {basis} basis R={R}: {len(terms)} mechanisms, {nd} detectors, {ng}/{nfull} "
      f"translations verified term by term, {norb} root cases ({len(logs)} run), {nodes} nodes: weight <= {W} "
      f"{rec['result']}" + (f" (solution of weight {len(sols[0])} re-verified: distinct, zero detector sum, nonzero "
                            f"observables)" if sols else "") + f" (expected {expect.upper()}) ({rec['sec']} s)")
    V.exit()


if __name__ == "__main__":
    main()
