"""build CSS single-interior-half-cycle instances (T=5, window 3-3) for chosen [[288]] circuits; no DFS."""
import sys, json, time
from inst import make, noisy, dem_columns, orbits, write_instance
R = '/Users/ephemeral/Desktop/qec-ai-search/results/E-019-audit'
code, hom, kind, sa, sb, basis = sys.argv[1:7]
sa, sb = int(sa), int(sb)
t0 = time.time()
M = make(code, hom, kind, sa, sb)
c, nc = noisy(M, basis, 5, False, 'sd6', (3, 3))
ndet, nobs, cols = dem_columns(nc)
orb, norb = orbits(M, M.memory(basis, 5, full_detectors=False), cols, None)
tag = f'{code}_{hom}_{kind}{sa}{sb}_{basis}_T5_f0_sd6_3-3'
rows = write_instance(f'{R}/inst/{tag}.txt', ndet, nobs, cols, orb, norb)
import collections
cw = collections.Counter(len(D) for D, _ in cols)
print(json.dumps(dict(tag=tag, rows=rows, cols=len(cols), norb=norb, colw=sorted(cw.items()), sec=round(time.time() - t0, 1), info=M.det_info)))
