"""E-042: OPB instances (E-031 encoding, e031/build.py imported unchanged) for the extended code of the period-10
gross circuit search/experiments/e040/g10_d12_spec.json.

Sides are named by kind as in E-031/E-032: kind X = X-check hooks, (H, L) = (HZ, LZ), i.e. the Z-basis memory;
kind Z = Z-check hooks, (HX, LX), the X-basis memory.  H, L and qubit indexing are e032.common.HLk (evaluator
build_code); the per-check CNOT orders are read from the circuit file (time order after the check's preparation,
cyclically modulo the period); residual supports = proper suffixes (e032.common.residuals).

    uv run python -m search.experiments.e042.pbbuild export KIND OUTDIR
        lists of E-040 (results/E-040-min-period/list{,11}_gross_KIND_A1A2B1A3B2B3.pkl) as column indices of
        build.build -> OUTDIR/g10_KIND_w10.json, g10_KIND_w11.json; asserts the column set equals the one of the
        audit's independent lists and that the lists are set-equal to the audit's.
    uv run python -m search.experiments.e042.pbbuild build KIND W OUTSTEM [--blocks F ...] [--drop-block i]
        same output as e031/build.py (OUTSTEM.opb/.inst/.json), with symmetry (72 translations).
"""
from __future__ import annotations

import json
import os
import pickle
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
for p in (str(ROOT), str(ROOT / "tests"), str(ROOT / "search/experiments/e031")):
    if p not in sys.path:
        sys.path.insert(0, p)

SPEC = ROOT / "search/experiments/e040/g10_d12_spec.json"
TYPE = "A1A2B1A3B2B3"
BASIS_OF_KIND = {"X": "Z", "Z": "X"}


def orders_from_spec(kind, spec=SPEC):
    s = json.load(open(spec))
    P = s["period"]
    return [[d for d, t in sorted(c["cnots"], key=lambda dt: (dt[1] - c["prep"]) % P)]
            for c in s["x_checks" if kind == "X" else "z_checks"]]


def load_g10(kind):
    cwd = os.getcwd()
    os.chdir(ROOT)
    from search.experiments.e032 import common as C
    H, L = C.HLk(kind)
    os.chdir(cwd)
    H = np.asarray(H, dtype=np.uint8) % 2
    L = np.asarray(L, dtype=np.uint8) % 2
    ords = orders_from_spec(kind)
    Hc = np.asarray(C.css().HX if kind == "X" else C.css().HZ, dtype=np.uint8) % 2
    for i, o in enumerate(ords):
        assert sorted(o) == np.nonzero(Hc[i])[0].tolist()
    sups = [(j,) for j in range(H.shape[1])] + [s for o in ords for s in C.residuals(o)]
    return dict(H=H, L=L, sups=sups, l=12, m=6, group=[(a, b) for a in range(12) for b in range(6)],
                name=f"g10_{kind}")


def key(H, L, S):
    return (H[:, list(S)].sum(1) % 2).astype(np.uint8).tobytes() + (L[:, list(S)].sum(1) % 2).astype(np.uint8).tobytes()


def export(kind, outdir):
    from build import build
    src = load_g10(kind)
    I = build(src, 11, ())
    H, L = src["H"], src["L"]
    idx = {key(H, L, S): j for j, S in enumerate(I["cols"])}
    # no column with zero H part (blocking B also blocks its supersets of size <= |B| + 1, harmless then)
    assert all(I["Hc"][:, j].any() for j in range(I["n"]))
    audit = ROOT / "results/E-040-audit-circ"
    out = {}
    for w, f in ((10, f"list_gross_{kind}_{TYPE}.pkl"), (11, f"list11_gross_{kind}_{TYPE}.pkl")):
        d = pickle.load(open(ROOT / "results/E-040-min-period" / f, "rb"))
        Lx = [sorted(idx[k] for k in keys) for keys in d["keys"]]
        assert all(len(set(x)) == w for x in Lx) and len({tuple(x) for x in Lx}) == len(Lx)
        a = pickle.load(open(audit / f"list_g10_{BASIS_OF_KIND[kind]}_w{w}.pkl", "rb"))
        assert set(a["colset"]) == set(idx), "column set differs from the audit's"
        assert {tuple(sorted(idx[k] for k in keys)) for keys in a["keys"]} == {tuple(x) for x in Lx}
        p = Path(outdir) / f"g10_{kind}_w{w}.json"
        p.write_text(json.dumps({"description": f"E-040 weight-{w} extended logicals of g10 kind {kind} ({f}), as "
                                 f"column indices of e031 build.build on e042.pbbuild.load_g10", "count": len(Lx),
                                 "logicals": [{"columns": x} for x in Lx]}))
        out[w] = len(Lx)
    print(kind, "columns", I["n"], "orbits", len(I["orbits"]), [len(o) for o in I["orbits"]], "lists", out,
          "logical rows", I["NL"], "basis", len(I["basis"]), flush=True)


def build_main(argv):
    import argparse
    from build import build, load_blocks, write
    ap = argparse.ArgumentParser()
    ap.add_argument("kind"); ap.add_argument("W", type=int); ap.add_argument("out")
    ap.add_argument("--blocks", nargs="*", default=[])
    ap.add_argument("--drop-block", type=int, default=None)
    a = ap.parse_args(argv)
    src = load_g10(a.kind)
    blocks = []
    for p in a.blocks:
        blocks += load_blocks(p, None)
    I = build(src, a.W, ())
    if a.drop_block is not None:
        b0 = tuple(sorted(blocks[a.drop_block]))
        orbit = {tuple(sorted(int(P[j]) for j in b0)) for P in I["perms"]}
        blocks = [b for b in blocks if tuple(sorted(b)) not in orbit]
        print("dropped", len(orbit), "blocked sets (orbit of block", a.drop_block, ")")
    I = build(src, a.W, blocks)
    meta = write(I, a.out)
    print(json.dumps({k: v for k, v in meta.items() if k not in ("row_sizes", "lrow_sizes")}))


if __name__ == "__main__":
    if sys.argv[1] == "export":
        export(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "build":
        build_main(sys.argv[2:])
