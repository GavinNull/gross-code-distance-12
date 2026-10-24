"""Build release/zenodo/certificates/veripb/ (version 2.0): OPB files, records and checker logs of the VeriPB
certificates (d_ext and list completeness for Fig. 12, [[90,8,10]] and u11).

    PYTHONPATH=release/zenodo/code uv run python scripts/zenodo/build_veripb.py init
        rebuild every OPB / search input with the package's build_opb.py, ship NAME.opb.gz (gzip -n), write
        records.jsonl; results of reference runs of E-034 (VeriPB 3 streamed) are imported for u11 W = 10, 11 and
        [[90]] Z W = 9 after checking that the research OPB file has the same sha256
    ... build_veripb.py merge RUNS.jsonl LOGDIR
        merge the output of `code/veripb/certify.py check NAME --record-out RUNS.jsonl --out LOGDIR` (package
        pipeline runs) into records.jsonl (for records without an imported reference run) and copy their logs
Research sources: results/E-034-veripb3-u11/{u11,bb90}/runs.jsonl and *.veripb3.log / *.search.log.
"""
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REL = Path("release/zenodo")
CERT = REL / "certificates" / "veripb"
LOGS = CERT / "logs"
WORK = Path("results/zenodo_build/veripb")
L = "data/logicals/"
INST = []
for b in "ZX":
    for w in (5, 6, 7, 8):
        INST.append((f"fig12_{b}_W{w}", "fig12", b, w, [], f"Fig. 12 order class, {b}-basis memory: no extended logical "
                     f"of weight <= {w} (d_ext >= {w + 1})"))
for b in "ZX":
    INST.append((f"bb90_{b}_W7", "bb90", b, 7, [], f"[[90,8,10]] (c16 / c11 / c12 / c13 class), {b}-basis memory: no "
                 "extended logical of weight <= 7 (d_ext >= 8)"))
    INST.append((f"bb90_{b}_W8", "bb90", b, 8, [L + f"bb90_weight8_logicals_{b}_memory.json"],
                 f"[[90,8,10]], {b}-basis memory: the extended logicals of weight <= 8 are exactly the 585 listed"))
    INST.append((f"bb90_{b}_W9", "bb90", b, 9, [L + f"bb90_weight8_logicals_{b}_memory.json",
                                                 L + f"bb90_weight9_logicals_{b}_memory.json"],
                 f"[[90,8,10]], {b}-basis memory: the extended logicals of weight <= 9 are exactly the 585 + 16830 listed"))
for b in "ZX":
    INST.append((f"u11_{b}_W9", "u11", b, 9, [], f"u11, {b}-basis memory: no extended logical of weight <= 9 "
                 "(d_ext >= 10)"))
    INST.append((f"u11_{b}_W10", "u11", b, 10, [L + f"u11_weight10_logicals_{b}_memory.json"],
                 f"u11, {b}-basis memory: the extended logicals of weight <= 10 are exactly the 144 listed"))
    INST.append((f"u11_{b}_W11", "u11", b, 11, [L + f"u11_weight10_logicals_{b}_memory.json",
                                                 L + f"u11_weight11_logicals_{b}_memory.json"],
                 f"u11, {b}-basis memory: the extended logicals of weight <= 11 are exactly the 144 + 7344 listed"))
# research reference runs (E-034, VeriPB 3.0.2, streamed); E-031/E-032 name the u11 sides by hook kind:
# kind X = Z-basis memory, kind Z = X-basis memory
IMPORT = {"u11_Z_W10": ("u11", "u11_X_W10_list"), "u11_X_W10": ("u11", "u11_Z_W10_list"),
          "u11_Z_W11": ("u11", "u11_X_W11_lists_F1M"), "u11_X_W11": ("u11", "u11_Z_W11_lists"),
          "bb90_Z_W9": ("bb90", "bb90_Z_W9_lists")}
RES = Path("results/E-034-veripb3-u11")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def scrub(text):
    """drop directory parts of file paths in tool logs"""
    return re.sub(r"(/[^\s'\"]*)/([^/\s'\"]+)", r"\2", text)


def nodes_of(result):
    m = re.search(r"nodes=(\d+)", result or "")
    return int(m.group(1)) if m else None


