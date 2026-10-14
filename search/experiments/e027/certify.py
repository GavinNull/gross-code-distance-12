"""Produce and check an unsatisfiability proof for one CNF, or for a list of CNFs in parallel.

For each instance:
  1. CaDiCaL solves the CNF and writes a DRAT proof (binary format);           exit code 20 = UNSAT
  2. drat-trim checks the DRAT proof (backward checking) and writes the core lemmas as an LRAT proof;
  3. cake_lpr (the formally verified CakeML checker) checks that LRAT proof   (optional; skipped if absent).
The result record has the solver answer, the checker verdicts, wall/CPU seconds of each step, proof sizes and
sha256 of the CNF (uncompressed), the DRAT proof and the LRAT proof.

    python certify.py one  CNF[.gz] OUTDIR NAME [--timeout S] [--keep]
    python certify.py many JOBS.tsv OUTDIR RESULTS.jsonl [--workers N] [--timeout S] [--keep]
JOBS.tsv: one "NAME<TAB>CNF path" per line.  Already recorded names in RESULTS.jsonl are skipped.
Tools: $CADICAL, $DRAT_TRIM, $CAKE_LPR (default: the names on $PATH).  --keep keeps the proof files
(otherwise they are deleted after checking; their sha256 and sizes are recorded).
"""
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CADICAL = os.environ.get("CADICAL", "cadical")
DRAT_TRIM = os.environ.get("DRAT_TRIM", "drat-trim")
CAKE_LPR = os.environ.get("CAKE_LPR", "cake_lpr")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def run(cmd, timeout=None, stdout_path=None):
    """Run cmd; return (exit code or None on timeout, stdout text, wall s, cpu s of the child)."""
    t0 = time.time()
    out = open(stdout_path, "wb") if stdout_path else subprocess.PIPE
    p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT)
    deadline = None if timeout is None else t0 + timeout
    code = None
    while True:
        pid, status, ru = os.wait4(p.pid, os.WNOHANG)
        if pid:
            code = os.waitstatus_to_exitcode(status)
            break
        if deadline and time.time() > deadline:
            p.kill()                       # our own child, by its PID
            pid, status, ru = os.wait4(p.pid, 0)
            code = None
            break
        time.sleep(0.05)
    p.returncode = 0 if code is None else code
    text = ""
    if stdout_path:
        out.close()
        text = Path(stdout_path).read_text(errors="replace")
    else:
        text = p.stdout.read().decode(errors="replace")
    return code, text, time.time() - t0, ru.ru_utime + ru.ru_stime


def certify(cnf, outdir, name, timeout=7200, keep=False):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    rec = {"name": name, "cnf": str(cnf)}
    plain = outdir / f"{name}.cnf"
    if str(cnf).endswith(".gz"):
        with gzip.open(cnf, "rb") as fi, open(plain, "wb") as fo:
            shutil.copyfileobj(fi, fo)
    else:
        shutil.copyfile(cnf, plain)
    rec["cnf_sha256"] = sha256(plain)
    with open(plain) as f:
        for line in f:
            if line.startswith("p cnf"):
                rec["vars"], rec["clauses"] = map(int, line.split()[2:4])
                break
    drat, lrat = outdir / f"{name}.drat", outdir / f"{name}.lrat"
    code, text, wall, cpu = run([CADICAL, "-q", "--binary=true", str(plain), str(drat)], timeout,
                                outdir / f"{name}.cadical.log")
    rec["solver"] = {"exit": code, "answer": {20: "UNSAT", 10: "SAT"}.get(code, "UNKNOWN" if code is None else
                                                                           f"error {code}"),
                     "wall_s": round(wall, 2), "cpu_s": round(cpu, 2)}
    if code == 20:
        rec["drat_bytes"] = drat.stat().st_size
        rec["drat_sha256"] = sha256(drat)
        code2, text2, wall2, cpu2 = run([DRAT_TRIM, str(plain), str(drat), "-t", str(int(timeout)), "-w",
                                         "-L", str(lrat)], timeout + 60, outdir / f"{name}.drat-trim.log")
        verified = any(l.strip() == "s VERIFIED" for l in text2.splitlines())
        timed_out = code2 is None or "TIMEOUT" in text2
        rec["drat_trim"] = {"verdict": "VERIFIED" if verified else ("TIMEOUT" if timed_out else "FAILED"),
                            "wall_s": round(wall2, 2), "cpu_s": round(cpu2, 2)}
        if verified and lrat.exists():
            rec["lrat_bytes"] = lrat.stat().st_size
            rec["lrat_sha256"] = sha256(lrat)
            if shutil.which(CAKE_LPR) or Path(CAKE_LPR).exists():
                code3, text3, wall3, cpu3 = run([CAKE_LPR, str(plain), str(lrat)], timeout,
                                                outdir / f"{name}.cake_lpr.log")
                ok = "s VERIFIED UNSAT" in text3
                rec["cake_lpr"] = {"verdict": "VERIFIED UNSAT" if ok else ("TIMEOUT" if code3 is None else "FAILED"),
                                   "wall_s": round(wall3, 2), "cpu_s": round(cpu3, 2)}
    if not keep:
        for p in (drat, lrat):
            if p.exists():
                p.unlink()
    plain.unlink()
    rec["ok"] = (rec["solver"]["answer"] == "UNSAT" and rec.get("drat_trim", {}).get("verdict") == "VERIFIED"
                 and rec.get("cake_lpr", {"verdict": "VERIFIED UNSAT"})["verdict"] == "VERIFIED UNSAT")
    return rec


def main(argv):
    opts = {"--timeout": 7200, "--workers": 1}
    keep = "--keep" in argv
    argv = [a for a in argv if a != "--keep"]
    pos = []
    i = 0
    while i < len(argv):
        if argv[i] in opts:
            opts[argv[i]] = int(argv[i + 1])
            i += 2
        else:
            pos.append(argv[i])
            i += 1
    if pos[0] == "one":
        rec = certify(pos[1], pos[2], pos[3], opts["--timeout"], keep)
        print(json.dumps(rec))
        print("PASS" if rec["ok"] else "FAIL", rec["name"])
        return 0 if rec["ok"] else 1
    jobs = [l.rstrip("\n").split("\t") for l in open(pos[1]) if l.strip()]
    res = Path(pos[3])
    done = set()
    if res.exists():
        done = {json.loads(l)["name"] for l in res.open() if l.strip()}
    todo = [j for j in jobs if j[0] not in done]
    print(f"{len(jobs)} jobs, {len(done)} done, {len(todo)} to run", flush=True)

    def one(job):
        rec = certify(job[1], pos[2], job[0], opts["--timeout"], keep)
        with res.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        print(("PASS" if rec["ok"] else "FAIL"), rec["name"], rec["solver"], rec.get("drat_trim"),
              rec.get("cake_lpr"), flush=True)
        return rec["ok"]

    with ThreadPoolExecutor(opts["--workers"]) as ex:
        oks = list(ex.map(one, todo))
    return 0 if all(oks) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
