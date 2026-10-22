"""Auditor E-033 (adapted from E-030 auditor a2): independent LER sampling, gross, R = 12 (own circuit encoder, own SD6-lambda noise, own logicals, own DEM -> check matrix,
stim DEM sampler with own seeds, ldpc.BpOsdDecoder with IBM parameters: min-sum, max_iter 10000, ms_scaling 0,
OSD-CS order 7).  Jobs = CHUNK shots; results appended to results/E-033-audit/s_sample.jsonl.
    WALL_S=... PLAN=... uv run python research/audits/2026-10-22-E-030-scripts/a2_sample.py
PLAN: "lam:p:circ:nchunks,..."  (each entry sampled in both bases)"""
import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["OMP_NUM_THREADS"] = "1"
import numpy as np
import scipy.sparse as sp
from mylib import memory_circuit, dem_terms, load_spec

SPECS = {"u11": "search/experiments/e032/u11_spec.json", "ibm": "search/experiments/e033/ibm_gross_spec.json",
         "fig12": "search/experiments/e033/fig12_gross_spec.json"}
OUT = Path(os.environ.get("OUT", "results/E-033-audit/s_sample.jsonl"))
R = 12
CHUNK = int(os.environ.get("CHUNK", "1000"))
DEADLINE = time.time() + float(os.environ.get("WALL_S", "3600"))
_cache = {}


def setup(lam, p, circ, basis):
    k = (lam, p, circ, basis)
    if k not in _cache:
        from ldpc import BpOsdDecoder
        import stim
        c = memory_circuit(load_spec(SPECS[circ]), basis, R, p, lam)
        terms, nd, no = dem_terms(c)
        rows, cols, lr, lc = [], [], [], []
        for j, (dm, om, pr) in enumerate(terms):
            for i in range(nd):
                if dm >> i & 1:
                    rows.append(i); cols.append(j)
            for i in range(no):
                if om >> i & 1:
                    lr.append(i); lc.append(j)
        H = sp.csc_matrix((np.ones(len(rows), np.uint8), (rows, cols)), shape=(nd, len(terms)))
        Lm = sp.csr_matrix((np.ones(len(lr), np.uint8), (lr, lc)), shape=(no, len(terms)))
        q = [t[2] for t in terms]
        dec = BpOsdDecoder(H, error_channel=q, max_iter=10000, bp_method="minimum_sum", ms_scaling_factor=0,
                           osd_method="osd_cs", osd_order=7)
        dem = c.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
        _cache[k] = (dem, Lm, dec)
    return _cache[k]


def job(arg):
    j, lam, p, circ, basis = arg
    if time.time() > DEADLINE:
        return None
    t0 = time.process_time()
    dem, Lm, dec = setup(lam, p, circ, basis)
    det, obs, _ = dem.compile_sampler(seed=33300000 + j).sample(CHUNK)
    fails = 0
    for s in range(CHUNK):
        corr = dec.decode(det[s].astype(np.uint8))
        fails += bool(((Lm @ corr) % 2 != obs[s]).any())
    return dict(job=j, lam=lam, p=p, circ=circ, basis=basis, shots=CHUNK, fails=fails, cpu=time.process_time() - t0)


def main():
    plan = []
    for ent in os.environ["PLAN"].split(","):
        lam, p, circ, n = ent.split(":")
        plan.append((float(lam), float(p), circ, int(n)))
    done = set()
    if OUT.exists():
        done = {json.loads(l)["job"] for l in OUT.read_text().splitlines() if l.strip()}
    jobs = []
    base = int(os.environ.get("JOBBASE", "0"))
    mx = max(n for *_, n in plan)
    for r in range(mx):          # interleaved so that a deadline stop leaves balanced partial data
        for e, (lam, p, circ, n) in enumerate(plan):
            for bi, b in enumerate("ZX"):
                j = base + (r * len(plan) + e) * 2 + bi
                if r < n and j not in done:
                    jobs.append((j, lam, p, circ, b))
    print("jobs", len(jobs), flush=True)
    with Pool(int(os.environ.get("NPROC", "3"))) as pool, open(OUT, "a") as fh:
        for r in pool.imap_unordered(job, jobs):
            if r is None:
                continue
            fh.write(json.dumps(r) + "\n"); fh.flush()


if __name__ == "__main__":
    main()
