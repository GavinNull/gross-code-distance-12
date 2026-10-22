"""Auditor: regenerate an E-031 VeriPB certificate and re-check it (own driver, own output dir).

    uv run python research/audits/2026-10-22-E-031-scripts/regen.py NAME SOURCE BASIS W [--blocks F ...] [--keep]

1. build.py (E-031 encoder) -> results/E-031-audit/regen/NAME.{opb,inst,json}; sha256 of the .opb compared with
   the E-031 record of the same name (runs.jsonl);
2. pbdfs (E-031 search, compiled by the auditor into results/E-031-audit/bin) writes NAME.pbp.gz;
   sha256 of the decompressed proof is recorded (compared with w9_plain_sha256.txt when present);
3. VeriPB 2 (tools/veripb2 through veripb_run.py) on the .opb that the auditor's own encoder (myenc.py) reproduces
   (the build.py file is used only if it is byte-identical to the own one);
   accepted only if rc == 0 and both 'Verification succeeded.' and 's VERIFIED UNSATISFIABLE' are printed.
One JSON line per run -> results/E-031-audit/regen/regen.jsonl
"""
import glob
import hashlib
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results/E-031-audit/regen"
BIN = ROOT / "results/E-031-audit/bin/pbdfs"
E31 = ROOT / "search/experiments/e031"
PY = sys.executable


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sha_gz_plain(p):
    h = hashlib.sha256()
    proc = subprocess.Popen(["gzip", "-dc", str(p)], stdout=subprocess.PIPE)
    for b in iter(lambda: proc.stdout.read(1 << 20), b""):
        h.update(b)
    proc.wait()
    return h.hexdigest()


def cpu():
    r = resource.getrusage(resource.RUSAGE_CHILDREN)
    return r.ru_utime + r.ru_stime


def main():
    a = sys.argv[1:]
    name, source, basis, W = a[:4]
    keep = "--keep" in a
    blocks = []
    if "--blocks" in a:
        i = a.index("--blocks") + 1
        while i < len(a) and not a[i].startswith("--"):
            blocks.append(a[i]); i += 1
    OUT.mkdir(parents=True, exist_ok=True)
    stem = str(OUT / name)
    rec = {"name": name, "start": time.strftime("%Y-%m-%dT%H:%M:%S")}
    cmd = [PY, str(E31 / "build.py"), source, basis, W, stem] + (["--blocks"] + blocks if blocks else [])
    subprocess.run(cmd, check=True, capture_output=True)
    rec["opb_sha256"] = sha(stem + ".opb")
    old = None
    for f in glob.glob(str(ROOT / "results/E-031-xor-certificates/*/runs.jsonl")):
        for l in open(f):
            r = json.loads(l)
            if r["name"] == name and "opb_sha256" in r:
                old = r["opb_sha256"]
    rec["opb_matches_E031_record"] = (old == rec["opb_sha256"]) if old else None
    # own encoder
    my = stem + ".mine.opb"
    subprocess.run([PY, str(Path(__file__).parent / "myenc.py"), source, basis, W, my] + blocks, check=True)
    rec["own_encoder_byte_identical"] = sha(my) == rec["opb_sha256"]
    proof = stem + ".pbp.gz"
    c0, t0 = cpu(), time.time()
    p = subprocess.run([str(BIN), stem + ".inst", "-p", proof], capture_output=True, text=True)
    rec["search"] = {"rc": p.returncode, "cpu_s": round(cpu() - c0, 1), "wall_s": round(time.time() - t0, 1),
                     "result": [l for l in p.stdout.splitlines() if l.startswith("RESULT")][-1:]}
    if p.returncode != 0:
        rec["verdict"] = "search did not end UNSAT"
    else:
        rec["proof_gz_bytes"] = os.path.getsize(proof)
        rec["proof_plain_sha256"] = sha_gz_plain(proof)
        w9 = ROOT / "results/E-031-xor-certificates/w9_plain_sha256.txt"
        for l in open(w9):
            if l.split()[0] == name:
                rec["plain_sha_matches_E031"] = l.split()[1] == rec["proof_plain_sha256"]
        opb = my if rec["own_encoder_byte_identical"] else stem + ".opb"
        rec["veripb_on"] = "own encoder file" if opb == my else "build.py file"
        c0, t0 = cpu(), time.time()
        q = subprocess.run([PY, str(E31 / "veripb_run.py"), opb, proof], capture_output=True, text=True)
        Path(stem + ".veripb.log").write_text(q.stdout + q.stderr)
        ok = q.returncode == 0 and "Verification succeeded." in q.stdout and "s VERIFIED UNSATISFIABLE" in q.stdout
        rec["veripb"] = {"rc": q.returncode, "cpu_s": round(cpu() - c0, 1), "wall_s": round(time.time() - t0, 1),
                         "verified_unsat": ok}
        rec["verdict"] = "VERIFIED UNSAT" if ok else "NOT VERIFIED"
        if not keep:
            os.remove(proof)
    rec["end"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(OUT / "regen.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec))


if __name__ == "__main__":
    main()
