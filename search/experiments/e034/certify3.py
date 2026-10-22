"""E-034 driver: build the OPB instance (e031/build.py, unchanged), run the proof-logging search (e034/pbdfs.c =
e031/pbdfs.c with VeriPB 3.0 proof syntax) and check the proof with VeriPB 3 (tools/veripb, main branch).

    uv run python search/experiments/e034/certify3.py NAME SOURCE BASIS W --out DIR [--blocks FILE ...]
        [--stream | --keep] [--syntax 2]

--stream: the proof is never stored.  pbdfs writes it into a FIFO; this script relays it (computing sha256 and
          size of the exact byte stream VeriPB reads) into a second FIFO read by VeriPB.  Generation and checking
          run concurrently.  Without --stream the proof is written gzip-compressed and checked afterwards
          (deleted unless --keep).
UNSAT is accepted ONLY if VeriPB prints the line "s VERIFIED UNSATISFIABLE" (the exit code is recorded but not
used: VeriPB also exits 0 with "s VERIFIED NO CONCLUSION") AND the search ended with RESULT UNSAT.
SAT answers of the search are re-verified with e031/certify.verify_solution.
"""
import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BIN = ROOT / "results" / "E-034-veripb3-u11" / "bin" / "pbdfs"
VERIPB = ROOT / "tools" / "veripb" / "target" / "release" / "veripb"
sys.path.insert(0, str(ROOT / "search" / "experiments" / "e031"))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def cpu_children():
    r = resource.getrusage(resource.RUSAGE_CHILDREN)
    return r.ru_utime + r.ru_stime


def ensure_bin():
    src = HERE / "pbdfs.c"
    if not BIN.exists() or BIN.stat().st_mtime < src.stat().st_mtime:
        BIN.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(BIN) + ".tmp"          # build aside, then rename: a running pbdfs keeps its own (old) file
        subprocess.run(["cc", "-O2", "-Wall", "-o", tmp, str(src)], check=True)
        os.replace(tmp, BIN)


