"""VeriPB certificates of the extended-code distances and of the completeness of the lists of extended logicals.

Each record of certificates/veripb/records.jsonl is one statement "no extended logical of weight <= W other than the
blocked (listed) ones", i.e. an OPB instance (certificates/veripb/NAME.opb.gz, written by code/veripb/build_opb.py
from the data files) that is unsatisfiable.  The proof is produced by the deterministic proof-logging search
code/veripb/pbdfs.c and checked by VeriPB 3 (3.0.2).  The largest proofs (up to 4.6e11 bytes) are never stored:
pbdfs writes the proof into a FIFO, this script relays it to a second FIFO read by VeriPB and computes the SHA-256
and length of exactly the byte stream VeriPB reads.  Records keep that hash, so a re-run can be compared byte for
byte (same pbdfs.c, same -F cache bound).

Verdict rule: a run is accepted ONLY if VeriPB prints the line "s VERIFIED UNSATISFIABLE" AND exits with code 0 AND
the search ends with "RESULT UNSAT" (VeriPB also exits with 0 on "s VERIFIED NO CONCLUSION", so the exit code alone is
not sufficient).

    python code/veripb/certify.py list
    python code/veripb/certify.py opb all                     # rebuild every OPB / search input, compare sha256 with
                                                              # the record and with the shipped .opb.gz
    python code/veripb/certify.py check NAME ... [--max-nodes N] [--cachemax N] [--out DIR]
                                                              # regenerate the proof stream, check it with VeriPB,
                                                              # compare sha256 / length with the record
Tools: VERIPB (default tools/veripb/target/release/veripb; built by code/veripb/build_veripb.sh), a C compiler.
Memory: VeriPB keeps every live constraint (about 2-4 KB each); the weight-11 u11 proofs need about 18 GB with
-F 1000000 and about 40 GB with -F 0.  Disk: none (streamed).
"""
import argparse
import gzip
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
ROOT = HERE.parents[1]
CERT = ROOT / "certificates" / "veripb"
RECORDS = CERT / "records.jsonl"
VERIPB = os.environ.get("VERIPB", str(ROOT / "tools/veripb/target/release/veripb"))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def cpu_children():
    r = resource.getrusage(resource.RUSAGE_CHILDREN)
    return r.ru_utime + r.ru_stime


def load_records():
    return {r["name"]: r for r in map(json.loads, open(RECORDS))}


def build(rec, out):
    stem = out / rec["name"]
    cmd = [sys.executable, str(HERE / "build_opb.py"), rec["source"], rec["basis"], str(rec["W"]), str(stem)]
    if rec["blocks"]:
        cmd += ["--blocks"] + [str(ROOT / b) for b in rec["blocks"]]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return stem


def pbdfs_bin(out):
    b = out / "pbdfs"
    if not b.exists():
        subprocess.run(["cc", "-O2", "-o", str(b), str(HERE / "pbdfs.c")], check=True)
    return b


