"""Audit E-023: structure of the experimenter's morphing sector DEMs (detector weights, column degrees by block)."""
import sys, json
import numpy as np
sys.path.insert(0, '.')
from search.experiments.e023.common import sectors, _plain, det_rounds
out = {}
for prob in ("m54_paper", "m54_repo"):
    for sec in sectors(prob, "sd6", 1e-3):
        plain, ann = _plain(prob, sec.label)
        dw = [len(i.targets_copy()) for i in ann if i.name == "DETECTOR"]
        dr = det_rounds(prob, sec.label)
        H = sec.H.tocsc()
        deg = np.diff(H.indptr)
        mx = np.array([dr[H.indices[H.indptr[j]:H.indptr[j+1]]].max() for j in range(sec.ncol)])
        blocks = {}
        for r in sorted(set(dr.tolist())):
            m = dr == r
            blocks[int(r)] = dict(ndet=int(m.sum()), det_rec_weight_mean=float(np.mean(np.array(dw)[m])),
                                  det_rec_weight_max=int(np.max(np.array(dw)[m])),
                                  col_deg_mean_latest_here=float(deg[mx == r].mean()) if (mx == r).any() else None,
                                  col_deg_max_latest_here=int(deg[mx == r].max()) if (mx == r).any() else None)
        out[f"{prob}_{sec.label}"] = dict(ndet=sec.ndet, ncol=sec.ncol, blocks=blocks)
        print(prob, sec.label, sec.ndet, sec.ncol)
        for r, b in blocks.items():
            print("  ", r, b)
json.dump(out, open('results/E-023-audit/a1_struct.json', 'w'), indent=1)
