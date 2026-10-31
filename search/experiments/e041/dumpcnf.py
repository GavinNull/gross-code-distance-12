"""E-041: write the DIMACS of a cached range encoder (rcegar pickle: legality + static patterns + lazy patterns so far),
optionally with a symmetric ansatz (sym.py) and/or fixed window starts as unit clauses, plus a json map of the
pi-literals and the tau order literals (for decoding a model with decode.py).
usage: uv run python -m search.experiments.e041.dumpcnf --tag W9_r1 --out x.cnf [--starts ...] [--sym s1R --C 8]"""
import argparse
import json
import pickle
import sys

OUT = "results/E-041-bb18-p9"

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--P", type=int, default=9)
    ap.add_argument("--starts", default=None)
    ap.add_argument("--sym", default=None)
    ap.add_argument("--C", type=int, default=8)
    a = ap.parse_args()
    sys.setrecursionlimit(100000)
    E, PE, pats = pickle.load(open(f"{OUT}/{a.tag}_enc.pkl", "rb"))
    if a.sym:
        from search.experiments.e041.sym import add_symmetry
        add_symmetry(E, a.sym, C=a.C)
    if a.starts:
        for k, v in zip(E.ks, [int(x) for x in a.starts.split(",")]):
            vv = [x for x in (v, v - a.P, v + a.P) if E.pi[k].lo <= x <= E.pi[k].hi]
            assert len(vv) == 1
            E.add([E.pi[k].eq(vv[0])])
    pil = {f"{k[0]}{k[1]}": {v: E.pi[k].eq(v) for v in range(E.pi[k].lo, E.pi[k].hi + 1)} for k in E.ks}
    with open(a.out, "w") as f:
        f.write(f"p cnf {E.nv} {len(E.cl)}\n")
        for c in E.cl:
            f.write(" ".join(map(str, c)) + " 0\n")
    tau = {f"{k[0]}{k[1]}:{x}": {"lo": E.tau[(k, x)].lo, "hi": E.tau[(k, x)].hi,
                                 "u": {str(t): v for t, v in E.tau[(k, x)].u.items()}} for k in E.ks for x in range(6)}
    json.dump({"pi_eq": pil, "tau": tau, "P": a.P, "nv": E.nv, "ncl": len(E.cl), "lazy": len(pats)},
              open(a.out.replace(".cnf", "_map.json"), "w"))
    print(E.nv, len(E.cl))
