"""Audit E-023: time-bulk fixed-weight MC, decoded in BOTH the experimenter's detector basis (orig) and the sparsified
basis (sparse), same samples.  Bulk mask = experimenter's common.bulk_mask (rounds 3..T-1).  Own sampler/seed.
args: prob sector seed  -> results/E-023-audit/a6_<prob>_<sector>.json"""
import sys, json, time
import numpy as np
sys.path.insert(0, '.'); sys.path.insert(0, 'research/audits/2026-10-11-E-023-scripts')
from search.experiments.e023.common import sectors, bulk_mask
from a3_decode_basis import decoders, fw_sample, get

GRID = [(1, 2000), (2, 20000), (3, 10000), (4, 5000), (5, 3000), (6, 3000), (8, 2000), (10, 1500), (13, 800), (16, 400)]
prob, label, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
bases = sys.argv[4].split(",") if len(sys.argv) > 4 else ["orig", "sparse"]
sec, Hs = get(prob, label)
si = [s.label for s in sectors(prob, "sd6", 1e-3)].index(label)
mask, TB = bulk_mask(prob, sectors(prob, "sd6", 1e-3)[si])
qb = np.where(mask, sec.q, 0.0)
L = sec.L.toarray().astype(np.uint8)
D = {b: decoders(Hs[b], sec.q) for b in bases}
rng = np.random.default_rng(seed)
out = dict(prob=prob, sector=label, seed=seed, TB=TB, nbulk=int(mask.sum()), grid={})
for w, n in GRID:
    sets = fw_sample(qb, w, n, rng)
    rec = {}
    for b in bases:
        H = Hs[b]
        for dn, d in D[b].items():
            k, t0, fl = 0, time.process_time(), []
            for i, S in enumerate(sets):
                e = np.zeros(sec.ncol, np.uint8); e[S] = 1
                s = (H @ e % 2).astype(np.uint8)
                eh = d(s)
                f = bool(((L @ eh) % 2 != (L @ e) % 2).any()) or bool(((H @ eh) % 2 != s).any())
                if f: fl.append(i)
            rec[f"{b}_{dn}"] = dict(k=len(fl), n=n, cpu=time.process_time() - t0)
            print(prob, label, "w", w, b, dn, len(fl), "/", n, round(rec[f"{b}_{dn}"]["cpu"]), flush=True)
    out["grid"][str(w)] = rec
    json.dump(out, open(f"results/E-023-audit/a6_{prob}_{label}{'' if len(bases)==2 else '_'+bases[0]}.json", "w"), indent=1)
