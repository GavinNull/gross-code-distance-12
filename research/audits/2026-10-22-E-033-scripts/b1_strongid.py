"""Auditor E-033, claim 3 (merge): group every sinter csv row used by e033.analyze by
(noise-normalised, circ, p, decoder, basis, R) and list the distinct strong_ids (sha256 of circuit text + DEM +
decoder name + json_metadata) per source.  Identical strong_id across E-033 and E-026/E-026b => byte-identical task."""
import glob, json
from collections import defaultdict
import sinter
ROOT = "/Users/ephemeral/Desktop/qec-ai-search/"
src = {"E033": glob.glob(ROOT + "results/E-033-gross-u11-ler/direct/*.csv"),
       "E026": glob.glob(ROOT + "results/E-026-gross-ler/direct/*.csv"),
       "E026b": glob.glob(ROOT + "results/E-026b-idle-sensitivity/direct/*.csv")}
ids = defaultdict(lambda: defaultdict(set))
for tag, files in src.items():
    for f in files:
        for s in sinter.read_stats_from_csv_files(f):
            m = s.json_metadata
            if m.get("R") != 12 or m["circ"] not in ("ibm", "fig12"):
                continue
            nz = m.get("noise", "lam1"); nz = "lam1" if nz == "sd6" else nz
            k = (nz, m["circ"], m["p"], s.decoder, m["basis"])
            ids[k][tag].add((s.strong_id[:12], json.dumps(m, sort_keys=True), f.split("/")[-1]))
out = []
for k in sorted(ids):
    if len(ids[k]) < 2 or "E033" not in ids[k]:
        continue
    new = {x[0] for x in ids[k]["E033"]}
    old = {x[0] for t in ids[k] if t != "E033" for x in ids[k][t]}
    print(k, "same-id" if new == old else "DIFF", {t: sorted(v) for t, v in ids[k].items()})
