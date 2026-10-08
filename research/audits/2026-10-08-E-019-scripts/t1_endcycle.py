"""exact end-cycle code distance (both end-cycle codes, both error types) with mdfs; K-translation orbits."""
import sys, json, subprocess, itertools
import numpy as np
from inst import make, HOM
from mycirc import logicals, PARENT
R = '/Users/ephemeral/Desktop/qec-ai-search/results/E-019-audit'

def code_dist(M, H_check, H_same, tag, Wmax=13):
    """errors of type P on left qubits; rows = H_check (other type), obs = same-type-as-check logicals"""
    Lo = logicals(H_check, H_same)        # logicals of the check type: ker(H_same) mod rowspace(H_check)
    f = HOM[M.hom]
    # orbits of K-translations on G: two cosets K and K^c -> orbit id = f(g)
    path = f'{R}/ec/{tag}.txt'
    rows = len(H_check)
    with open(path, 'w') as fh:
        fh.write(f"{rows} {M.N} {len(Lo)} 2\n")
        for q in range(M.N):
            g = M.G[q]
            rr = np.nonzero(H_check[:, q])[0]
            oo = np.nonzero(Lo[:, q])[0]
            fh.write(f"{f(g)} {len(rr)} " + " ".join(map(str, rr)) + f" {len(oo)} " + " ".join(map(str, oo)) + "\n")
    # orbit validity: translation by k in K maps check rows to check rows (row set closed), cheap check
    for W in range(1, Wmax + 1):
        out = subprocess.run([f'{R}/mdfs', path, str(W)], capture_output=True, text=True).stdout
        if 'FOUND' in out:
            return W
    return None

if __name__ == '__main__':
    import os; os.makedirs(f'{R}/ec', exist_ok=True)
    codes = sys.argv[1].split(',')
    res = []
    for code in codes:
        for hom in ('x', 'y', 'xy'):
            try:
                make(code, hom, 'IV', 0, 0)
            except AssertionError:
                continue
            for kind in ('IV', 'VIII'):
                for sa, sb in itertools.product((0, 1), (0, 1)):
                    M = make(code, hom, kind, sa, sb)
                    ec = M.check_contraction()
                    ds = []
                    for i in (1, 2):
                        HX, HZ = ec[i]
                        # check translation invariance of the row sets (needed for the orbit split)
                        f = HOM[hom]
                        K = [g for g in M.G if f(g) == 0]
                        for H in (HX, HZ):
                            S = {tuple(np.nonzero(r)[0]) for r in H}
                            for s in K[:5]:
                                S2 = {tuple(sorted(M.gi(M.add(M.G[q], s)) for q in r)) for r in S}
                                assert S2 == S
                        dX = code_dist(M, HZ, HX, f'{code}_{hom}_{kind}{sa}{sb}_c{i}_Xerr')
                        dZ = code_dist(M, HX, HZ, f'{code}_{hom}_{kind}{sa}{sb}_c{i}_Zerr')
                        ds += [dX, dZ]
                    r = dict(code=code, hom=hom, kind=kind, sa=sa, sb=sb, d=ds)
                    print(json.dumps(r), flush=True); res.append(r)
    json.dump(res, open(f'{R}/t1_endcycle_{"_".join(codes)}.json', 'w'))
