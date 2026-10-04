"""E-012：穷举全部合法六色状态（跳过三色照抄），两段式：初筛 → 加大力度复核。lead。

    PYTHONPATH=. uv run python -m search.noninterleaved.six_screen --workers 8
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
    a = ap.parse_args()
    states = [tuple(s) for s in json.loads((OUT / "e012_proper_states.json").read_text())]
    lifts = [s for s in states if s[0] == s[1] and s[2] == s[3] and s[4] == s[5]]
    todo = [s for s in states if s not in set(lifts)]
    logf = open(OUT / "e012_screen.log", "a")
    recf = open(OUT / "e012_screen.jsonl", "a")

    def log(m):
        line = f"[{time.strftime('%H:%M:%S')}] {m}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    log(f"{len(states)} proper states, {len(lifts)} three-colour lifts skipped (known <= 9), screening {len(todo)}")
    dist, cands = {}, []
    with Pool(a.workers) as p:
        for n, (st, w) in enumerate(p.imap_unordered(weight, [(s, (0, 1), 300) for s in todo]), 1):
            recf.write(json.dumps({"stage": "screen", "state": st, "w": w}) + "\n")
            recf.flush()
            dist[w] = dist.get(w, 0) + 1
            if w is not None and w >= 10:
                cands.append(st)
            if n % 100 == 0:
                log(f"screen {n}/{len(todo)}: weight distribution {dict(sorted(dist.items(), key=str))}")
        log(f"screen done: {dict(sorted(dist.items(), key=str))}; {len(cands)} to harden")
        surv = []
        for n, st in enumerate(cands, 1):
            res = p.map(weight, [(st, (s,), 1000) for s in (11, 12, 13)])
            ws = [w for _, w in res]
            recf.write(json.dumps({"stage": "harden", "state": st, "ws": ws}) + "\n")
            recf.flush()
            if all(w is not None and w >= 10 for w in ws):
                surv.append(st)
                log(f"SURVIVOR {st} weights {ws}")
            if n % 20 == 0:
                log(f"harden {n}/{len(cands)}: survivors {len(surv)}")
    log(f"done: {len(todo)} screened, {len(cands)} hardened, {len(surv)} survivors")
    (OUT / "e012_survivors.json").write_text(json.dumps(surv))


if __name__ == "__main__":
    main()
