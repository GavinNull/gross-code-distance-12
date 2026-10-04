"""E-012 第二段：并行复核初筛中达到 10 的六色状态（状态 × 种子 全部放进同一个进程池）。lead。

    PYTHONPATH=. uv run python -m search.noninterleaved.six_harden --workers 8
"""
import argparse
import json
import time
from multiprocessing import Pool

from search.noninterleaved.run import OUT
from search.noninterleaved.six_colour import weight


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seeds", type=int, nargs="+", default=[11, 12, 13])
    ap.add_argument("--trials", type=int, default=1000)
    a = ap.parse_args()
    recs = [json.loads(l) for l in open(OUT / "e012_screen.jsonl")]
    cands = sorted({tuple(r["state"]) for r in recs if r.get("stage") == "screen" and r["w"] is not None
                    and r["w"] >= 10})
    logf = open(OUT / "e012_harden.log", "a")
    recf = open(OUT / "e012_harden.jsonl", "a")

    def log(m):
        line = f"[{time.strftime('%H:%M:%S')}] {m}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    log(f"{len(cands)} candidates x seeds {a.seeds} x {a.trials} trials")
    jobs = [(s, (sd,), a.trials) for s in cands for sd in a.seeds]
    res = {s: [] for s in cands}
    done = 0
    with Pool(a.workers) as p:
        for st, w in p.imap_unordered(weight, jobs):
            done += 1
            res[st].append(w)
            recf.write(json.dumps({"state": st, "w": w}) + "\n")
            recf.flush()
            if len(res[st]) == len(a.seeds) and all(x is not None and x >= 10 for x in res[st]):
                log(f"SURVIVOR {st} weights {res[st]}")
            if done % 150 == 0:
                killed = sum(1 for v in res.values() if any(x is not None and x < 10 for x in v))
                log(f"harden {done}/{len(jobs)} runs: states killed so far {killed}")
    surv = [s for s, v in res.items() if all(x is not None and x >= 10 for x in v)]
    log(f"done: {len(cands)} hardened, {len(surv)} survivors")
    (OUT / "e012_survivors.json").write_text(json.dumps(surv))


if __name__ == "__main__":
    main()
