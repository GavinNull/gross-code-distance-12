"""E-037 task 2 (requested route): direct CNF of "undetectable logical of weight <= W" on a DEM, CaDiCaL + DRAT.

    uv run python search/experiments/e037/cnf_dem.py SOURCE W OUTDIR [--timeout S] [--minimal]

Encoding: x_j per column; every detector: Tseitin XOR chain (fresh variable per prefix, 4 clauses per link), last
link forced to 0; every observable i: chain with output o_i; one selector clause (o_1 v ... v o_k); |x| <= W by a
sequential counter (Sinz 2005).  --minimal adds the cardinality constraints of e037/dem_inst.small_trivial as
clauses (at most one of each trivial 3-set: pairwise binary clauses; at most two of each trivial 4-set: the four
3-subsets as negative clauses); same justification as in dem_inst.py.  Solved by CaDiCaL (tools/cadical) with a
DRAT proof, checked by drat-trim and cake_lpr via e027/certify.py (judged by output lines only).
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import dem_inst  # noqa: E402
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("e027_certify", ROOT / "search/experiments/e027/certify.py")
CE = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(CE)   # e027/certify.py (E-027 pipeline)

CE.CADICAL = str(ROOT / "tools/cadical/build/cadical")
CE.DRAT_TRIM = str(ROOT / "tools/drat-trim/drat-trim")
CE.CAKE_LPR = str(ROOT / "tools/cake_lpr/cake_lpr")


def encode(src, W, minimal=False):
    D, L = src["D"], src["L"]
    n = len(D)
    nv = [n]
    cl = []

    def new():
        nv[0] += 1
        return nv[0]

    def xor_chain(lits):
        """returns a literal equal to XOR(lits)"""
        acc = lits[0]
        for b in lits[1:]:
            y = new()
            cl.extend([[-y, acc, b], [-y, -acc, -b], [y, -acc, b], [y, acc, -b]])
            acc = y
        return acc
    rows = [[] for _ in range(src["ndet"])]
    obs = [[] for _ in range(src["nobs"])]
    for j, (d, o) in enumerate(zip(D, L)):
        for x in d:
            rows[x].append(j + 1)
        for x in o:
            obs[x].append(j + 1)
    for r in rows:
        if r:
            cl.append([-xor_chain(r)])
    cl.append([xor_chain(o) for o in obs if o])
    # sequential counter: s_{i,k} = at least k of x_1..x_i (k = 1..W), forbid W+1
    prev = [None] * (W + 1)
    for i in range(1, n + 1):
        cur = [None] * (W + 1)
        for k in range(1, W + 1):
            cur[k] = new()
        cl.append([-i, cur[1]])
        for k in range(1, W + 1):
            if prev[k] is not None:
                cl.append([-prev[k], cur[k]])
            if k > 1 and prev[k - 1] is not None:
                cl.append([-i, -prev[k - 1], cur[k]])
        if prev[W] is not None:
            cl.append([-i, -prev[W]])
        prev = cur
    if minimal:
        T3, T4 = dem_inst.small_trivial(D, L, 4)
        for t in T3:
            a, b, c = (v + 1 for v in t)
            cl.extend([[-a, -b], [-a, -c], [-b, -c]])
        for t in T4:
            v = [u + 1 for u in t]
            for skip in range(4):
                cl.append([-v[q] for q in range(4) if q != skip])
    return nv[0], cl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source"); ap.add_argument("W", type=int); ap.add_argument("out")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--minimal", action="store_true")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    src = dem_inst.load_source(a.source)
    nvar, cl = encode(src, a.W, a.minimal)
    name = a.source.replace(":", "_") + f"_W{a.W}" + ("_min" if a.minimal else "")
    cnf = out / f"{name}.src.cnf"
    with open(cnf, "w") as f:
        f.write(f"p cnf {nvar} {len(cl)}\n")
        for c in cl:
            f.write(" ".join(map(str, c)) + " 0\n")
    rec = CE.certify(cnf, out, name, timeout=a.timeout)
    rec.update(source=a.source, W=a.W, minimal=a.minimal)
    cnf.unlink()
    with open(out / "runs.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec))


if __name__ == "__main__":
    main()
