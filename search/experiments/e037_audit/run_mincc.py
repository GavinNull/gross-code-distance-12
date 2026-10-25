"""E-037 audit: independent minimum-weight computation on my own DEM (mydem.py) with mincc.c.

  uv run python search/experiments/e037_audit/run_mincc.py SRC W [--sym] [--out results/E-037-audit/mincc.jsonl]

--sym: use the translation group, verified here independently: every translation x^a y^b maps detector (check i,
cycle c) to (g(i), c), every column's image detector set is a column, and span(D, L o P) == span(D, L) (so P preserves
{x : Dx = 0, Lx != 0} together with weight).  Solutions printed by mincc are re-verified (silent, some observable odd,
weight) and, in sym mode, expanded under the group and de-duplicated, giving the total count.
"""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path

import mydem

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BIN = ROOT / "results" / "E-037-audit" / "bin" / "mincc"


def ensure_bin():
    src = HERE / "mincc.c"
    if not BIN.exists() or BIN.stat().st_mtime < src.stat().st_mtime:
        BIN.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["cc", "-O2", "-Wall", "-o", str(BIN), str(src)], check=True)


def group(src):
    D, L = src["D"], src["L"]
    n = len(D)
    index = {tuple(d): j for j, d in enumerate(D)}
    assert len(index) == n
    key = {tuple(c): i for i, c in enumerate(src["coords"])}
    l, m = src["l"], src["m"]
    Drows = mydem.rows_from(D, src["ndet"])
    Lrows = mydem.rows_from(L, src["nobs"])
    perms = []
    for a in range(l):
        for b in range(m):
            def tq(i):
                x, y = divmod(i, m)
                return ((x + a) % l) * m + (y + b) % m
            rp = [key[(tq(c[0]), c[1])] for c in src["coords"]]
            P = []
            for d in D:
                img = tuple(sorted(rp[x] for x in d))
                assert img in index, ("translation does not map columns", a, b)
                P.append(index[img])
            assert sorted(P) == list(range(n))
            # L o P^{-1}: row i of the translated observable = {P[j] : j in supp L_i}
            LP = []
            for r in Lrows:
                v, w = r, 0
                while v:
                    bb = v & -v
                    w |= 1 << P[bb.bit_length() - 1]
                    v ^= bb
                LP.append(w)
            ok, rk = mydem.same_logicals_mod_det(Drows, Lrows, LP)
            assert ok, ("translation does not preserve logicals mod detectors", a, b, rk)
            perms.append(P)
    return perms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("W", type=int)
    ap.add_argument("--sym", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "results" / "E-037-audit" / "mincc.jsonl"))
    ap.add_argument("--save", default=None, help="write all minimum-weight solutions (group-expanded) as JSON")
    a = ap.parse_args()
    ensure_bin()
    t0 = time.time()
    src = mydem.load(a.src)
    D, L = src["D"], src["L"]
    n = len(D)
    lines = [f"{n} {src['ndet']} {a.W} {1 if a.sym else 0}"]
    for d, o in zip(D, L):
        lines.append(f"{len(d)} " + " ".join(map(str, d)) + f" {sum(1 << x for x in o)}")
    perms = None
    if a.sym:
        perms = group(src)
        seen = [False] * n
        orbits = []
        for j in range(n):
            if seen[j]:
                continue
            o = sorted({P[j] for P in perms})
            for x in o:
                seen[x] = True
            orbits.append(o)
        lines.append(str(len(orbits)))
        for o in orbits:
            lines.append(f"{o[0]} {len(o)} " + " ".join(map(str, o)))
    tb = time.time() - t0
    t1 = time.time()
    r0 = os.times()
    p = subprocess.run([str(BIN)], input="\n".join(lines) + "\n", capture_output=True, text=True)
    r1 = os.times()
    assert p.returncode == 0, p.stderr[-2000:]
    sols = []
    done = None
    for ln in p.stdout.splitlines():
        if ln.startswith("SOL"):
            t = list(map(int, ln.split()[1:]))
            sols.append(tuple(sorted(t[1:])))
            assert t[0] == len(t) - 1
        elif ln.startswith("DONE"):
            done = ln
    assert done
    # re-verify
    bad = 0
    for s in sols:
        dd, oo = set(), set()
        for j in s:
            dd ^= set(D[j]); oo ^= set(L[j])
        if dd or not oo or len(s) > a.W or len(set(s)) != len(s):
            bad += 1
    minw = min((len(s) for s in sols), default=None)
    total = None
    if sols:
        mins = [s for s in sols if len(s) == minw]
        if perms:
            allx = set()
            for s in mins:
                for P in perms:
                    allx.add(tuple(sorted(P[j] for j in s)))
            total = len(allx)
            mins = sorted(allx)
        else:
            total = len(set(mins))
            assert total == len(mins), "duplicate solutions in nosym mode"
    if a.save and sols:
        Path(a.save).write_text(json.dumps(dict(src=a.src, minw=minw, sols=[list(s) for s in mins], D=D, L=L)))
    rec = dict(src=a.src, W=a.W, sym=a.sym, ncols=n, ndet=src["ndet"], group=len(perms) if perms else 1,
               result=done, nsol_printed=len(sols), bad=bad, minw=minw, count_minw_total=total,
               build_s=round(tb, 1), search_cpu_s=round((r1.children_user - r0.children_user), 1),
               wall_s=round(time.time() - t0, 1))
    with open(a.out, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec), flush=True)


if __name__ == "__main__":
    main()
