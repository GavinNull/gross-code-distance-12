"""Auditor E-035: independent LER sampling under the auditor's own NA model (na_mine: own code, logicals, encoder,
own NA noise), own DEM -> check matrix, stim DEM sampler with own seeds (35350000 + job), ldpc.BpOsdDecoder with IBM
parameters (min-sum, max_iter 10000, ms_scaling 0, OSD-CS order 7).  Adapted from the E-030 / E-033 auditor a2/s_sample.

PRE-SET PLAN (fixed before any of my samples were drawn; written into this file at creation):
  S1  bb90  proj        c11, ibm90   25000 shots per basis (50 chunks x 500)      <- headline ratio
  S2  bb90  cur_par_unp c11, ibm90     500 shots per basis (5 chunks x 100)       <- decisive negative
  S3  gross curx0.5     u11, ibm     18000 shots per basis (36 chunks x 500)      <- only significant gross point
  Jobs interleaved across tasks; stop rule = shots reached, or global CPU cap 18 h (outcome independent).
  No extension, whatever the outcome.
    PLAN=S1,S2,S3 NPROC=5 uv run python research/audits/2026-10-24-E-035-scripts/s_sample.py"""
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
import na_mine as nm

PLANS = {"S1": [("proj", "c11", 50, 500), ("proj", "ibm90", 50, 500)],
         "S2": [("cur_par_unp", "c11", 5, 100), ("cur_par_unp", "ibm90", 5, 100)],
         "S3": [("curx0.5", "u11", 36, 500), ("curx0.5", "ibm", 36, 500)]}
BASEJ = {"S1": 0, "S2": 100000, "S3": 200000}
OUT = Path("/Users/ephemeral/Desktop/qec-ai-search/results/E-035-audit/s_sample.jsonl")
CPU_CAP = 18 * 3600
_cache = {}


def setup(model, circ, basis):
    k = (model, circ, basis)
    if k not in _cache:
        from ldpc import BpOsdDecoder
        fam, _ = nm.spec(circ)
        c, _ = nm.build(circ, basis, nm.RNDS[fam], model)
        dem = c.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
        rows, cols, lr, lc, q = [], [], [], [], []
        j = 0
        for ins in dem.flattened():
            if ins.type != "error":
                continue
            for t in ins.targets_copy():
                if t.is_relative_detector_id():
                    rows.append(t.val); cols.append(j)
                elif t.is_logical_observable_id():
                    lr.append(t.val); lc.append(j)
            q.append(ins.args_copy()[0]); j += 1
        H = sp.csc_matrix((np.ones(len(rows), np.uint8), (rows, cols)), shape=(dem.num_detectors, j))
        Lm = sp.csr_matrix((np.ones(len(lr), np.uint8), (lr, lc)), shape=(dem.num_observables, j))
        # merge parallel columns? no: ldpc handles duplicate columns; keep the DEM as is (same as E-030/E-033 audits)
        dec = BpOsdDecoder(H, error_channel=q, max_iter=10000, bp_method="minimum_sum", ms_scaling_factor=0,
                           osd_method="osd_cs", osd_order=7)
        _cache[k] = (dem, Lm, dec)
    return _cache[k]


def job(arg):
    j, model, circ, basis, chunk = arg
    t0 = time.process_time()
    dem, Lm, dec = setup(model, circ, basis)
    det, obs, _ = dem.compile_sampler(seed=35350000 + j).sample(chunk)
    fails = 0
    for s in range(chunk):
        corr = dec.decode(det[s].astype(np.uint8))
        fails += bool(((Lm @ corr) % 2 != obs[s]).any())
    return dict(job=j, model=model, circ=circ, basis=basis, shots=chunk, fails=fails, cpu=time.process_time() - t0)


def main():
    done, used = set(), 0.0
    if OUT.exists():
        for l in OUT.read_text().splitlines():
            if l.strip():
                r = json.loads(l); done.add(r["job"]); used += r["cpu"]
    jobs = []
    for name in os.environ["PLAN"].split(","):
        ent = PLANS[name]
        mx = max(e[2] for e in ent)
        for r in range(mx):
            for e, (model, circ, n, chunk) in enumerate(ent):
                for bi, b in enumerate("ZX"):
                    j = BASEJ[name] + (r * len(ent) + e) * 2 + bi
                    if r < n and j not in done:
                        jobs.append((j, model, circ, b, chunk))
    print("jobs", len(jobs), "cpu used so far", round(used), flush=True)
    with Pool(int(os.environ.get("NPROC", "5"))) as pool, open(OUT, "a") as fh:
        for r in pool.imap(job, jobs):
            fh.write(json.dumps(r) + "\n"); fh.flush()
            used += r["cpu"]
            if used > CPU_CAP:
                print("CPU cap reached", flush=True)
                pool.terminate()
                break


if __name__ == "__main__":
    main()
