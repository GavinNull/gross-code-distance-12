"""E-044 CPU tally (seconds): stratified sampling from strat/*.jsonl (decode + sampling process time; +60 s per run
for DEM/decoder construction), sinter seconds of the anomaly run, enumeration wall (single-threaded, ~98% CPU), plus
a fixed allowance for probe / determinism / weights / analysis runs (logged in the journal).
  uv run python -m search.experiments.e044.cpu"""
import json
import re

import sinter

from search.experiments.e044.common import OUT

strat = 0.0
runs = set()
for f in (OUT / "strat").glob("*.jsonl"):
    for ln in f.read_text().splitlines():
        r = json.loads(ln)
        strat += r["sec_dec"] + r["sec_samp"]
        runs.add((f.name, r["tag"]))
strat += 60 * len(runs)
anom = sum(s.seconds for s in sinter.read_stats_from_csv_files(str(OUT / "anomaly_ibm_2e-3.csv")))
enum = 0.0
for b in "ZX":
    t = re.findall(r"orbit 11 done (\d+)s", (OUT / f"exact_g10_{b}_R1.log").read_text())
    enum += float(t[0]) if t else 0
other = 3 * 3600  # probe ~1.0 h, determinism 0.05 h, weights ~0.4 h, validation/analysis runs ~1 h, pk caches ~0.5 h
tot = strat + anom + enum + other
print(dict(strat_h=round(strat / 3600, 2), anomaly_h=round(anom / 3600, 2), enum_h=round(enum / 3600, 2),
           other_h=other / 3600, total_h=round(tot / 3600, 2)))
