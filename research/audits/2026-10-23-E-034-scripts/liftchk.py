"""Auditor: instance-level comparison of the E-031 lift CNF (liftcert.setup + liftcert.add_instance, i.e. exactly
what goes into the DRAT batches) with an independent lift encoder.

Independent side: circuit + SD6 DEM from the earlier auditors' libraries (E-030 audit mylib.py for [[90]], E-032
audit alib32.py for gross; neither imports search/ or evaluators/), own image keys (own H, own logical basis),
own grouping of DEM terms by the column whose SUPPORT has that image (Table I re-asserted here), own CNF
(at-least-one + pairwise at-most-one per column, the zero-term case solved separately as "exactly one zero term",
XOR = 0 on every touched detector by Tseitin chains of length 3), solved with pysat Minisat22.
The E-031 instance is solved from its own clause list with pysat Cadical153.

    PYTHONPATH=.:tests uv run python liftchk.py FAMILY SPEC XO ZO BASIS R  [--n K | --all] [--seed s] [--tag T]

Also checks: liftcert.setup's instance list == the replica used here; the lists used by the lift (E-028 / E-032
pickles) == the release lists (bb90: 585 / 16830) or the E-031 u11 export (u11), via column supports.
Output: results/E-034-audit/lift/liftchk.jsonl
"""
import importlib
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
for p in (ROOT, ROOT / "tests", ROOT / "search/experiments/e031", ROOT / "search/experiments/e027"):
    sys.path.insert(0, str(p))
sys.path.insert(0, str(HERE))
from pysat.solvers import Cadical153, Minisat22  # noqa: E402


def their_side(family, spec_path, xo, zo, R, basis):
    import liftcert
    from evaluators.candidate import parse_schedule
    C = importlib.import_module(f"search.experiments.{family}.common")
    L = importlib.import_module(f"search.experiments.{family}.lift")
    cg = importlib.import_module(f"search.experiments.{family}.cegar")
    D = 8 if family == "e028" else 10
    spec = parse_schedule(json.load(open(spec_path))).canonical()
    lo = L.label_orders(spec)
    k = L.KIND_OF_BASIS[basis]
    E = C.ext_general(k, lo[k], group=[(0, 0)])
    o = xo if k == "X" else zo
    lA, _ = cg.load_class(k, "all", o, D)
    lB, _ = cg.load_class(k, "all", o, D + 1)
    sA, _ = L.reindex(E, lA)
    sB, _ = L.reindex(E, lB)
    insts, meta = liftcert.setup(family, spec_path, xo, zo, R, basis)
    assert len(insts) == len(sA) + len(sB)
    return E, sA, sB, insts, meta, D, liftcert


def solve_theirs(liftcert, inst):
    from lift_cnf import Builder
    b = Builder()
    liftcert.add_instance(b, inst, [])
    with Cadical153(bootstrap_with=b.clauses) as s:
        return s.solve()


def solve_mine(groups, zeros):
    """groups: list of lists of detector masks (one list per column); zeros: None or list of masks (exactly one)."""
    def run(gs):
        cl, top, var_det = [], 0, {}
        for g in gs:
            vs = []
            for dm in g:
                top += 1; vs.append(top)
                x = dm
                while x:
                    low = x & -x
                    var_det.setdefault(low.bit_length() - 1, []).append(top)
                    x ^= low
            cl.append(vs)
            cl += [[-vs[a], -vs[b]] for a in range(len(vs)) for b in range(a + 1, len(vs))]
        for det, vs in var_det.items():
            cur = vs[0]
            for v in vs[1:]:
                top += 1; y = top
                cl += [[-cur, -v, -y], [cur, v, -y], [cur, -v, y], [-cur, v, y]]
                cur = y
            cl.append([-cur])
        with Minisat22(bootstrap_with=cl) as s:
            return s.solve()
    if zeros is None:
        return run(groups)
    return run(groups) or (bool(zeros) and run(groups + [zeros]))


