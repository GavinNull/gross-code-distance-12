"""Audit E-023: re-decode the experimenter's decoded structural strata (m54 _W6/_W7/_W8) in the sparsified basis.
Reports HT-weighted failing subsets per size and the minimum failing size where the ideal (MLE-vs-complement) decoder
is correct (decoder-specific failures).  args: prob"""
import sys, glob, json
import numpy as np
sys.path.insert(0, '.'); sys.path.insert(0, 'research/audits/2026-10-11-E-023-scripts')
from a3_decode_basis import decoders, get
prob = sys.argv[1]
out = {}
for label in "ZX":
    sec, Hs = get(prob, label)
    L = sec.L.toarray().astype(np.uint8); H = Hs["sparse"]
    D = decoders(H, sec.q)
    for f in sorted(glob.glob(f"results/E-023-ler-benefit/splits/{prob}_sd6_{label}_W*.npz")):
        z = np.load(f, allow_pickle=True)
        names = list(z["names"]); S = z["S"]; size = z["size"]; ht = z["ht"]; id3 = z["ideal3"]
        tag = f.split("_")[-1][:-4]
        for dn, d in D.items():
            fl = np.zeros(len(S), bool)
            for i, row in enumerate(S):
                s_ = [int(x) for x in row if x >= 0]
                e = np.zeros(sec.ncol, np.uint8); e[s_] = 1
                syn = (H @ e % 2).astype(np.uint8); eh = d(syn)
                fl[i] = bool(((L @ eh) % 2 != (L @ e) % 2).any()) or bool(((H @ eh) % 2 != syn).any())
            orig = z["dec"][:, names.index(dn)]
            for t in sorted(set(size.tolist())):
                m = size == t
                r = dict(n=int(m.sum()), sparse_fail=int(fl[m].sum()), orig_fail=int(orig[m].sum()),
                         sparse_fail_ideal_ok=int((fl[m] & (id3[m] == 0)).sum()),
                         orig_fail_ideal_ok=int((orig[m] & (id3[m] == 0)).sum()),
                         ideal_fail=float((id3[m] > 0).sum()),
                         HT_sparse=float((fl[m] * ht[m]).sum()), HT_orig=float((orig[m] * ht[m]).sum()))
                out[f"{label}_{tag}_t{t}_{dn}"] = r
                print(prob, label, tag, "t", t, dn, r, flush=True)
json.dump(out, open(f"results/E-023-audit/a10_{prob}.json", "w"), indent=1)
