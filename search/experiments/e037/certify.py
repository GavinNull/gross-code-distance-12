"""E-037 driver: certify "no undetectable logical of weight <= W" on a DEM with VeriPB 3.  experimenter.

    uv run python search/experiments/e037/certify.py SOURCE W --out DIR [--stream | --keep] [--cachemax N]

Steps (all logged to DIR/runs.jsonl):
 1. dem_inst.py SOURCE W  (no blocks)                                   -> NAME_p1.{opb,inst,json,cols.json}
 2. pbdfs NAME_p1.inst -R NAME.triv   (count-only pass: records the trivial sets met at nodes with budget left)
 3. dem_inst.py SOURCE W --blocks NAME.triv   (blocks closed under the group; every block checked trivial)
 4. pbdfs NAME.inst -p PROOF  ->  VeriPB 3  NAME.opb PROOF   (streamed through two FIFOs, sha256 of the exact byte
    stream; or written gzip'ed and checked afterwards)
UNSAT is accepted only if VeriPB prints "s VERIFIED UNSATISFIABLE" and the search ended "RESULT UNSAT".
"""
import argparse
import hashlib
import json
import os
import queue
import resource
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BIN = ROOT / "results" / "E-037-ibm-cert" / "bin" / "pbdfs"
VERIPB = ROOT / "tools" / "veripb" / "target" / "release" / "veripb"


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
        tmp = str(BIN) + ".tmp"
        subprocess.run(["cc", "-O2", "-Wall", "-o", tmp, str(src)], check=True)
        os.replace(tmp, BIN)


def verified(text):
    return any(l.strip() == "s VERIFIED UNSATISFIABLE" for l in text.splitlines())


def run_build(args, log):
    p = subprocess.run([sys.executable, str(HERE / "dem_inst.py")] + args, capture_output=True, text=True)
    log.write(p.stdout + p.stderr)
    if p.returncode:
        raise SystemExit("build failed:\n" + p.stdout + p.stderr)


