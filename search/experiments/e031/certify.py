"""E-031 driver: build the OPB instance, run the proof-logging search, check the proof with VeriPB, log one JSON line.

    uv run python search/experiments/e031/certify.py NAME SOURCE BASIS W --out DIR [--blocks FILE ...]
        [--drop-block I] [--expect unsat|sat] [--no-sym] [--keep]

UNSAT is accepted only if VeriPB exits 0 and prints both "s VERIFIED UNSATISFIABLE" and "Verification succeeded."
(the proof ends with `conclusion UNSAT` pointing at a derived contradiction, so VeriPB checks the claim itself).
SAT answers of the (untrusted) search are re-verified here from the release data: H x = 0, L x != 0 (original
logical rows), |x| <= W, and x contains no blocked set.
Proofs are written gzip-compressed (VeriPB 2 reads .gz directly); --keep keeps them, otherwise only sha256 + size.
"""
import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BIN = ROOT / "results" / "E-031-xor-certificates" / "bin" / "pbdfs"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def cpu_children():
    r = resource.getrusage(resource.RUSAGE_CHILDREN)
    return r.ru_utime + r.ru_stime


def run(cmd, **kw):
    c0, t0 = cpu_children(), time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    return p, cpu_children() - c0, time.time() - t0


def ensure_bin():
    src = HERE / "pbdfs.c"
    if not BIN.exists() or BIN.stat().st_mtime < src.stat().st_mtime:
        BIN.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["cc", "-O2", "-Wall", "-o", str(BIN), str(src)], check=True)


def verify_solution(source, basis, cols, W, blocks):
    sys.path.insert(0, str(HERE))
    import numpy as np
    from build import load_ibm, load_release
    src = load_release(source, basis) if source in ("gross", "bb90") else load_ibm(source.split(":")[1], basis)
    H, L, sups = src["H"], src["L"], src["sups"]
    # column indices refer to the merged column list of build.build (identical to the release order for release data)
    from build import build
    I = build(src, W, ())
    e = np.zeros(H.shape[1], dtype=np.uint8)
    for j in cols:
        e[list(I["cols"][j])] ^= 1
    ok = (H @ e % 2 == 0).all() and (L @ e % 2).any() and len(cols) <= W and len(set(cols)) == len(cols)
    contains_block = any(set(b) <= set(cols) for b in blocks)
    return bool(ok), bool(contains_block)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("source")
    ap.add_argument("basis")
    ap.add_argument("W", type=int)
    ap.add_argument("--out", required=True)
    ap.add_argument("--blocks", nargs="*", default=[])
    ap.add_argument("--drop-block", type=int, default=None)
    ap.add_argument("--expect", choices=["unsat", "sat"], default="unsat")
    ap.add_argument("--no-sym", action="store_true")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    ensure_bin()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = out / a.name
    rec = {"name": a.name, "source": a.source, "basis": a.basis, "W": a.W, "blocks": a.blocks,
           "drop_block": a.drop_block, "expect": a.expect, "sym": not a.no_sym,
           "start": time.strftime("%Y-%m-%dT%H:%M:%S")}
    cmd = [sys.executable, str(HERE / "build.py"), a.source, a.basis, str(a.W), str(stem)]
    if a.blocks:
        cmd += ["--blocks"] + a.blocks
    if a.drop_block is not None:
        cmd += ["--drop-block", str(a.drop_block)]
    if a.no_sym:
        cmd += ["--no-sym"]
    p, c, t = run(cmd)
    if p.returncode:
        print(p.stdout, p.stderr)
        raise SystemExit("build failed")
    rec["build"] = {"cpu_s": round(c, 1), "meta": json.loads(Path(str(stem) + ".json").read_text())}
    rec["opb_sha256"] = sha(str(stem) + ".opb")
    proof = str(stem) + ".pbp.gz"
    cmd = [str(BIN), str(stem) + ".inst", "-p", proof]
    if a.limit:
        cmd += ["-n", str(a.limit)]
    p, c, t = run(cmd)
    res = [l for l in p.stdout.splitlines() if l.startswith("RESULT")]
    rec["search"] = {"rc": p.returncode, "cpu_s": round(c, 1), "wall_s": round(t, 1), "result": res[-1] if res else None,
                     "stderr": p.stderr[-500:]}
    Path(str(stem) + ".search.log").write_text(p.stdout + p.stderr)
    if p.returncode == 2:
        sol = [l for l in p.stdout.splitlines() if l.startswith("SAT columns:")][-1]
        cols = [int(x) for x in sol.split(":")[1].split()]
        listed = []
        for f in a.blocks:
            listed += [tuple(e["columns"]) for e in json.load(open(f))["logicals"]]
        # blocked sets actually in the instance (after --drop-block): read back from the OPB file
        active = [tuple(int(v[2:]) - 1 for v in l.split()[1::2]) for l in open(str(stem) + ".opb")
                  if l.startswith("1 ~x")]
        ok, blk = verify_solution(a.source, a.basis, cols, a.W, active)
        rec["verdict"] = "SAT"
        rec["solution"] = cols
        rec["solution_verified"] = ok and not blk
        rec["solution_in_given_list"] = any(set(b) == set(cols) for b in listed)
        rec["ok"] = (a.expect == "sat") and ok and not blk
        os.remove(proof)
    elif p.returncode == 0:
        rec["proof_bytes_gz"] = os.path.getsize(proof)
        rec["proof_sha256"] = sha(proof)
        q, c2, t2 = run([sys.executable, str(HERE / "veripb_run.py"), "--stats", str(stem) + ".opb", proof])
        Path(str(stem) + ".veripb.log").write_text(q.stdout + q.stderr)
        verified = (q.returncode == 0 and "s VERIFIED UNSATISFIABLE" in q.stdout
                    and "Verification succeeded." in q.stdout)
        rec["veripb"] = {"rc": q.returncode, "cpu_s": round(c2, 1), "wall_s": round(t2, 1),
                         "verified_unsat": verified,
                         "tail": [l for l in q.stdout.splitlines() if "VERIFIED" in l or "Verification" in l
                                  or "Failed" in l or "Hint" in l][:4]}
        rec["verdict"] = "UNSAT (VeriPB verified)" if verified else "UNSAT claimed, proof NOT verified"
        rec["ok"] = (a.expect == "unsat") and verified
        if not a.keep:
            os.remove(proof)
    else:
        rec["verdict"] = f"search rc={p.returncode}"
        rec["ok"] = False
    rec["end"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(out / "runs.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps({k: rec[k] for k in ("name", "verdict", "ok")}),
          rec["search"]["result"], rec.get("veripb", {}).get("cpu_s"), rec.get("proof_bytes_gz"))
    sys.exit(0 if rec["ok"] else 1)


if __name__ == "__main__":
    main()
