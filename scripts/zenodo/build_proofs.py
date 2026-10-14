"""Copy the DRAT/LRAT certificate results of E-027 into release/zenodo/certificates/proofs/.

    uv run python scripts/zenodo/build_proofs.py [--max-ship-bytes 100e6]
Inputs (results/E-027-certificates/): part3/results.jsonl + part3/proofs/ (existing SM S10 CNFs),
lift_{A,B,C}/results.jsonl (Lemma 2 batches), lift_fig12/results.jsonl and control.txt (positive control),
tools/VERSIONS.txt.  Outputs: certificates_proofs.jsonl, drat/<name>.drat.xz (proofs up to the limit), logs/,
lift_circuit_{A,B,C}.jsonl, lift_control.txt, TOOLS.txt.
"""
import json
import lzma
import shutil
import sys
from pathlib import Path

RES = Path("results/E-027-certificates")
OUT = Path("release/zenodo/certificates/proofs")
limit = float(sys.argv[sys.argv.index("--max-ship-bytes") + 1]) if "--max-ship-bytes" in sys.argv else 100e6
(OUT / "drat").mkdir(parents=True, exist_ok=True)
(OUT / "logs").mkdir(parents=True, exist_ok=True)

recs = {}
for l in open(RES / "part3/results.jsonl"):
    r = json.loads(l)
    recs[r["name"]] = r                      # last record of a name wins (reruns)
shipped = 0
with open(OUT / "certificates_proofs.jsonl", "w") as f:
    for name in sorted(recs):
        r = dict(recs[name])
        r["cnf"] = r["cnf"].replace("release/zenodo/", "", 1)
        src = RES / "part3/proofs" / f"{name}.drat"
        r["proof_shipped"] = bool(r.get("drat_bytes") and r["drat_bytes"] <= limit and src.exists()
                                  and r.get("drat_trim", {}).get("verdict") == "VERIFIED")
        dst = OUT / "drat" / f"{name}.drat.xz"
        if r["proof_shipped"] and not dst.exists():
            with open(src, "rb") as fi, lzma.open(dst, "wb", preset=6) as fo:
                shutil.copyfileobj(fi, fo)
        if r["proof_shipped"]:
            r["proof_file"] = f"certificates/proofs/drat/{name}.drat.xz"
            r["proof_file_bytes"] = dst.stat().st_size
            shipped += 1
        for tool in ("drat-trim", "cake_lpr"):
            lg = RES / "part3/proofs" / f"{name}.{tool}.log"
            if lg.exists():
                shutil.copyfile(lg, OUT / "logs" / f"{name}.{tool}.log")
        f.write(json.dumps(r) + "\n")
print(len(recs), "certificate records,", shipped, "proofs shipped")

for circ in "ABC":
    src = RES / f"lift_{circ}/results.jsonl"
    if not src.exists():
        continue
    lift = {}
    for l in open(src):
        r = json.loads(l)
        r.pop("cnf", None)
        lift[r["name"]] = r
    lift = sorted(lift.values(), key=lambda r: (r["basis"], r["R"], r["split"][0]))
    with open(OUT / f"lift_circuit_{circ}.jsonl", "w") as f:
        for r in lift:
            f.write(json.dumps(r) + "\n")
    print(circ, len(lift), "lift batch records, all ok:", all(r["ok"] for r in lift))
ctl = RES / "control.txt"
if ctl.exists():
    shutil.copyfile(ctl, OUT / "lift_control.txt")
shutil.copyfile("tools/VERSIONS.txt", OUT / "TOOLS.txt")