def stream(stem, extra, rec):
    f1, f2 = Path(str(stem) + ".fifo1"), Path(str(stem) + ".fifo2")
    for f in (f1, f2):
        if f.exists():
            f.unlink()
        os.mkfifo(f)
    slog = open(str(stem) + ".search.log", "w")
    vlog = open(str(stem) + ".veripb3.log", "w")
    ps = subprocess.Popen([str(BIN), str(stem) + ".inst", "-p", str(f1)] + extra, stdout=slog, stderr=subprocess.STDOUT)
    pv = subprocess.Popen([str(VERIPB), "--stats", str(stem) + ".opb", str(f2)], stdout=vlog, stderr=subprocess.STDOUT)
    rec["pids"] = [ps.pid, pv.pid]
    h = hashlib.sha256(); nbytes = [0]
    qu = queue.Queue(maxsize=512)

    def reader():
        fi = os.open(f1, os.O_RDONLY)
        try:
            while True:
                b = os.read(fi, 1 << 20)
                if not b:
                    break
                h.update(b); nbytes[0] += len(b); qu.put(b)
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
                    continue
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
    slog.close(); vlog.close()
    rec["proof_bytes"] = nbytes[0]; rec["proof_sha256"] = h.hexdigest()
    return rs, rv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source"); ap.add_argument("W", type=int)
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", default=None)
    ap.add_argument("--stream", action="store_true")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--cachemax", type=int, default=0)
    ap.add_argument("--sym", choices=["proof", "formula"], default="formula")
    ap.add_argument("--gz", action="store_true", help="write the proof gzip-compressed (extra gzip process)")
    a = ap.parse_args()
    ensure_bin()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    name = a.name or a.source.replace(":", "_") + f"_W{a.W}"
    stem = out / name
    rec = {"name": name, "source": a.source, "W": a.W, "sym": a.sym, "start": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "veripb_binary_sha256": sha(VERIPB), "pbdfs_src_sha256": sha(HERE / "pbdfs.c"),
           "dem_inst_sha256": sha(HERE / "dem_inst.py"), "ibm_model_sha256": sha(HERE / "ibm_model.py")}
    blog = open(str(stem) + ".build.log", "w")
    c0 = cpu_children(); t0 = time.time()
    run_build([a.source, str(a.W), str(stem) + "_p1", "--no-symcheck", "--sym", a.sym], blog)
    p = subprocess.run([str(BIN), str(stem) + "_p1.inst", "-R", str(stem) + ".triv"], capture_output=True, text=True)
    Path(str(stem) + ".pass1.log").write_text(p.stdout + p.stderr)
    res1 = [l for l in p.stdout.splitlines() if l.startswith("RESULT")]
    rec["pass1"] = {"rc": p.returncode, "result": res1[-1] if res1 else None, "cpu_s": round(cpu_children() - c0, 1)}
    if p.returncode == 2:
        sol = [l for l in p.stdout.splitlines() if l.startswith("SAT columns:")][-1]
        rec.update(verdict="SAT (logical found in pass 1)", solution=[int(x) for x in sol.split(":")[1].split()], ok=False)
        with open(out / "runs.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(json.dumps(rec)); sys.exit(1)
    for ext in (".opb", ".inst"):
        os.remove(str(stem) + "_p1" + ext)
    c1 = cpu_children()
    run_build([a.source, str(a.W), str(stem), "--blocks", str(stem) + ".triv", "--sym", a.sym], blog)
    blog.close()
    meta = json.loads(Path(str(stem) + ".json").read_text())
    rec["build"] = {"cpu_s": round(cpu_children() - c1, 1), "meta": meta}
    rec["opb_sha256"] = meta["opb_sha256"]
    rec["triv_sha256"] = sha(str(stem) + ".triv")
    extra = ["-F", str(a.cachemax)] if a.cachemax else []
    rec["cachemax"] = a.cachemax
    c2 = cpu_children(); t2 = time.time()
    if a.stream:
        rs, rv = stream(stem, extra, rec)
    else:
        proof = str(stem) + (".pbp.gz" if a.gz else ".pbp")
        with open(str(stem) + ".search.log", "w") as slog:
            rs = subprocess.run([str(BIN), str(stem) + ".inst", "-p", proof] + extra, stdout=slog,
                                stderr=subprocess.STDOUT).returncode
        rv = None
        if rs == 0:
            rec["proof_file_bytes"] = os.path.getsize(proof); rec["proof_file_sha256"] = sha(proof)
            rec["proof_gz"] = a.gz
            tv = time.time(); cv = cpu_children()
            with open(str(stem) + ".veripb3.log", "w") as vlog:
                rv = subprocess.run([str(VERIPB), "--stats", str(stem) + ".opb", proof], stdout=vlog,
                                    stderr=subprocess.STDOUT).returncode
            rec["veripb_cpu_s"] = round(cpu_children() - cv, 1); rec["veripb_wall_s"] = round(time.time() - tv, 1)
        if not a.keep and os.path.exists(proof):
            os.remove(proof)
    rec["certify_wall_s"] = round(time.time() - t2, 1)
    rec["certify_cpu_s"] = round(cpu_children() - c2, 1)
    rec["wall_s"] = round(time.time() - t0, 1)
    rec["cpu_s_total_children"] = round(cpu_children() - c0, 1)
    stext = Path(str(stem) + ".search.log").read_text()
    vtext = Path(str(stem) + ".veripb3.log").read_text() if Path(str(stem) + ".veripb3.log").exists() else ""
    res = [l for l in stext.splitlines() if l.startswith("RESULT")]
    rec["search"] = {"rc": rs, "result": res[-1] if res else None}
    rec["veripb"] = {"rc": rv, "verified_unsat": verified(vtext),
                     "tail": [l for l in vtext.splitlines() if l.strip()][-6:]}
    if rs == 0 and rec["veripb"]["verified_unsat"] and res and res[-1].startswith("RESULT UNSAT"):
        rec.update(verdict="UNSAT (VeriPB 3: s VERIFIED UNSATISFIABLE)", ok=True)
    else:
        rec.update(verdict=f"NOT verified (search rc={rs}, veripb rc={rv})", ok=False)
    rec["end"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(out / "runs.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps({k: rec.get(k) for k in ("name", "verdict", "ok", "wall_s", "cpu_s_total_children",
                                              "proof_bytes", "proof_file_bytes", "veripb_cpu_s")}),
          rec["search"]["result"], flush=True)
    sys.exit(0 if rec["ok"] else 1)


if __name__ == "__main__":
    main()
