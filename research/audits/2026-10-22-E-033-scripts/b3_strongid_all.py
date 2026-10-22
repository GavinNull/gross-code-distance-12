"""Auditor E-033 claim 3: every ibm/fig12 R=12 row that e033.analyze reads (E-026, E-026b, E-033 csvs, any noise it
prints: sd6/lam0/lam0.1/lam1): recompute the strong_id from the CURRENT e033.common.noisy() circuit with the row's own
metadata, and compare with the stored strong_id."""
import sys, glob
from collections import defaultdict
sys.path[:0] = ["/Users/ephemeral/Desktop/qec-ai-search", "/Users/ephemeral/Desktop/qec-ai-search/tests"]
import sinter
from search.experiments.e033.common import noisy
ROOT = "/Users/ephemeral/Desktop/qec-ai-search/"
files = glob.glob(ROOT + "results/E-026-gross-ler/direct/*.csv") + glob.glob(ROOT + "results/E-026b-idle-sensitivity/direct/*.csv") + glob.glob(ROOT + "results/E-033-gross-u11-ler/direct/*.csv")
seen = {}
for f in files:
    for s in sinter.read_stats_from_csv_files(f):
        m = s.json_metadata
        if m.get("R") != 12 or m["circ"] not in ("ibm", "fig12", "u11"):
            continue
        nz = m.get("noise", "lam1")
        if nz not in ("sd6", "lam0", "lam0.1", "lam1"):
            continue
        k = (s.strong_id, f.split("/")[-1])
        if k in seen:
            continue
        model = "lam1" if nz == "sd6" else nz
        c = noisy(m["circ"], m["basis"], 12, m["p"], model)
        mm = dict(circ=m["circ"], basis=m["basis"], p=m["p"], R=12, noise=nz)  # creation key order (json key order enters the hash)
        t = sinter.Task(circuit=c, decoder=s.decoder, json_metadata=mm, detector_error_model=c.detector_error_model(
            decompose_errors=False, allow_gauge_detectors=False, approximate_disjoint_errors=True))
        seen[k] = (t.strong_id() == s.strong_id, m, s.decoder)
bad = [v for v in seen.values() if not v[0]]
print("distinct (strong_id, file) checked:", len(seen), "mismatches:", len(bad))
for v in bad: print(v)
