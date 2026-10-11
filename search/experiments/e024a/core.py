"""E-024a: deletion-based extraction of a small set of modelled logicals (orbit reps of the family) whose blocking is
already impossible (CEGAR UNSAT with only those logicals), by chunked deletion.  Each test = one cegar run with
--rec_subset and --no_exact (model-SAT means the subset is not a core).

    PYTHONPATH=.:tests uv run python -m search.experiments.e024a.core --P 17 --sub "1,2;0,3" --tag core_P17_H24
"""
import argparse
import json
import subprocess
import time
from pathlib import Path

OUT = Path("results/E-024a-gross12-period")


def test(keep, a, k):
    f = OUT / f"{a.tag}_subset.json"
    f.write_text(json.dumps(keep))
    cmd = ["uv", "run", "python", "-m", "search.experiments.e024a.cegar", "--P", str(a.P), "--sub", a.sub,
           "--tighten", "0", "--no_exact", "1", "--rec_subset", str(f), "--max_sec", str(a.max_sec),
           "--tag", f"{a.tag}_t"] + (["--split_units", a.split_units] if a.split_units else []) + \
          (["--maxwin", str(a.maxwin)] if a.maxwin else []) + (["--winunits", a.winunits] if a.winunits else [])
    r = subprocess.run(cmd, capture_output=True, text=True, env={**__import__("os").environ, "PYTHONPATH": ".:tests"})
    st = [l for l in r.stdout.splitlines() if l.startswith("STATUS")]
    return st[-1] if st else "ERR " + r.stderr[-300:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--sub", default="1,2;0,3")
    ap.add_argument("--split_units", default="")
    ap.add_argument("--maxwin", type=int, default=0)
    ap.add_argument("--winunits", default="")
    ap.add_argument("--n", type=int, default=184, help="number of recs in the full family")
    ap.add_argument("--max_sec", type=float, default=900)
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    keep = list(range(a.n))
    t0 = time.time()
    st = test(keep, a, 0)
    print("full:", st, flush=True)
    assert " UNSAT " in st
    chunk = max(1, len(keep) // 4)
    while True:
        i = 0
        changed = False
        while i < len(keep):
            trial = keep[:i] + keep[i + chunk:]
            st = test(trial, a, i)
            ok = " UNSAT " in st
            print(f"size {len(keep)} chunk {chunk} remove [{i}:{i + chunk}] -> {'UNSAT keep removal' if ok else st[:60]} "
                  f"({time.time() - t0:.0f}s)", flush=True)
            if ok:
                keep = trial; changed = True
            else:
                i += chunk
        if chunk == 1:
            break
        chunk = max(1, chunk // 2)
    print("CORE", len(keep), keep, flush=True)
    (OUT / f"{a.tag}.json").write_text(json.dumps({"P": a.P, "sub": a.sub, "core": keep, "sec": round(time.time() - t0)}))


if __name__ == "__main__":
    main()
