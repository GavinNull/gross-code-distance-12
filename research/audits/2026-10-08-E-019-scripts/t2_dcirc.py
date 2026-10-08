"""d_circ search on my own circuit's stim DEM.
usage: t2_dcirc.py code hom kind sa sb basis T full(0/1) model(sd6|noidle) window(all|t_lo-t_hi) Wlist [orb(0/1)]
Runs mdfs for each W in Wlist (comma) in increasing order, stops at the first W with a solution; prints JSON."""
import sys, json, subprocess, time, os
from inst import make, noisy, dem_columns, orbits, write_instance
R = '/Users/ephemeral/Desktop/qec-ai-search/results/E-019-audit'
code, hom, kind, sa, sb, basis, T, full, model, window, Wl = sys.argv[1:12]
use_orb = len(sys.argv) > 12 and sys.argv[12] == '1'
sa, sb, T, full = int(sa), int(sb), int(T), bool(int(full))
win = None if window == 'all' else tuple(map(int, window.split('-')))
M = make(code, hom, kind, sa, sb)
c, nc = noisy(M, basis, T, full, model, win)
ndet, nobs, cols = dem_columns(nc)
orb, norb = (None, 0)
if use_orb:
    orb, norb = orbits(M, M.memory(basis, T, full_detectors=full), cols, None)
    if orb is None:
        print('orbit split unavailable:', norb, file=sys.stderr); norb = 0
tag = f'{code}_{hom}_{kind}{sa}{sb}_{basis}_T{T}_f{int(full)}_{model}_{window}'
os.makedirs(f'{R}/inst', exist_ok=True)
path = f'{R}/inst/{tag}.txt'
nrows = write_instance(path, ndet, nobs, cols, orb, norb)
res = dict(tag=tag, ndet=ndet, rows=nrows, cols=len(cols), nobs=nobs, norb=norb, runs=[])
for W in map(int, Wl.split(',')):
    t0 = time.time()
    out = subprocess.run([f'{R}/mdfs', path, str(W)], capture_output=True, text=True).stdout
    fl = [l for l in out.splitlines() if l.startswith('FOUND')]
    summ = [l for l in out.splitlines() if l.startswith('SUMMARY')]
    nodes = sum(int(l.split()[5]) for l in out.splitlines() if l.startswith('CASE'))
    res['runs'].append(dict(W=W, found=len(fl) > 0, first=fl[0] if fl else None, summary=summ[-1] if summ else None, wall=round(time.time() - t0, 1), nodes=nodes))
    if fl:
        break
print(json.dumps(res))
with open(f'{R}/t2_log.jsonl', 'a') as fh:
    fh.write(json.dumps(res) + '\n')