def stream_check(binp, stem, extra):
    """pbdfs -> FIFO -> (sha256, length) -> FIFO -> VeriPB; returns (search rc, veripb rc, bytes, sha256, logs)."""
    f1, f2 = Path(str(stem) + ".fifo1"), Path(str(stem) + ".fifo2")
    for f in (f1, f2):
        if f.exists():
            f.unlink()
        os.mkfifo(f)
    slog, vlog = open(str(stem) + ".search.log", "w"), open(str(stem) + ".veripb.log", "w")
    ps = subprocess.Popen([str(binp), str(stem) + ".inst", "-p", str(f1)] + extra, stdout=slog, stderr=subprocess.STDOUT)
    pv = subprocess.Popen([VERIPB, "--stats", str(stem) + ".opb", str(f2)], stdout=vlog, stderr=subprocess.STDOUT)
    h = hashlib.sha256(); nbytes = [0]; qu = queue.Queue(maxsize=512); err = []

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
                    err.append("VeriPB closed its input early"); dead = True
        finally:
            os.close(fo)
    th = [threading.Thread(target=reader), threading.Thread(target=writer)]
    for t in th:
        t.start()
    rs = ps.wait()
    for t in th:
        t.join()
    rv = pv.wait()
    f1.unlink(); f2.unlink(); slog.close(); vlog.close()
    return rs, rv, nbytes[0], h.hexdigest(), err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "opb", "check"])
    ap.add_argument("names", nargs="*")
    ap.add_argument("--out", default="veripb_run")
    ap.add_argument("--max-nodes", type=float, default=None, help="check only records with at most this many nodes")
    ap.add_argument("--cachemax", type=int, default=None, help="override the record's pbdfs -F bound (new proof)")
    ap.add_argument("--record-out", default=None, help="append a full record of every run to this file")
    a = ap.parse_args()
    recs = load_records()
    names = list(recs) if (not a.names or a.names == ["all"]) else a.names
    if a.max_nodes is not None:
        names = [n for n in names if recs[n].get("search", {}).get("nodes", 0) <= a.max_nodes]
    if a.cmd == "list":
        for n in names:
            r = recs[n]
            if r.get("proof_sha256") is None:
                print(f"{n:14s} {r['statement']}  (no run recorded)")
                continue
            print(f"{n:14s} {r['statement']}; {r['search']['nodes']:.3g} nodes, proof {r['proof_bytes'] / 1e9:.3g} GB, "
                  f"VeriPB {r['veripb']['cpu_s']:.0f} s, pbdfs -F {r['cachemax']}")
        return 0
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    bad = 0
    for n in names:
        r = recs[n]
        stem = build(r, out)
        o_ok = sha(str(stem) + ".opb") == r["opb_sha256"] and sha(str(stem) + ".inst") == r["inst_sha256"]
        with gzip.open(CERT / f"{n}.opb.gz", "rb") as f:
            shipped = hashlib.sha256(f.read()).hexdigest()
        o_ok &= shipped == r["opb_sha256"]
        if a.cmd == "opb":
            print(("PASS  " if o_ok else "FAIL  ") + f"{n}: OPB and search input rebuilt from the data files, sha256 "
                  f"= record = shipped {n}.opb.gz ({r['statement']})", flush=True)
            bad |= not o_ok
            continue
        cm = r["cachemax"] if a.cachemax is None else a.cachemax
        extra = ["-F", str(cm)] if cm else []
        c0, t0 = cpu_children(), time.time()
        rs, rv, nb, hx, err = stream_check(pbdfs_bin(out), stem, extra)
        stext = Path(str(stem) + ".search.log").read_text()
        vtext = Path(str(stem) + ".veripb.log").read_text()
        res = [l_ for l_ in stext.splitlines() if l_.startswith("RESULT")]
        verified = any(l_.strip() == "s VERIFIED UNSATISFIABLE" for l_ in vtext.splitlines())
        ok = o_ok and rs == 0 and rv == 0 and verified and bool(res) and res[-1].startswith("RESULT UNSAT") and not err
        same = cm == r["cachemax"] and r.get("proof_sha256") is not None
        ident = nb == r["proof_bytes"] and hx == r["proof_sha256"]
        if same:
            ok &= ident
        rec = {"name": n, "cachemax": cm, "proof_bytes": nb, "proof_sha256": hx, "search_rc": rs, "veripb_rc": rv,
               "verified_unsat_line": verified, "search_result": res[-1] if res else None,
               "cpu_s": round(cpu_children() - c0, 1), "wall_s": round(time.time() - t0, 1),
               "identical_to_record": ident if same else None}
        if a.record_out:
            with open(a.record_out, "a") as f:
                f.write(json.dumps(rec) + "\n")
        print(("PASS  " if ok else "FAIL  ") + f"{n}: {r['statement']}; VeriPB: 's VERIFIED UNSATISFIABLE' "
              f"{'yes' if verified else 'NO'}, exit code {rv}; search {' '.join(res[-1].split()[:4]) if res else rs}; "
              f"proof stream {nb} bytes, sha256 {'= record' if (same and ident) else ('differs from record' if same else '(new proof, -F ' + str(cm) + ')')}"
              f" ({rec['cpu_s']} CPU s)", flush=True)
        bad |= not ok
    return int(bad)


if __name__ == "__main__":
    sys.exit(main())