def init():
    CERT.mkdir(parents=True, exist_ok=True); LOGS.mkdir(exist_ok=True); WORK.mkdir(parents=True, exist_ok=True)
    recs = []
    for name, src, b, w, blocks, stmt in INST:
        stem = WORK / name
        cmd = [sys.executable, str(REL / "code/veripb/build_opb.py"), src, b, str(w), str(stem)]
        if blocks:
            cmd += ["--blocks"] + [str(REL / x) for x in blocks]
        subprocess.run(cmd, check=True, capture_output=True)
        with open(str(stem) + ".opb", "rb") as fi, gzip.GzipFile(CERT / f"{name}.opb.gz", "wb", mtime=0) as fo:
            shutil.copyfileobj(fi, fo)
        meta = json.loads(Path(str(stem) + ".json").read_text())
        r = {"name": name, "statement": stmt, "source": src, "basis": b, "W": w, "blocks": blocks,
             "opb_file": f"certificates/veripb/{name}.opb.gz", "opb_sha256": sha(str(stem) + ".opb"),
             "inst_sha256": sha(str(stem) + ".inst"),
             "instance": {k: meta[k] for k in ("n", "R", "NL", "W", "nsym", "orbits", "blocks", "ncons", "nvars")},
             "cachemax": 0, "proof_format": "VeriPB 3.0", "proof_bytes": None, "proof_sha256": None,
             "proof_shipped": False}
        if name in IMPORT:
            d, rn = IMPORT[name]
            rr = [json.loads(l_) for l_ in open(RES / d / "runs.jsonl")]
            x = [q for q in rr if q["name"] == rn and q["ok"]][-1]
            assert x["opb_sha256"] == r["opb_sha256"], (name, "research OPB differs")
            assert x["stream"] and x["syntax"] == "3" and x["veripb"]["verified_unsat"] and x["veripb"]["rc"] == 0
            assert x["search"]["rc"] == 0 and x["search"]["result"].startswith("RESULT UNSAT")
            r.update(cachemax=x.get("cachemax") or 0, proof_bytes=x["proof_bytes"], proof_sha256=x["proof_sha256"],
                     search={"nodes": nodes_of(x["search"]["result"]), "result": x["search"]["result"]},
                     veripb={"version": "3.0.2", "verdict_line": "s VERIFIED UNSATISFIABLE", "rc": 0,
                             "cpu_s": float(re.search(r"time total: ([\d.]+)", " ".join(x["veripb"]["tail"])).group(1))},
                     cpu_s_total=x["cpu_s_total_children"], wall_s=x["wall_s"],
                     run="reference run (streamed; proof never stored)",
                     generator="code/veripb/pbdfs.c" + (f" -F {x['cachemax']}" if x.get("cachemax") else ""))
            stem_r = RES / d / rn
            for ext_, dst in ((".veripb3.log", ".veripb.log"), (".search.log", ".search.log")):
                Path(LOGS / f"{name}{dst}").write_text(scrub(Path(str(stem_r) + ext_).read_text()))
        recs.append(r)
    with open(CERT / "records.jsonl", "w") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    print(len(recs), "records,", sum(r["proof_sha256"] is not None for r in recs), "with imported reference runs")


def merge(runs, logdir):
    recs = [json.loads(l_) for l_ in open(CERT / "records.jsonl")]
    runs = {}
    for l_ in open(sys.argv[2]):
        x = json.loads(l_)
        runs[x["name"]] = x
    logdir = Path(logdir)
    n = 0
    for r in recs:
        x = runs.get(r["name"])
        if x is None:
            continue
        ok = x["search_rc"] == 0 and x["veripb_rc"] == 0 and x["verified_unsat_line"] and \
            x["search_result"].startswith("RESULT UNSAT")
        assert ok, x
        if r["proof_sha256"] is not None:
            # a package re-run of an imported reference run: record the comparison only
            r.setdefault("reruns", []).append({"identical": x["identical_to_record"], "cpu_s": x["cpu_s"]})
            assert x["identical_to_record"], x
            continue
        vt = (logdir / f"{r['name']}.veripb.log").read_text()
        r.update(cachemax=x["cachemax"], proof_bytes=x["proof_bytes"], proof_sha256=x["proof_sha256"],
                 search={"nodes": nodes_of(x["search_result"]), "result": x["search_result"]},
                 veripb={"version": "3.0.2", "verdict_line": "s VERIFIED UNSATISFIABLE", "rc": 0,
                         "cpu_s": float(re.search(r"time total: ([\d.]+)", vt).group(1))},
                 cpu_s_total=x["cpu_s"], wall_s=x["wall_s"], run="package pipeline (streamed; proof never stored)",
                 generator="code/veripb/pbdfs.c" + (f" -F {x['cachemax']}" if x["cachemax"] else ""))
        for ext_ in (".veripb.log", ".search.log"):
            Path(LOGS / f"{r['name']}{ext_}").write_text(scrub((logdir / f"{r['name']}{ext_}").read_text()))
        n += 1
    with open(CERT / "records.jsonl", "w") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    print("merged", n, "runs;", sum(r["proof_sha256"] is None for r in recs), "records without a run")


if __name__ == "__main__":
    if sys.argv[1] == "init":
        init()
    else:
        merge(sys.argv[2], sys.argv[3])