def verified(text):
    return any(l.strip() == "s VERIFIED UNSATISFIABLE" for l in text.splitlines())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name"); ap.add_argument("source"); ap.add_argument("basis"); ap.add_argument("W", type=int)
    ap.add_argument("--out", required=True)
    ap.add_argument("--blocks", nargs="*", default=[])
    ap.add_argument("--stream", action="store_true")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--syntax", default="3")
    ap.add_argument("--cachemax", type=int, default=0, help="pbdfs -F: bounded parity-clause cache (0 = E-031 behaviour)")
    a = ap.parse_args()
    ensure_bin()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    stem = out / a.name
    rec = {"name": a.name, "source": a.source, "basis": a.basis, "W": a.W, "blocks": a.blocks, "stream": a.stream,
           "syntax": a.syntax, "start": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "veripb_binary_sha256": sha(VERIPB), "pbdfs_src_sha256": sha(HERE / "pbdfs.c")}
    c0 = cpu_children()
    cmd = [sys.executable, str(ROOT / "search/experiments/e031/build.py"), a.source, a.basis, str(a.W), str(stem)]
    if a.blocks:
        cmd += ["--blocks"] + a.blocks
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        print(p.stdout, p.stderr); raise SystemExit("build failed")
    rec["build"] = {"cpu_s": round(cpu_children() - c0, 1), "meta": json.loads(Path(str(stem) + ".json").read_text())}
    rec["opb_sha256"] = sha(str(stem) + ".opb")
    extra = (["-2"] if a.syntax == "2" else []) + (["-F", str(a.cachemax)] if a.cachemax else [])
    rec["cachemax"] = a.cachemax
    vlog = open(str(stem) + ".veripb3.log", "w")
    slog = open(str(stem) + ".search.log", "w")
    t0 = time.time()
    if a.stream:
        f1, f2 = Path(str(stem) + ".fifo1"), Path(str(stem) + ".fifo2")
        for f in (f1, f2):
            if f.exists():
                f.unlink()
            os.mkfifo(f)
        ps = subprocess.Popen([str(BIN), str(stem) + ".inst", "-p", str(f1)] + extra, stdout=slog, stderr=subprocess.STDOUT)
        pv = subprocess.Popen([str(VERIPB), "--stats", str(stem) + ".opb", str(f2)], stdout=vlog, stderr=subprocess.STDOUT)
        h = hashlib.sha256(); nbytes = [0]

        # reader and writer decoupled by a bounded queue (up to ~512 MB in flight), so that generation and
        # checking overlap instead of alternating on the small OS pipe buffers
        import queue
        qu = queue.Queue(maxsize=512)

        def reader():
            fi = os.open(f1, os.O_RDONLY)
            try:
                while True:
                    b = os.read(fi, 1 << 20)
                    if not b:
                        break
                    h.update(b); nbytes[0] += len(b)
                    qu.put(b)
            finally:
                os.close(fi); qu.put(None)

        def writer():
            fo = os.open(f2, os.O_WRONLY)
            dead = False
            try:
                while True:
                    b = qu.get()
                    if b is None:
                        break
                    if dead:
                        continue           # keep draining so that the reader never blocks
                    mv = memoryview(b)
                    try:
                        while mv:
                            n = os.write(fo, mv); mv = mv[n:]
                    except BrokenPipeError:
                        rec["relay_error"] = "veripb closed its input early"; dead = True
            finally:
                os.close(fo)
        th = [threading.Thread(target=reader), threading.Thread(target=writer)]
        for t in th:
            t.start()
        rs = ps.wait()
        for t in th:
            t.join()
        rv = pv.wait()
        f1.unlink(); f2.unlink()
        rec["proof_bytes"] = nbytes[0]; rec["proof_sha256"] = h.hexdigest()
    else:
        proof = str(stem) + ".pbp.gz"
        rs = subprocess.run([str(BIN), str(stem) + ".inst", "-p", proof] + extra, stdout=slog, stderr=subprocess.STDOUT).returncode
        rv = None
        if rs == 0:
            rec["proof_bytes_gz"] = os.path.getsize(proof); rec["proof_gz_sha256"] = sha(proof)
            rv = subprocess.run([str(VERIPB), "--stats", str(stem) + ".opb", proof], stdout=vlog, stderr=subprocess.STDOUT).returncode
        if not a.keep and os.path.exists(proof):
            os.remove(proof)
    vlog.close(); slog.close()
    rec["wall_s"] = round(time.time() - t0, 1)
    rec["cpu_s_total_children"] = round(cpu_children() - c0, 1)
    stext = Path(str(stem) + ".search.log").read_text()
    vtext = Path(str(stem) + ".veripb3.log").read_text()
    res = [l for l in stext.splitlines() if l.startswith("RESULT")]
    rec["search"] = {"rc": rs, "result": res[-1] if res else None}
    rec["veripb"] = {"rc": rv, "verified_unsat": verified(vtext),
                     "tail": [l for l in vtext.splitlines() if l.strip()][-4:]}
    if rs == 2:
        from certify import verify_solution
        sol = [l for l in stext.splitlines() if l.startswith("SAT columns:")][-1]
        cols = [int(x) for x in sol.split(":")[1].split()]
        active = [tuple(int(v[2:]) - 1 for v in l.split() if v.startswith("~x")) for l in open(str(stem) + ".opb")
                  if l.startswith("1 ~x")]
        ok, blk = verify_solution(a.source, a.basis, cols, a.W, active)
        rec.update(verdict="SAT (logical found)", solution=cols, solution_verified=ok and not blk, ok=False)
    elif rs == 0 and rec["veripb"]["verified_unsat"] and res and res[-1].startswith("RESULT UNSAT"):
        rec.update(verdict="UNSAT (VeriPB 3: s VERIFIED UNSATISFIABLE)", ok=True)
    else:
        rec.update(verdict=f"NOT verified (search rc={rs}, veripb rc={rv})", ok=False)
    rec["end"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(out / "runs.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps({k: rec.get(k) for k in ("name", "verdict", "ok", "wall_s", "cpu_s_total_children", "proof_bytes")}),
          rec["search"]["result"], flush=True)
    sys.exit(0 if rec["ok"] else 1)


if __name__ == "__main__":
    main()
