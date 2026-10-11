"""E-024a: collect STATUS lines of all CEGAR logs into a table (results/E-024a-gross12-period/summary.tsv)."""
import glob
import re
from pathlib import Path

OUT = Path("results/E-024a-gross12-period")
rows = []
for f in sorted(glob.glob(str(OUT / "*.log"))):
    for line in open(f):
        if line.startswith("STATUS"):
            m = re.search(r"P=(\d+) \|H\|=(\d+) (\w+) it=(\d+).*?([\d.]+)s", line)
            if m:
                rows.append((Path(f).stem, int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4)), float(m.group(5))))
rows.sort(key=lambda r: (r[0].split("_")[0], r[1], -r[2]))
with open(OUT / "summary.tsv", "w") as fo:
    fo.write("log\tP\tH\tstatus\titers\tsec\n")
    for r in rows:
        fo.write("\t".join(map(str, r)) + "\n")
tot = sum(r[5] for r in rows)
print(len(rows), "runs; total wall-sec of finished CEGAR runs", round(tot), "=", round(tot / 3600, 2), "h")
for r in rows:
    print(*r, sep="\t")
