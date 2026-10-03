"""Uniform tiling: same term order on every check of one type.  For each of the 90 term-order classes, decide
whether the tiled extended code (one error type only) has a logical of weight <= CAP.
usage: t5_uniform.py CODE TYPE CAP [WORKERS] [TIME]"""
import sys, json, time
sys.path.insert(0, "research/audits/2026-10-03-E-005-scripts")
from multiprocessing import Pool
from audext import *

def job(args):
    name, ct, cap, ci, tl = args
    c = Code(name)
    cls = term_order_classes(c, ct)[ci]
    rep = list(cls[0])
    H, L = c.det(ct)
    nrows = H.shape[0]
    res = [S for r in range(nrows) for S in nontrivial_suffixes(check_order_from_terms(c, ct, r, rep))]
    M, rH = ext_matrix(H, L, res)
    r = highs_fixed(M, rH, cap, tl, feasibility=True)
    x = r.pop("x", None)
    if x is not None:
        r["support"] = [int(j) for j in np.nonzero(x)[0]]
    r.update(cls=ci, rep_terms=rep, n_orders=len(cls), all_terms=["".join(map(str, p)) for p in cls])
    return r

if __name__ == "__main__":
    name, ct, cap = sys.argv[1], sys.argv[2], int(sys.argv[3])
    W = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    tl = float(sys.argv[5]) if len(sys.argv) > 5 else 600
    sub = [int(v) for v in sys.argv[6].split(",")] if len(sys.argv) > 6 else list(range(90))
    t0 = time.time(); out = []
    with Pool(W) as p:
        for r in p.imap_unordered(job, [(name, ct, cap, i, tl) for i in sub]):
            out.append(r); print(r["cls"], r["rep_terms"], r["status"], r["value"], r["seconds"], flush=True)
    out.sort(key=lambda r: r["cls"])
    hist = {}
    for r in out:
        hist[r["status"]] = hist.get(r["status"], 0) + 1
    json.dump({"code": name, "type": ct, "cap": cap, "hist": hist, "cpu_s": sum(r["seconds"] for r in out),
               "classes": out}, open(f"results/E-005-audit/uniform_{name}_{ct}_cap{cap}{'' if len(sub)==90 else '_sub'}.json", "w"), indent=1)
    print("HIST", hist, "cpu", sum(r["seconds"] for r in out))
