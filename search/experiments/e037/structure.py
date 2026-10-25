"""E-037 task 1: structural checks of the IBM-model rebuild.  experimenter.

  uv run python search/experiments/e037/structure.py [--R 1 2 3] > results/E-037-ibm-cert/structure.json

1. codes: n, k (rank), logical bases; a weight-d logical exists (upper bound; d itself is the published value of
   arXiv:2308.07915 Table 3, not re-proved here)
2. our gate list (ibm_model.cycle, built from decoder_setup.py's description) == baselines.schedule.ibm_depth8
   (the circuit of E-026/E-033) layer by layer (CNOT sets, preps, measurements)
3. IBM model columns: numpy frame simulator, decoder_setup.py-faithful (no reset at PrepX in the X simulator) vs
   resetting simulator vs stim circuit: identical merged column sets
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE))
import ibm_model as im  # noqa: E402


def check_schedule(code):
    from baselines.bb_code import BBCode
    from baselines.schedule import ibm_depth8
    bb = BBCode(code.l, code.m, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"])
    assert (np.asarray(bb.HX) % 2 == code.hx).all() and (np.asarray(bb.HZ) % 2 == code.hz).all(), "H differs"
    s = ibm_depth8(bb)
    cyc = im.cycle(code)
    out = []
    for t, (L, g) in enumerate(zip(s.layers, cyc)):
        mine = dict(cn={(a[1], a[2]) for a in g if a[0] == "CNOT"}, px={a[1] for a in g if a[0] == "PrepX"},
                    pz={a[1] for a in g if a[0] == "PrepZ"}, mx={a[1] for a in g if a[0] == "MeasX"},
                    mz={a[1] for a in g if a[0] == "MeasZ"})
        ours = dict(cn=set(map(tuple, L.cnots)), px=set(L.prep_x), pz=set(L.prep_z), mx=set(L.meas_x),
                    mz=set(L.meas_z))
        same = all(mine[k] == ours[k] for k in mine)
        out.append(dict(layer=t, same=same, ncnot=len(mine["cn"])))
    assert len(s.layers) == len(cyc) == 8
    # within-round order matters only through 'MeasZ before CNOTs' in round 6 (disjoint qubits) -> irrelevant
    return out


def min_logical_weight_witness(code):
    """A weight-d logical (upper bound check): search translates of short combinations is overkill; use the known
    IBM-paper logical form via BP-OSD-free method: low-weight vectors in ker(hx) found by random info-set decoding."""
    rng = np.random.default_rng(37)
    best = None
    H = code.hx
    n = code.n
    for _ in range(4000):
        perm = rng.permutation(n)
        R, piv = im.rref(H[:, perm])
        # nullspace vectors with one free variable set: weight = 1 + |column of R|
        pivset = set(piv)
        for f in range(n):
            if f in pivset:
                continue
            v = np.zeros(n, dtype=np.uint8)
            v[perm[f]] = 1
            for i, pc in enumerate(piv):
                if R[i, f]:
                    v[perm[pc]] = 1
            w = int(v.sum())
            if best is not None and w >= best[0]:
                continue
            if (code.hx @ v % 2).any():
                continue
            # nontrivial: not in rowspace(hz)
            if im.rank(np.vstack([code.hz, v[None]])) == im.rank(code.hz):
                continue
            best = (w, v)
    return best[0]


def compare_columns(code, typ, R):
    a = im.build_dem(code, typ, R, ibm_faithful=True)
    b = im.build_dem(code, typ, R, ibm_faithful=False)
    sa = set(zip(a["D"], a["L"]))
    sb = set(zip(b["D"], b["L"]))
    sc = im.stim_columns(im.stim_circuit(code, typ, R))
    return dict(code=code.name, typ=typ, R=R, nfaults=a["nfaults"], ncols=len(sa), faithful_eq_reset=sa == sb,
                faithful_eq_stim=sa == sc, n_stim=len(sc), ndet=a["ndet"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--R", type=int, nargs="*", default=[1, 2, 3])
    a = ap.parse_args()
    res = {}
    for name in ("gross", "bb108"):
        code = im.Code(name)
        dw = min_logical_weight_witness(code)
        res[name] = dict(n=code.n, k=code.k, k_expected=code.k_exp, d_published=code.d_pub,
                         min_weight_found_by_info_set=dw, schedule=check_schedule(code),
                         columns=[compare_columns(code, t, R) for t in ("X", "Z") for R in a.R])
        print(json.dumps(res[name]), flush=True)
    Path(ROOT / "results/E-037-ibm-cert").mkdir(parents=True, exist_ok=True)
    (ROOT / "results/E-037-ibm-cert/structure.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
