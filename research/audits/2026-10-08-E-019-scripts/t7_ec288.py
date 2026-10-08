"""end-cycle code distance for one [[288]] variant, end-cycle code C~1, X errors (rows HZ) and Z errors.
usage: t7_ec288.py hom kind sa sb d   -> runs W=d-1 (expect none) and W=d (expect found)"""
import sys, json, subprocess, time
import numpy as np
from inst import make, HOM
from mycirc import logicals
R = '/Users/ephemeral/Desktop/qec-ai-search/results/E-019-audit'
hom, kind, sa, sb, d = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
M = make('bb288', hom, kind, sa, sb)
HX, HZ = M.check_contraction()[1]
f = HOM[hom]
res = dict(variant=f'bb288_{hom}_{kind}{sa}{sb}', runs=[])
for err, Hc, Hs in (('X', HZ, HX), ('Z', HX, HZ)):
    Lo = logicals(Hc, Hs)
    path = f'{R}/ec/bb288_{hom}_{kind}{sa}{sb}_c1_{err}err.txt'
    with open(path, 'w') as fh:
        fh.write(f"{len(Hc)} {M.N} {len(Lo)} 2\n")
        for q in range(M.N):
            rr = np.nonzero(Hc[:, q])[0]; oo = np.nonzero(Lo[:, q])[0]
            fh.write(f"{f(M.G[q])} {len(rr)} " + " ".join(map(str, rr)) + f" {len(oo)} " + " ".join(map(str, oo)) + "\n")
    for W in (d - 1, d):
        t0 = time.time()
        out = subprocess.run([f'{R}/mdfs', path, str(W)], capture_output=True, text=True).stdout
        res['runs'].append(dict(err=err, W=W, found='FOUND' in out, sec=round(time.time() - t0, 1)))
        print(json.dumps(res['runs'][-1]), flush=True)
with open(f'{R}/t7_log.jsonl', 'a') as fh:
    fh.write(json.dumps(res) + '\n')
