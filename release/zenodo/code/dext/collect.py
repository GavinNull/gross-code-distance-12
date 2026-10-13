"""Collect the outputs of run_dext.sh and compare with the paper / the data files.

  W = 10 (dfs_w10): every job printed a SUMMARY line and no job found a logical  =>  d_ext >= 11 (both bases).
  W = 11 (enum_w11): the union of the translates (24-element group) of all solutions is exactly the list in
                     data/logicals/weight11_logicals_<b>_memory.json (4224 per basis, 176 orbits)  =>  d_ext = 11
                     and the list is complete.
    python code/dext/collect.py [OUTDIR] [w10|w11|both]
"""
import glob
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_cli import Verdict, circuit, load_code       # noqa: E402
from gross12 import ext as E                             # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "dext_run")
what = sys.argv[2] if len(sys.argv) > 2 else "both"
code = load_code()
V = Verdict()
f12 = circuit("fig12")
G = E.order_group(f12)
EXPECTED_W11_NODES = {"Z": 6174513371, "X": 5819348553}   # deterministic; informational
for basis in "ZX":
    if what in ("w10", "both"):
        jobs = [l.split() for l in open(out / "w10_jobs.txt") if l.startswith(basis + " ")]
        summ = []
        for fn in glob.glob(str(out / f"w10_out_{basis}_*.txt")):
            summ += [l for l in open(fn) if l.startswith("SUMMARY")]
        found = sum(int(re.search(r"found=(\d+)", l).group(1)) for l in summ)
        nodes = sum(int(re.search(r"nodes=(\d+)", l).group(1)) for l in summ)
        V(len(summ) == len(jobs) and found == 0,
          f"d_ext >= 11, {basis}-basis memory: W = 10 exhaustive search, {len(summ)}/{len(jobs)} jobs complete, "
          f"{found} solutions, {nodes:.3e} nodes")
    if what in ("w11", "both"):
        keys, sups, supkey = E.ext_columns(code, basis, f12)
        perms = E.column_perms(code, basis, f12, keys, sups, supkey, G)
        jobs = [l for l in open(out / "w11_jobs.txt") if l.startswith(basis + " ")]
        found, nodes, nsum, raw = set(), 0, 0, 0
        for fn in glob.glob(str(out / f"w11_out_{basis}_*.txt")):
            for line in open(fn):
                if line.startswith("SUMMARY"):
                    nodes += int(line.split()[4]); nsum += 1
                    continue
                S = tuple(map(int, line.split()))
                raw += 1
                for p in perms:
                    found.add(tuple(sorted(p[j] for j in S)))
        listed = {tuple(sorted(S)) for S in E.load_w11(basis)}
        V(nsum == len(jobs) and found == listed and len(found) == 4224,
          f"weight-11 list, {basis}-basis memory: {nsum}/{len(jobs)} jobs complete, {raw} raw solutions, "
          f"{nodes} nodes (reference run: {EXPECTED_W11_NODES[basis]}); expanded by the {len(G)} translations: "
          f"{len(found)} logicals, equal to data/logicals ({len(listed)})")
V.exit()
