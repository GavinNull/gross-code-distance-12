"""Sequential, resumable job queue for E-004 L2 runs.

  PYTHONPATH=. uv run python -m search.proxy.queue results/E-004-proxy-fidelity/jobs_gold.txt --workers 4

Each non-comment line of the jobs file: <cand> <decoder> <rounds_mult: 1|h> <seed> <min_sector_errors> <max_shots>
("h" = rounds d/2).  A job is skipped if its output JSON already exists.  Stops (without starting the next job) if
the file STOP exists in results/E-004-proxy-fidelity/.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

OUT = Path("results/E-004-proxy-fidelity")


def main():
    jobs = Path(sys.argv[1])
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 4
    from search.proxy import candidates as C
    C.load_bad(OUT / "bad_schedules.json")
    for line in jobs.read_text().splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        if (OUT / "STOP").exists():
            print("STOP file present; exiting", flush=True)
            return
        cand, dec, rm, seed, mse, ms = line.split()
        d = C.get(cand).d
        rounds = d if rm == "1" else (d // 2 if rm == "h" else int(rm) * d)
        tag = f"{cand}__{dec}__r{rounds}__paper__s{seed}"
        if (OUT / "l2" / f"{tag}.json").exists():
            print(f"skip {tag}", flush=True)
            continue
        cmd = [sys.executable, "-m", "search.proxy.run_l2", "--cand", cand, "--decoder", dec, "--rounds", str(rounds),
               "--seed", seed, "--min-sector-errors", mse, "--max-shots", ms, "--workers", str(workers), "--tag", tag]
        print("RUN", " ".join(cmd), flush=True)
        with open(OUT / "logs" / f"{tag}.log", "w") as f:
            r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
        print(f"done {tag} rc={r.returncode}", flush=True)


if __name__ == "__main__":
    main()
