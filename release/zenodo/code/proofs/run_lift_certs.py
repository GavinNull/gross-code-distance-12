"""Lift certificates of circuits A, B, C (SM S13): for each (circuit, basis, R) write the batch CNFs of lift_cnf.py, refute each with CaDiCaL
(DRAT), check with drat-trim (and the LRAT core with cake_lpr unless --no-cake), record, delete the files.

    python run_lift_certs.py CIRCUIT RANGE OUTDIR [--basis Z X] [--workers N] [--no-cake] [--expect sat]
RANGE e.g. 1-32.  One job per (basis, R); split K = max(1, ceil(R/2)) batches (about <= 3 M clauses each).
Results: OUTDIR/results.jsonl (one record per batch CNF, with sha256 of CNF / DRAT / LRAT); finished batches are
skipped on restart.  --expect sat: positive control (Fig. 12), each batch must be SAT.
--compare REC.jsonl (e.g. certificates/proofs/lift_circuit_A.jsonl): also require that the batch CNF has the recorded
sha256 (the CNFs are deterministic); a differing DRAT proof (other CaDiCaL build) is reported, not an error.
"""
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import certify as C            # noqa: E402
import lift_cnf as LC          # noqa: E402


def parse_range(s):
    out = []
    for part in s.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def job(args):
    circ, basis, R, outdir, cake, expect, done, ref = args
    outdir = Path(outdir)
    lists, groups, st = LC.setup(circ, basis, R)
    K = max(1, math.ceil(R / 2))
    recs = []
    for s in range(K):
        name = f"{circ}_{basis}_R{R}_s{s}of{K}"
        if name in done:
            continue
        idx = list(range(s, len(lists), K))
        b = LC.batch(lists, groups, idx)
        cnf = outdir / "tmp" / f"{name}.cnf"
        cnf.parent.mkdir(parents=True, exist_ok=True)
        LC.write(cnf, b, [f"lift batch: circuit {circ}, {basis}-basis memory, R = {R}, weight-11 logicals i = {s} mod "
                          f"{K} ({len(idx)} instances); selector variables 1..{len(idx)}; UNSAT iff no instance lifts"])
        if not cake:
            os.environ["CAKE_LPR"] = "/nonexistent"
            C.CAKE_LPR = "/nonexistent"
        rec = C.certify(cnf, outdir / "work", name, timeout=7200, keep=False)
        cnf.unlink()
        rec.update(circuit=circ, basis=basis, R=R, split=[s, K], instances=len(idx), dem=st)
        if expect == "sat":
            rec["ok"] = rec["solver"]["answer"] == "SAT"
        if ref is not None:
            want = ref.get(name)
            rec["cnf_matches_record"] = bool(want) and want["cnf_sha256"] == rec["cnf_sha256"]
            rec["drat_matches_record"] = bool(want) and want.get("drat_sha256") == rec.get("drat_sha256")
            rec["ok"] = rec["ok"] and rec["cnf_matches_record"]
        with open(outdir / "results.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(("PASS" if rec["ok"] else "FAIL"), name, f"{rec['instances']} instances, {rec['clauses']} clauses:",
              rec["solver"]["answer"], "drat-trim", rec.get("drat_trim", {}).get("verdict", "-"),
              "cake_lpr", {"not run": "SKIP (not run)"}.get(rec.get("cake_lpr", {}).get("verdict", "-"),
                                                           rec.get("cake_lpr", {}).get("verdict", "-")),
              *([f"cnf sha256 {'= record' if rec['cnf_matches_record'] else 'DIFFERS'}, proof "
                 f"{'= record' if rec['drat_matches_record'] else 'differs from record'}"] if ref is not None else []),
              flush=True)
        recs.append(rec["ok"])
    return all(recs)


def main(argv):
    circ, rng, outdir = argv[0], parse_range(argv[1]), Path(argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    bases = ["Z", "X"]
    if "--basis" in argv:
        i = argv.index("--basis") + 1
        bases = []
        while i < len(argv) and not argv[i].startswith("--"):
            bases.append(argv[i]); i += 1
    workers = int(argv[argv.index("--workers") + 1]) if "--workers" in argv else 1
    cake = "--no-cake" not in argv
    expect = "sat" if "--expect" in argv else "unsat"
    res = outdir / "results.jsonl"
    done = {json.loads(l)["name"] for l in res.open()} if res.exists() else set()
    ref = None
    if "--compare" in argv:
        ref = {json.loads(l)["name"]: json.loads(l) for l in open(argv[argv.index("--compare") + 1])}
    jobs = [(circ, b, R, str(outdir), cake, expect, done, ref) for R in sorted(rng, reverse=True) for b in bases]
    with ProcessPoolExecutor(workers) as ex:
        oks = list(ex.map(job, jobs))
    print(("PASS" if all(oks) else "FAIL"), f"lift certificates circuit {circ}, R = {argv[1]}, bases {' '.join(bases)}: "
          f"{'every batch ' + ('SAT' if expect == 'sat' else 'UNSAT with a verified proof') if all(oks) else 'some batch failed'}")
    return 0 if all(oks) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