def main():
    a = sys.argv[1:]
    family, spec_path, xo, zo, basis, R = a[:6]
    R = int(R)
    nsamp = None if "--all" in a else int(a[a.index("--n") + 1]) if "--n" in a else 200
    seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 0
    t0 = time.time()
    E, sA, sB, insts, meta, D, liftcert = their_side(family, spec_path, xo, zo, R, basis)
    sups = [E["col_sups"][j][0] for j in range(E["N"])]
    # own library
    if family == "e028":
        sys.path.insert(0, str(ROOT / "research/audits/2026-10-22-E-030-scripts"))
        import mylib as lib
        HX, HZ, LX, LZ = lib.code_with_logicals()
        circ = lib.memory_circuit(lib.load_spec(spec_path), basis, R, 1e-3, 1.0, image_obs=True)
        terms = [(d, o) for d, o, _ in lib.dem_terms(circ)[0]]
    else:
        sys.path.insert(0, str(ROOT / "research/audits/2026-10-22-E-032-scripts"))
        import alib32 as lib
        HX, HZ, LX, LZ = lib.code()
        circ = lib.memory_circuit(lib.load_spec(spec_path), basis, R, image_obs=True)
        terms = lib.dem_terms(circ)[0]
    H, Lg = (HZ, LZ) if basis == "Z" else (HX, LX)
    nH, k = H.shape[0], Lg.shape[0]
    n = H.shape[1]

    def okey(S):
        v = np.zeros(n, np.uint8); v[list(S)] = 1
        return tuple(int(x) for x in (H.astype(int) @ v) % 2) + tuple(int(x) for x in (Lg.astype(int) @ v) % 2)
    col_of = {}
    for j, S in enumerate(sups):
        kk = okey(S)
        assert kk not in col_of
        col_of[kk] = j
    own, zeros = {}, []
    bad = 0
    for dm, om in terms:
        logic = om & ((1 << k) - 1)
        img = tuple((om >> (k + r)) & 1 for r in range(nH + k))
        assert logic == sum(img[nH + r] << r for r in range(k)), "observable != L part"
        if not any(img):
            if dm:
                zeros.append(dm)
            continue
        if img not in col_of:
            bad += 1; continue
        own.setdefault(col_of[img], set()).add(dm)
    assert bad == 0, f"{bad} terms with an image that is not one column (Table I)"
    assert len(own) == E["N"]
    res = {"family": family, "spec": Path(spec_path).stem, "basis": basis, "R": R, "nA": len(sA), "nB": len(sB),
           "own_terms": len(terms), "own_zero_terms": len(set(zeros)), "their_zero_terms": meta["zero_terms"],
           "own_detectors": circ.num_detectors, "their_detectors": meta.get("detectors")}
    # lists vs release / export
    from alib import DATA, ext_code
    if family == "e028":
        Em = ext_code("bb90", DATA / "circuits/bb90_c16.json", basis, DATA / f"extended_code/bb90_extended_code_{basis}_memory.json")
        rel = {w: {tuple(sorted(e["columns"])) for e in json.load(open(DATA / f"logicals/bb90_weight{w}_logicals_{basis}_memory.json"))["logicals"]} for w in (8, 9)}
    else:
        Em = ext_code("gross", ROOT / "search/experiments/e032/u11_spec.json", basis, None)
        kind = "X" if basis == "Z" else "Z"
        U = ROOT / "results/E-031-xor-certificates/u11"
        rel = {w: {tuple(sorted(e["columns"])) for e in json.load(open(U / f"u11_{kind}_w{w}.json"))["logicals"]} for w in (10, 11)}
    if Path(spec_path).stem in ("c16_spec", "u11_spec", "u16_spec"):
        mj = [Em["keys"][Em["key"](S)] for S in sups]
        res["lists_equal_reference"] = ({tuple(sorted(mj[j] for j in S)) for S in sA} == rel[D] and
                                        {tuple(sorted(mj[j] for j in S)) for S in sB} == rel[D + 1])
    # instances
    idx = list(range(len(insts)))
    if nsamp is not None and nsamp < len(idx):
        rnd = random.Random(seed)
        na = min(len(sA), nsamp // 2)
        idx = sorted(rnd.sample(range(len(sA)), na) + rnd.sample(range(len(sA), len(insts)), nsamp - na))
    agree = sat_t = sat_m = shape_ok = 0
    dis = []
    for i in idx:
        S = sA[i] if i < len(sA) else sB[i - len(sA)]
        gs_t, z_t = insts[i]
        gs_m = [sorted(own[j]) for j in S]
        U = 0
        for g in gs_m:
            for dm in g:
                U |= dm
        z_m = sorted({z for z in zeros if z & ~U == 0}) if i < len(sA) else None
        shape_ok += (sorted(len(set(g)) for g in gs_t) == sorted(len(g) for g in gs_m)
                     and (z_m is None and not z_t or z_m is not None and len(set(z_t)) == len(z_m)))
        rt = solve_theirs(liftcert, insts[i])
        rm = solve_mine(gs_m, z_m)
        sat_t += rt; sat_m += rm
        if rt == rm:
            agree += 1
        else:
            dis.append(i)
    res.update(instances=len(idx), shape_equal=shape_ok, decisions_agree=agree, sat_theirs=sat_t, sat_mine=sat_m,
               disagree=dis[:20], sec=round(time.time() - t0, 1))
    res["ok"] = agree == len(idx) and shape_ok == len(idx) and res.get("lists_equal_reference", True)
    print(json.dumps(res), flush=True)
    out = ROOT / "results/E-034-audit/lift"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "liftchk.jsonl", "a") as f:
        f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
