"""Item 5 driver: c11 SD6 DEM -> own C DFS (dfs.c; compile: cc -O3 -o results/paperP_audit/dfs_bin dfs.c).
  PYTHONPATH=.:tests uv run python search/experiments/paperP_audit/item5_dfs.py <basis> <R> <W>"""
import json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from item5_dem_direct import mechanisms
ROOT = Path(__file__).resolve().parents[3]
basis, R, W = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
t0 = time.time()
M, nd, coords = mechanisms(basis, R)
starts = [i for i, (ds, _) in enumerate(M) if any(int(coords[d][0]) == 0 for d in ds)]
lines = [f"{nd} {len(M)} 8"] + [f"{len(ds)} {' '.join(map(str, sorted(ds)))} {sum(1 << o for o in os_)}" for ds, os_ in M]
lines += [str(len(starts)), " ".join(map(str, starts))]
out = subprocess.run([str(ROOT / "results/paperP_audit/dfs_bin"), str(W)], input="\n".join(lines), capture_output=True, text=True).stdout.strip()
rec = {"basis": basis, "R": R, "W<=": W, "n_mech": len(M), "n_det": nd, "n_start": len(starts), "out": out}
if out.startswith("FOUND"):
    sol = [int(x) for x in out.split(":")[1].split(" nodes")[0].split()]
    dd, oo = set(), set()
    for i in sol:
        dd ^= set(M[i][0]); oo ^= set(M[i][1])
    rec["verified"] = (not dd) and bool(oo); rec["weight"] = len(sol)
rec["s"] = round(time.time() - t0, 1)
print(json.dumps(rec), flush=True)
