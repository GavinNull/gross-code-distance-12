"""Build release/zenodo/data/ler/ (version 2.0): sampling statistics and summaries of the logical-error-rate
comparisons (SM S7, S8) and of the independent re-sampling.

    uv run python scripts/zenodo/build_ler.py
Sources: results/E-030-bb90-period-ler/direct/*.csv + direct_summary_R10.json + analyze_final.txt ([[90]], SD6 lambda);
results/E-033-gross-u11-ler/direct/*.csv + direct_summary.json + analyze_final.txt (gross), pooled with the identical
fig12 / ibm tasks of results/E-026-gross-ler/direct and results/E-026b-idle-sensitivity/direct (R = 12, as the E-033
analysis did); results/E-035-neutral-atom-ler/direct/{main,sens}.csv + summary.{json,md}; the independent re-sampling
of the audits (results/E-030-audit/a2_*, results/E-033-audit/s_*, results/E-035-audit/s_*).
"""
import csv
import io
import json
import shutil
from pathlib import Path

OUT = Path("release/zenodo/data/ler")
for d in ("sd6_lambda_bb90", "sd6_lambda_gross/earlier", "neutral_atom", "independent_resampling"):
    (OUT / d).mkdir(parents=True, exist_ok=True)

src = Path("results/E-030-bb90-period-ler")
for f in sorted((src / "direct").glob("*.csv")):
    shutil.copyfile(f, OUT / "sd6_lambda_bb90" / f.name)
shutil.copyfile(src / "direct_summary_R10.json", OUT / "sd6_lambda_bb90" / "summary.json")
shutil.copyfile(src / "analyze_final.txt", OUT / "sd6_lambda_bb90" / "summary.txt")

src = Path("results/E-033-gross-u11-ler")
for f in sorted((src / "direct").glob("*.csv")):
    shutil.copyfile(f, OUT / "sd6_lambda_gross" / f.name)
shutil.copyfile(src / "direct_summary.json", OUT / "sd6_lambda_gross" / "summary.json")
txt = (src / "analyze_final.txt").read_text().replace("E-033 sinter seconds", "sinter seconds (new sampling)")
(OUT / "sd6_lambda_gross" / "summary.txt").write_text(txt)
n_old = 0
for tag, d in (("a", Path("results/E-026-gross-ler/direct")), ("b", Path("results/E-026b-idle-sensitivity/direct"))):
    for f in sorted(d.glob("*.csv")):
        lines = f.read_text().splitlines(keepends=True)
        keep = [lines[0]]
        for line in lines[1:]:
            row = next(csv.reader(io.StringIO(line)))
            m = json.loads(row[6])
            if m.get("R") == 12 and m["circ"] in ("u11", "fig12", "ibm"):
                keep.append(line)
        if len(keep) > 1:
            (OUT / "sd6_lambda_gross" / "earlier" / f"earlier_{tag}_{f.name}").write_text("".join(keep))
            n_old += len(keep) - 1
print("earlier fig12 / ibm rows:", n_old)

src = Path("results/E-035-neutral-atom-ler")
for f in ("main.csv", "sens.csv"):
    shutil.copyfile(src / "direct" / f, OUT / "neutral_atom" / f)
shutil.copyfile(src / "summary.json", OUT / "neutral_atom" / "summary.json")
shutil.copyfile(src / "summary.md", OUT / "neutral_atom" / "summary.md")

for name, smp, summ in (("bb90_sd6_lambda", "results/E-030-audit/a2_sample.jsonl", "results/E-030-audit/a2_summary.json"),
                        ("gross_sd6_lambda", "results/E-033-audit/s_sample.jsonl", "results/E-033-audit/s_summary.json"),
                        ("neutral_atom", "results/E-035-audit/s_sample.jsonl", "results/E-035-audit/s_summary.json")):
    shutil.copyfile(smp, OUT / "independent_resampling" / f"{name}_jobs.jsonl")
    t = Path(summ).read_text().replace("pooled_with_experimenter", "pooled_with_first_pipeline").replace('"mine"', '"second_pipeline"')
    (OUT / "independent_resampling" / f"{name}_summary.json").write_text(t)
print("ler data written")
