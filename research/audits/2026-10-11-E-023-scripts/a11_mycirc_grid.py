"""Audit E-023: full-circuit (T = 8) fixed-weight grid on the independent [[54]] morphing circuit (mycirc, natural
Pauli-propagation detectors, same-basis), BP-OSD (IBM) + Relay5, priors at 1e-3.  Stores counts and π_w(p) of the DEM
at each p of P (same columns, priors recomputed).  args: var basis seed"""
import sys, json, time
import numpy as np
sys.path.insert(0, 'research/audits/2026-10-08-E-019-scripts'); sys.path.insert(0, '.')
sys.path.insert(0, 'research/audits/2026-10-11-E-023-scripts')
from inst import make
from evaluators.noise import add_noise
from a3_decode_basis import decoders, fw_sample
from a4_mycirc import merged_dem
P = [1e-4, 2e-4, 3e-4, 5e-4, 7e-4, 1e-3, 2e-3, 3e-3]
GRID = [(2, 10000), (3, 10000), (4, 6000), (5, 4000), (6, 3000), (8, 2000), (10, 1500), (13, 800), (16, 400)]
var, basis, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
SUF = ""
if len(sys.argv) > 4:
    GRID = [tuple(map(int, x.split(":"))) for x in sys.argv[4].split(",")]; SUF = "_" + sys.argv[5]
M = make("bb108", "y", "IV", *{"paper": (0, 0), "repo": (1, 1)}[var])
c = M.memory(basis, 8, full_detectors=False)
H, L, q, keys = merged_dem(add_noise(c, "sd6", 1e-3))
def wdist(qq, wmax=120):
    Pw = np.zeros(wmax + 1); Pw[0] = 1
    for x in qq: Pw[1:] = Pw[1:] * (1 - x) + Pw[:-1] * x; Pw[0] *= 1 - x
    return Pw
pis = {}
for p in P:
    H2, L2, q2, k2 = merged_dem(add_noise(c, "sd6", p))
    assert k2 == keys
    pis[str(p)] = wdist(q2).tolist()
out = dict(var=var, basis=basis, seed=seed, pis=pis, grid={})
D = decoders(H, q); rng = np.random.default_rng(seed)
for w, n in GRID:
    sets = fw_sample(q, w, n, rng); rec = {}
    for dn, d in D.items():
        k, t0 = 0, time.process_time()
        for S in sets:
            e = np.zeros(H.shape[1], np.uint8); e[S] = 1
            s = (H @ e % 2).astype(np.uint8); eh = d(s)
            k += int(((L @ eh) % 2 != (L @ e) % 2).any() or ((H @ eh) % 2 != s).any())
        rec[dn] = dict(k=k, n=n, cpu=time.process_time() - t0)
        print(var, basis, "w", w, dn, k, "/", n, round(rec[dn]["cpu"]), flush=True)
    out["grid"][str(w)] = rec
    json.dump(out, open(f"results/E-023-audit/a11_{var}_{basis}{SUF}.json", "w"))
