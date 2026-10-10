"""E-022 audit: validity + exact end-cycle distances (both end codes, both error types) for E-022 keys, using the
E-019 auditor's circuit (mycirc: contraction derived by Pauli propagation) and mdfs with the K / K^c split
(row-set translation invariance checked for ALL of K here).
usage: a4_endcode.py key [key ...]"""
import sys, json, subprocess
import numpy as np
sys.path.insert(0, '/Users/ephemeral/Desktop/qec-ai-search/research/audits/2026-10-11-E-022-scripts')
from a1_build import match, OUT
import mycirc
from mycirc import logicals, gf2_rank, HOM
from search.experiments.e019 import common
from search.experiments.e022.newcodes import load_random, register

def dist(M, Hc, Hs, tag, Wmax=14):
    Lo = logicals(Hc, Hs)
    f = HOM[M.hom]
    path = f'{OUT}/ec_{tag}.txt'
    with open(path, 'w') as fh:
        fh.write(f"{len(Hc)} {M.N} {len(Lo)} 2\n")
        for q in range(M.N):
            rr = np.nonzero(Hc[:, q])[0]; oo = np.nonzero(Lo[:, q])[0]
            fh.write(f"{f(M.G[q])} {len(rr)} " + " ".join(map(str, rr)) + f" {len(oo)} " + " ".join(map(str, oo)) + "\n")
    for W in range(1, Wmax + 1):
        out = subprocess.run([f'{OUT}/mdfs', path, str(W)], capture_output=True, text=True).stdout
        fl = [l for l in out.splitlines() if l.startswith('FOUND')]
        if fl:
            return W, [int(x) for x in fl[0].split('cols:')[1].split()], len(Lo)
    return None, None, len(Lo)

if __name__ == '__main__':
    register(load_random()); mycirc.PARENT.update(common.CODES)
    for key in sys.argv[1:]:
        M, lab = match(key)
        if M is None:
            print(json.dumps(dict(key=key, error='no match'))); continue
        ec = M.check_contraction()          # asserts the contraction structure
        X, Z = M.mid_stabs()
        HXm = np.array([[1 if s[q] else 0 for q in range(2 * M.N)] for s in X], np.uint8)
        HZm = np.array([[1 if s[q] else 0 for q in range(2 * M.N)] for s in Z], np.uint8)
        kmid = 2 * M.N - gf2_rank(HXm) - gf2_rank(HZm)
        f = HOM[M.hom]; K = [g for g in M.G if f(g) == 0]
        res = dict(key=key, label=lab, n_mid=2 * M.N, k_mid=int(kmid))
        for i in (1, 2):
            HX, HZ = ec[i]
            res[f'k_end{i}'] = int(M.N - gf2_rank(HX) - gf2_rank(HZ))
            res[f'w_end{i}'] = sorted({int(r.sum()) for r in np.vstack([HX, HZ])})
            for H in (HX, HZ):
                S = {tuple(np.nonzero(r)[0]) for r in H}
                for s in K:
                    assert {tuple(sorted(M.gi(M.add(M.G[q], s)) for q in r)) for r in S} == S
            dX, wX, _ = dist(M, HZ, HX, f'{key}_c{i}_Xerr')
            dZ, wZ, _ = dist(M, HX, HZ, f'{key}_c{i}_Zerr')
            res[f'd_end{i}'] = [dX, dZ]
        print(json.dumps(res), flush=True)
        with open(f'{OUT}/a4_log.jsonl', 'a') as fh:
            fh.write(json.dumps(res) + '\n')
