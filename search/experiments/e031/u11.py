"""E-031 part 2: extended code of the E-032 circuit u11 (search/experiments/e032/u11_spec.json) for the VeriPB pipeline.

Sides are named by E-032's `kind` (common.py): kind X = X-check hooks, (H, L) = (HZ, LZ), i.e. the Z-basis memory;
kind Z = Z-check hooks, (HX, LX).  H, L and the qubit indexing are E-032's (evaluator build_code), the per-check CNOT
orders are read from the circuit file itself (time order of the CNOTs after the check's preparation, cyclically
modulo the period), residual supports = proper suffixes as in e032.common.residuals.

    uv run python search/experiments/e031/u11.py export KIND OUT_DIR
writes OUT_DIR/u11_KIND_w10.json, u11_KIND_w11.json (E-032 lists converted to column indices of build.build) and
checks that the column set equals the one of E-032's list files (uniform order class A1A2A3B3B1B2).
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def orders_from_spec(kind, spec=ROOT / "search/experiments/e032/u11_spec.json"):
    s = json.load(open(spec))
    P = s["period"]
    out = []
    for c in s["x_checks" if kind == "X" else "z_checks"]:
        out.append([d for d, t in sorted(c["cnots"], key=lambda dt: (dt[1] - c["prep"]) % P)])
    return out


def load_u11(kind):
    import os
    cwd = os.getcwd()
    os.chdir(ROOT)
    from search.experiments.e032 import common as C
    H, L = C.HLk(kind)
    os.chdir(cwd)
    H = np.asarray(H, dtype=np.uint8) % 2
    L = np.asarray(L, dtype=np.uint8) % 2
    ords = orders_from_spec(kind)
    # each check's order covers exactly its row of the check matrix of the opposite type (X check -> HX row)
    Hc = np.asarray(C.css().HX if kind == "X" else C.css().HZ, dtype=np.uint8) % 2
    for i, o in enumerate(ords):
        assert sorted(o) == np.nonzero(Hc[i])[0].tolist()
    sups = [(j,) for j in range(H.shape[1])] + [s for o in ords for s in C.residuals(o)]
    return dict(H=H, L=L, sups=sups, l=12, m=6, group=[(a, b) for a in range(12) for b in range(6)],
                name=f"u11_{kind}")


def e032key(H, L, S):
    return (H[:, list(S)].sum(1) % 2).astype(np.uint8).tobytes() + (L[:, list(S)].sum(1) % 2).astype(np.uint8).tobytes()


def export(kind, outdir):
    sys.path.insert(0, str(HERE))
    from build import build
    src = load_u11(kind)
    I = build(src, 11, ())
    H, L = src["H"], src["L"]
    idx = {e032key(H, L, S): j for j, S in enumerate(I["cols"])}
    R = ROOT / "results/E-032-gross-short-period"
    out = {}
    for w, f in ((10, f"w10_{kind}_all_A1A2A3B3B1B2.pkl"), (11, f"w11_{kind}_all_A1A2A3B3B1B2.pkl")):
        d = pickle.load(open(R / f, "rb"))
        assert set(d["colset"]) == set(idx), "u11 column set differs from the E-032 list's"
        L_ = [sorted(idx[k] for k in keys) for keys in d["keys"]]
        assert all(len(set(x)) == w for x in L_)
        p = Path(outdir) / f"u11_{kind}_w{w}.json"
        p.write_text(json.dumps({"description": f"E-032 weight-{w} extended logicals of u11 kind {kind} "
                                 f"({f}), as column indices of e031 build.build", "count": len(L_),
                                 "logicals": [{"columns": x} for x in L_]}))
        out[w] = len(L_)
    print(kind, "columns", I["n"], "orbits", len(I["orbits"]), "lists", out)


if __name__ == "__main__":
    if sys.argv[1] == "export":
        export(sys.argv[2], sys.argv[3])
