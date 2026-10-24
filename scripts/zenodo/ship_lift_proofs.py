"""After package re-runs of extended-lift batches (code/proofs/ext_lift_certs.py ... --keep-proofs), ship the DRAT proofs
up to a size limit (certificates/proofs/drat_lift/NAME.drat.xz), add the checker logs of re-run batches whose original
logs were not kept to logs/lift_<circuit>_logs.txt.gz, and record the re-runs in the records (field "rerun").

    uv run python scripts/zenodo/ship_lift_proofs.py OUTDIR [OUTDIR ...] [--max-bytes 5e6]
Every re-run must have CNF sha256 = record (asserted); proofs are shipped only if their sha256 equals the record.
"""
import gzip
import json
import lzma
import re
import shutil
import sys
from pathlib import Path

PR = Path("release/zenodo/certificates/proofs")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
lim = float(sys.argv[sys.argv.index("--max-bytes") + 1]) if "--max-bytes" in sys.argv else 5e6
if "--max-bytes" in sys.argv:
    args.remove(sys.argv[sys.argv.index("--max-bytes") + 1])
(PR / "drat_lift").mkdir(exist_ok=True)


def scrub(t):
    return re.sub(r"(/[^\s'\"]*)/([^/\s'\"]+)", r"\2", t)


runs = {}
for d in args:
    for l_ in open(Path(d) / "results.jsonl"):
        r = json.loads(l_)
        runs[r["name"]] = (r, Path(d))
shipped = 0
for circ in ("u11", "c11", "c12", "c13", "c16"):
    f = PR / f"lift_{circ}.jsonl"
    recs = [json.loads(l_) for l_ in open(f)]
    logf = PR / "logs" / f"lift_{circ}_logs.txt.gz"
    old = gzip.open(logf, "rt").read()
    have = set(re.findall(r"^==> (\S+)\.drat-trim\.log$", old, re.M))
    add = []
    for r in recs:
        if r["name"] not in runs:
            continue
        x, d = runs[r["name"]]
        assert x["cnf_sha256"] == r["cnf_sha256"], r["name"]
        r["rerun"] = {"cnf_identical": True, "drat_identical": x.get("drat_sha256") == r["drat_sha256"],
                      "solver": x["solver"]["answer"], "drat_trim": x.get("drat_trim", {}).get("verdict"),
                      "cake_lpr": x.get("cake_lpr", {}).get("verdict")}
        p = d / "work" / f"{r['name']}.drat"
        if p.exists() and p.stat().st_size <= lim and r["rerun"]["drat_identical"]:
            with open(p, "rb") as fi, lzma.open(PR / "drat_lift" / f"{r['name']}.drat.xz", "wb", preset=6) as fo:
                shutil.copyfileobj(fi, fo)
            r["proof_shipped"] = True
            r["proof_file"] = f"certificates/proofs/drat_lift/{r['name']}.drat.xz"
            shipped += 1
        if r["name"] not in have:
            for tool in ("cadical", "drat-trim", "cake_lpr"):
                lg = d / "work" / f"{r['name']}.{tool}.log"
                if lg.exists():
                    add.append(f"==> {r['name']}.{tool}.log  (package re-run)\n" + scrub(lg.read_text()))
    with open(f, "w") as fo:
        for r in recs:
            fo.write(json.dumps(r) + "\n")
    if add:
        with gzip.GzipFile(logf, "wb", mtime=0) as gz:
            gz.write((old + "".join(add)).encode())
    print(circ, "re-runs", sum("rerun" in r for r in recs), "logs added", len(add) // 3)
print("shipped", shipped, "proofs")
