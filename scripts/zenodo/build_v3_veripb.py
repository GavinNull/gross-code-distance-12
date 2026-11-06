"""g10 VeriPB records for release/zenodo/certificates/veripb/ (version 3.0).

    uv run python scripts/zenodo/build_v3_veripb.py
The certified run named its instances by the error type (g10_X_W10 = X errors = Z-basis memory); the package names
them by the memory basis like every other record.  The OPB rebuilt from the package data files must be byte-identical
to the certified run's OPB (asserted); OPB (gz), search input sha256 and checker logs are shipped.  The proofs were
checked while being written (gzip on disk) and deleted afterwards; their compressed size and hash are kept.
"""
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REL = Path("release/zenodo")
CERT = REL / "certificates" / "veripb"
PB = Path("results/E-042-g10-cert/pb")
runs = {}
for f in (PB / "runs.jsonl", PB / "certs" / "runs.jsonl"):
    for l in open(f):
        r = json.loads(l)
        runs[r["name"]] = r
KIND = {"Z": "X", "X": "Z"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


recs = [json.loads(l) for l in open(CERT / "records.jsonl")]
recs = [r for r in recs if r["source"] != "g10"]
tmp = Path(tempfile.mkdtemp())
for basis in "ZX":
    for W in (10, 11):
        name = f"g10_{basis}_W{W}"
        src = runs[f"g10_{KIND[basis]}_W{W}"]
        blocks = [f"data/logicals/g10_weight10_logicals_{basis}_memory.json"]
        if W == 11:
            blocks.append(f"data/logicals/g10_weight11_logicals_{basis}_memory.json")
        stem = tmp / name
        subprocess.run([sys.executable, str(REL / "code/veripb/build_opb.py"), "g10", basis, str(W), str(stem),
                        "--blocks"] + [str(REL / b) for b in blocks], check=True, capture_output=True)
        ho = sha(str(stem) + ".opb")
        assert ho == src["opb_sha256"], (name, "OPB differs from the certified run")
        with open(str(stem) + ".opb", "rb") as fi, open(CERT / f"{name}.opb.gz", "wb") as fo:
            with gzip.GzipFile(filename="", mode="wb", fileobj=fo, mtime=0, compresslevel=9) as g:
                shutil.copyfileobj(fi, g)
        meta = src["build"]["meta"]
        res = src["search"]["result"]
        nodes = int(re.search(r"nodes=(\d+)", res).group(1))
        stmt = (f"g10, {basis}-basis memory: no extended logical of weight <= {W} other than the "
                f"{'3204' if W == 10 else '3204 + 121104'} listed (d_ext >= 10"
                f"{'' if W == 10 else ', complete weight-11 list'})")
        rec = {"name": name, "statement": stmt, "source": "g10", "basis": basis, "W": W, "blocks": blocks,
               "opb_file": f"certificates/veripb/{name}.opb.gz", "opb_sha256": ho,
               "inst_sha256": sha(str(stem) + ".inst"),
               "instance": {k: meta[k] for k in ("n", "R", "NL", "W", "nsym", "orbits", "blocks", "ncons", "nvars")},
               "cachemax": src["cachemax"], "proof_format": "VeriPB 3.0", "proof_bytes": None, "proof_sha256": None,
               "proof_gz_bytes": src["proof_bytes_gz"], "proof_gz_sha256": src["proof_gz_sha256"],
               "proof_shipped": False, "search": {"nodes": nodes, "result": res},
               "veripb": {"version": "3.0.2", "verdict_line": "s VERIFIED UNSATISFIABLE", "rc": src["veripb"]["rc"],
                          "time_total_s": float(src["veripb"]["tail"][-1].split()[-2])},
               "cpu_s_total": src["cpu_s_total_children"], "wall_s": src["wall_s"],
               "run": "reference run (proof written gzip-compressed, checked by VeriPB, then deleted; "
                      "proof_gz_* refer to that compressed file)",
               "generator": "code/veripb/pbdfs.c"}
        recs.append(rec)
        d = PB if W == 10 else PB / "certs"
        for kind, tag in (("search", "search"), ("veripb3", "veripb")):
            t = (d / f"g10_{KIND[basis]}_W{W}.{kind}.log").read_text()
            t = re.sub(r"(/[^\s'\"]*)/([^/\s'\"]+)", r"\2", t)
            (CERT / "logs" / f"{name}.{tag}.log").write_text(t)
        print(name, "OPB identical", ho[:12], "nodes", nodes)
with open(CERT / "records.jsonl", "w") as f:
    for r in recs:
        f.write(json.dumps(r) + "\n")
shutil.rmtree(tmp)
print("records:", len(recs))
