"""Auditor (E-026b) claim 2: independent direct sampling.
noise = mynoise.my_sd6_lam (own builder), DEM = own merge, sampler = stim DEM sampler (own seeds),
decoder = ldpc.BpOsdDecoder, IBM parameters (min-sum, max_iter 10000, ms_scaling 0, OSD-CS order 7).
Jobs are chunks of CHUNK shots (seed = 26150000 + job index); 4 worker processes; results appended to jsonl.
  PYTHONPATH=.:tests uv run python research/audits/2026-10-15-E-026b-scripts/sample.py"""
import json, os, sys, time
from multiprocessing import Pool
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["OMP_NUM_THREADS"] = "1"
import numpy as np
from mynoise import circuit, build_dem, ROOT

OUT = ROOT / "results/E-026b-audit"
P = 4e-3; R = 12; CHUNK = 250
# (lam, circ) -> chunks per basis   (cost-balanced for ~6 CPU h total)
PLAN = {(0.0, "p18"): 160, (0.0, "fig12"): 60, (0.1, "p18"): 16, (0.1, "fig12"): 60}
DEADLINE = time.time() + float(os.environ.get("WALL_S", "7200"))
_cache = {}


def setup(lam, circ, basis):
    k = (lam, circ, basis)
    if k not in _cache:
        from ldpc import BpOsdDecoder
        dem, H, L, q, _ = build_dem(circuit(circ, basis, R, P, lam))
        dec = BpOsdDecoder(H.tocsc(), error_channel=list(q), max_iter=10000, bp_method="minimum_sum",
                           ms_scaling_factor=0, osd_method="osd_cs", osd_order=7)
        _cache[k] = (dem, H, L, dec)
    return _cache[k]


def job(arg):
    j, lam, circ, basis = arg
    if time.time() > DEADLINE:
        return None
    t0 = time.process_time()
    dem, H, L, dec = setup(lam, circ, basis)
    det, obs = dem.compile_sampler(seed=26150000 + j).sample(CHUNK)[:2]
    fails = 0
    for s in range(CHUNK):
        corr = dec.decode(det[s].astype(np.uint8))
        fails += bool(((L @ corr) % 2 != obs[s]).any())
    return dict(job=j, lam=lam, circ=circ, basis=basis, shots=CHUNK, fails=fails, cpu=time.process_time() - t0)


def main():
    done = set()
    f = OUT / "sample.jsonl"
    if f.exists():
        done = {json.loads(l)["job"] for l in f.read_text().splitlines() if l.strip()}
    jobs = []
    j = 0
    mx = max(PLAN.values())
    for r in range(mx):  # interleave so a deadline stop leaves balanced partial data
        for (lam, circ), n in PLAN.items():
            for b in "ZX":
                j += 1
                if r < n and j not in done:
                    jobs.append((j, lam, circ, b))
    print("jobs", len(jobs), flush=True)
    with Pool(4) as pool, open(f, "a") as fh:
        for r in pool.imap_unordered(job, jobs):
            if r is None:
                continue
            fh.write(json.dumps(r) + "\n"); fh.flush()


if __name__ == "__main__":
    main()
