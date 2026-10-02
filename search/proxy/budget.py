"""E-004 CPU accounting: sum of measured CPU seconds over everything written to results/E-004-proxy-fidelity/.

  PYTHONPATH=. uv run python -m search.proxy.budget

L2: decode+sample process time of every completed batch (cpu_s_all_batches) + per-worker decoder build overhead
estimated as workers x build time (not measured per batch; counted as 20 s per worker per run for n>=120 codes,
5 s otherwise).  Partial runs (batches dir without l2 json) are counted from their batch files.
Distance: RUSAGE self+children of each distance_proxy run.  Bad-schedule search: wall seconds x 2 workers.
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path("results/E-004-proxy-fidelity")


def main():
    tot = {"l2": 0.0, "l2_overhead": 0.0, "l2_partial": 0.0, "distance": 0.0, "bad_search": 0.0}
    done = set()
    for f in (OUT / "l2").glob("*.json"):
        d = json.loads(f.read_text())
        e = d["e004"]
        done.add(e["tag"])
        tot["l2"] += e["cpu_s_all_batches"]
        nw = d["inputs"]["num_workers"]
        tot["l2_overhead"] += nw * (20 if e["candidate"]["n"] >= 120 else 5)
    for bd in (OUT / "batches").glob("*"):
        if bd.name in done:
            continue
        for f in bd.glob("batch_*.json"):
            try:
                tot["l2_partial"] += json.loads(f.read_text())["cpu_s"]
            except Exception:  # noqa: BLE001 - file being written
                pass
    for f in (OUT / "distance").glob("*.json"):
        tot["distance"] += json.loads(f.read_text())["cpu_s_total"]
    log = OUT / "logs" / "bad_G.log"
    if log.exists():
        for line in log.read_text().splitlines():
            if line.startswith("{"):
                tot["bad_search"] += 2 * json.loads(line)["seconds"]
    s = sum(tot.values())
    print(json.dumps({k: round(v / 3600, 3) for k, v in tot.items()}), f"total {s / 3600:.2f} CPU h")


if __name__ == "__main__":
    main()
