"""Single-check bound (Prop. 4 argument): exact d_ext of (code + residuals of ONE check) for all 90 classes.
usage: t3_single.py CODE TYPE [WORKERS] [CLASS_SUBSET comma list]"""
import sys, json, time
sys.path.insert(0, "research/audits/2026-10-03-E-005-scripts")
from multiprocessing import Pool
from audext import *

def job(args):
    name, ct, ci = args
    c = Code(name)
    cl = single_check_classes(c, ct, 0)[ci]
    H, L = c.det(ct)
    M, rH = ext_matrix(H, L, cl["residuals"])
    M, keep = dedupe_columns(M)
    t = time.time()
    r = highs_min(M, rH, cap=c.nkd[2], time_limit=1800)
    x = r.get("x")
    wit = None
    if x is not None:
        cols = keep[np.nonzero(x)[0]]
        wit = {"data": [int(j) for j in cols if j < c.n], "residuals": [list(map(int, cl["residuals"][j - c.n])) for j in cols if j >= c.n]}
    return {"class": ci, "rep": cl["rep"], "value": r["value"], "status": r["status"], "lower": r["lower"],
            "seconds": round(time.time() - t, 1), "witness": wit}

if __name__ == "__main__":
    name, ct = sys.argv[1], sys.argv[2]
    W = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    sub = [int(v) for v in sys.argv[4].split(",")] if len(sys.argv) > 4 else list(range(90))
    t0 = time.time()
    with Pool(W) as p:
        res = []
        for r in p.imap_unordered(job, [(name, ct, i) for i in sub]):
            res.append(r); print(r["class"], r["rep"], r["value"], r["status"], r["seconds"], flush=True)
    res.sort(key=lambda r: r["class"])
    hist = {}
    for r in res:
        k = f'{r["value"]}{"" if r["status"]=="optimal" else "?"}'
        hist[k] = hist.get(k, 0) + 1
    out = {"code": name, "type": ct, "check_row": 0, "hist": hist, "cpu_s": sum(r["seconds"] for r in res),
           "wall_s": round(time.time() - t0, 1), "classes": res}
    tag = "" if len(sub) == 90 else "_subset"
    json.dump(out, open(f"results/E-005-audit/single_{name}_{ct}{tag}.json", "w"), indent=1)
    print("HIST", hist, "cpu", out["cpu_s"])
