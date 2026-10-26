"""E-039 cube-and-conquer over prep times: cubes = all value vectors of pi for a chosen list of checks (pi of the first
check is fixed to 0 by the encoding; every schedule of the class has at least one legal pi vector, so the cubes cover
the class).  Inside each cube: scegar.Driver.run with the cube as assumptions (patterns are global, shared across
cubes of one worker; workers also re-read the other workers' pattern files between cubes).
usage: uv run python -m search.experiments.e039.pcube W 8 --checks Z0,X1,Z1 --shard 0/8"""
import argparse
import glob
import itertools
import json
import random
import time

from search.experiments.e038.cegar import load_patterns
from search.experiments.e039.scegar import OUT, Driver


def parse_check(s):
    return (s[0], int(s[1:]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cls")
    ap.add_argument("P", type=int)
    ap.add_argument("--checks", required=True)
    ap.add_argument("--static", default="HH,HHM,DDH")
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--lns", type=int, default=5)
    ap.add_argument("--resume", default="")
    ap.add_argument("--tag", default="")
    ap.add_argument("--seed", type=int, default=20261027)
    a = ap.parse_args()
    sh, n = map(int, a.shard.split("/"))
    tag = f"{a.cls}{a.P}{a.tag}_pc{sh}of{n}"
    D = Driver(a.cls, a.P, a.static.split(","), [p for p in a.resume.split(",") if p], tag=tag, seed=a.seed + sh)
    E = D.E
    cks = [parse_check(c) for c in a.checks.split(",")]
    vals = [range(E.pi[k].lo, E.pi[k].hi + 1) for k in cks]
    allc = list(itertools.product(*vals))
    order = list(range(len(allc)))
    random.Random(a.seed).shuffle(order)
    mine = [i for j, i in enumerate(order) if j % n == sh]
    done = json.load(open(f"{OUT}/{tag}_done.json")) if glob.glob(f"{OUT}/{tag}_done.json") else []
    seen_files = {}
    t0 = time.time()
    for ci in mine:
        if ci in done:
            continue
        # import patterns learned by other workers
        for path in glob.glob(f"{OUT}/{a.cls}{a.P}{a.tag}_pc*_patterns.json"):
            if path.endswith(f"_pc{sh}of{n}_patterns.json"):
                continue
            try:
                for pat in load_patterns(path):
                    D.add(pat)
            except Exception:
                pass
        cube = [E.pi[k].eq(v) for k, v in zip(cks, allc[ci])]
        cube = [l for l in cube if l is not True]
        assert all(l is not False for l in cube)
        tc = time.time()
        res, info = D.run(cube=cube, nlns=a.lns)
        D.logw({"cube": ci, "vals": allc[ci], "res": res, "iters": info if res != "FOUND" else None,
                "sec": round(time.time() - tc, 1), "patterns": len(D.pats), "done": len(done) + 1, "of": len(mine),
                "total": round(time.time() - t0, 1)})
        if res == "FOUND":
            break
        done.append(ci)
        D.save()
        json.dump(done, open(f"{OUT}/{tag}_done.json", "w"))
    D.logw({"result": "SHARD_DONE", "shard": sh, "cubes": len(done)})
