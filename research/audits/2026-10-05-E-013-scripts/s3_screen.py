"""Evaluator screen on the auditor-built spec (identical to lead's)."""
import sys, json, time; sys.path.insert(0, "research/audits/2026-10-05-E-013-scripts")
from evaluators.pipeline import screen
spec = json.load(open("results/E-013-audit/spec_auditor.json"))
t0 = time.time()
rep = screen("bb108-dcirc", None, spec)
txt = rep.to_text()
open("results/E-013-audit/s3_screen.txt", "w").write(f"seconds {time.time()-t0:.0f}\n" + txt)
print(txt[:3000])
