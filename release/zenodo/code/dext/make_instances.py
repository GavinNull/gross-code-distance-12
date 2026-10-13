"""Write the extended-code instances for the two exhaustive searches (SM S4), for both memory bases.

The extended code is recomputed from the Fig. 12 CNOT orders and checked against data/extended_code/; the 24
colour-preserving translations that preserve the orders are recomputed and must give 15 column orbits.
Outputs (in OUTDIR, default dext_run/):
  w10_<b>.txt                 instance for dfs_w10 (format in dfs_w10.c): one case per orbit
  w10_jobs.txt                "<basis> <case> [split_mod split_idx]" (cases 0..2 split 4 ways)
  w11_<b>.txt, excl_<b>_<k>.txt, w11_jobs.txt
                              instance, exclusion files and jobs for enum_w11 (W = 11): orbit class k starts from its
                              smallest column and excludes all columns of classes < k; every class split 8 ways
    python code/dext/make_instances.py [OUTDIR]
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_cli import circuit, load_code       # noqa: E402
from gross12 import ext as E                    # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "dext_run")
out.mkdir(parents=True, exist_ok=True)
code = load_code()
f12 = circuit("fig12")
G = E.order_group(f12)
assert len(G) == 24, len(G)
w10_jobs, w11_jobs = [], []
for basis in "ZX":
    keys, sups, supkey = E.ext_columns(code, basis, f12)
    assert keys == E.ext_keys_from_file(code, basis), "extended code differs from the data file"
    perms = E.column_perms(code, basis, f12, keys, sups, supkey, G)
    classes = E.orbits(perms, len(keys))
    assert len(classes) == 15 and all(len(c) == 24 for c in classes)
    orb = {j: o for o, cl in enumerate(classes) for j in cl}
    H, L = E.hl(code, basis)
    Hm = np.array([np.frombuffer(k[:H.shape[0]], np.uint8) for k in keys])
    Lm = np.array([np.frombuffer(k[H.shape[0]:], np.uint8) for k in keys])
    with open(out / f"w10_{basis}.txt", "w") as f:
        f.write(f"{H.shape[0]} {len(keys)} {len(classes)}\n")
        for j in range(len(keys)):
            hm = sum(1 << int(i) for i in np.nonzero(Hm[j])[0])
            lm = sum(1 << int(i) for i in np.nonzero(Lm[j])[0])
            f.write(f"{hm & ((1 << 64) - 1)} {hm >> 64} {lm} {orb[j]}\n")
        f.write(" ".join(str(c[0]) for c in classes) + "\n")
    for c in range(len(classes)):
        if c < 3:
            w10_jobs += [f"{basis} {c} 4 {s}" for s in range(4)]
        else:
            w10_jobs.append(f"{basis} {c}")
    with open(out / f"w11_{basis}.txt", "w") as f:
        f.write(f"{len(keys)} {H.shape[0]} {L.shape[0]}\n")
        for hb, lb in zip(Hm, Lm):
            h = int("".join(map(str, hb[::-1])), 2)
            lv = int("".join(map(str, lb[::-1])), 2)
            f.write(f"{h & ((1 << 64) - 1)} {h >> 64} {lv}\n")
    for k, cl in enumerate(classes):
        low = [c for cc in classes[:k] for c in cc]
        (out / f"excl_{basis}_{k}.txt").write_text(f"{len(low)}\n" + " ".join(map(str, low)) + "\n")
        w11_jobs += [f"{basis} {cl[0]} 8 {s} excl_{basis}_{k}.txt" for s in range(8)]
    print(f"{basis} basis: {len(keys)} columns, check-weight histogram "
          f"{dict(zip(*np.unique(Hm.sum(1), return_counts=True)))}, {len(G)} translations, {len(classes)} orbits")
(out / "w10_jobs.txt").write_text("\n".join(w10_jobs) + "\n")
(out / "w11_jobs.txt").write_text("\n".join(w11_jobs) + "\n")
print(len(w10_jobs), "W=10 jobs,", len(w11_jobs), "W=11 jobs in", out)
