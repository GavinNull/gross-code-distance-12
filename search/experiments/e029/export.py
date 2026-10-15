"""E-029: write ccsearch instances (own code).

  dem   CIRCUIT_JSON TASK BASIS R OUT   evaluator public entry: build_circuits + add_noise(sd6, 1e-3), stim DEM
                                        (decompose_errors=False); symmetry = translations found on the DEM itself
  ibm72 BASIS R OUT                     IBM depth-8 schedule on [[72,12,6]] (baselines.schedule.ibm_depth8)
  stim  STIM_FILE OUT                   any stim circuit (no symmetry)
  ext   CIRCUIT_JSON BASIS OUT          extended code built here from the circuit's per-check CNOT orders
                                        (data columns + every proper suffix of the hook-spreading checks, merged by
                                        image); symmetry = translations preserving the column set

Instance format: see ccsearch.c.  Also writes OUT.meta.json (column descriptions, group, checks).

Symmetry check (DEM): a translation t of the check torus acts on detectors (check index, round, type) -> (t(check),
round, type).  t is accepted iff every mechanism's detector set maps onto the detector set of a mechanism (a column
permutation P) AND rank[D;L] = rank[D;L P] = rank[D;L;L P] over GF(2) (so ker[D;L] and ker D are P-invariant:
zero syndrome and nontrivial observable are both preserved).
"""
import json
import sys
from pathlib import Path

import numpy as np
import stim

ROOT = Path(__file__).resolve().parents[3]
for p in (str(ROOT), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from evaluators.candidate import build_circuits, parse_schedule  # noqa: E402
from evaluators.noise import add_noise  # noqa: E402
from evaluators.tasks import build_code, get_task  # noqa: E402

LM = {"gross-dcirc": (12, 6), "bb72-dcirc": (6, 6)}


def gf2_rank(M):
    M = (np.asarray(M, np.uint8) % 2).copy()
    r = 0
    rows, cols = M.shape
    for c in range(cols):
        piv = np.nonzero(M[r:, c])[0]
        if len(piv) == 0:
            continue
        p = r + piv[0]
        if p != r:
            M[[r, p]] = M[[p, r]]
        nz = np.nonzero(M[:, c])[0]
        nz = nz[nz != r]
        M[nz] ^= M[r]
        r += 1
        if r == rows:
            break
    return r


def dem_columns(circ: stim.Circuit):
    dem = circ.detector_error_model(decompose_errors=False)
    cols = []
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        d, o = set(), set()
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                d ^= {t.val}
            elif t.is_logical_observable_id():
                o ^= {t.val}
        cols.append((tuple(sorted(d)), tuple(sorted(o))))
    return dem, cols


def translations_dem(dem, cols, l, m):
    co = dem.get_detector_coordinates()
    key = {tuple(v): k for k, v in co.items()}
    assert len(key) == dem.num_detectors
    index = {}
    for j, (d, o) in enumerate(cols):
        assert d not in index or not d, ("duplicate detector set", d)
        index[d] = j
    nd, no, nc = dem.num_detectors, dem.num_observables, len(cols)
    D = np.zeros((nd, nc), np.uint8)
    Lm = np.zeros((no, nc), np.uint8)
    for j, (d, o) in enumerate(cols):
        D[list(d), j] = 1
        Lm[list(o), j] = 1
    base = gf2_rank(np.vstack([D, Lm]))
    group = []
    for a in range(l):
        for b in range(m):
            def tdet(x):
                c = co[x]
                i = int(c[0]); xx, yy = divmod(i, m)
                return key[tuple([float(((xx + a) % l) * m + (yy + b) % m)] + list(c[1:]))]
            perm = []
            ok = True
            for d, o in cols:
                if not d:
                    perm.append(None); continue
                img = tuple(sorted(tdet(x) for x in d))
                if img not in index:
                    ok = False; break
                perm.append(index[img])
            if not ok:
                continue
            if any(p is None for p in perm):
                ok = all((p is None) == (not cols[j][0]) for j, p in enumerate(perm))
                zero = [j for j, p in enumerate(perm) if p is None]
                assert all(not cols[j][1] for j in zero), "weight-1 logical"
                perm = [j if p is None else p for j, p in enumerate(perm)]
            assert sorted(perm) == list(range(nc))
            LP = Lm[:, perm]          # L x' for x'_{perm[j]} = x_j
            r1 = gf2_rank(np.vstack([D, LP]))
            r2 = gf2_rank(np.vstack([D, Lm, LP]))
            if r1 == base and r2 == base:
                group.append(((a, b), perm))
            else:
                print("translation", (a, b), "maps detector sets but not logical classes", base, r1, r2)
    return group, base


def orbits_from(group, nc):
    seen = [-1] * nc
    orbs = []
    for c in range(nc):
        if seen[c] >= 0:
            continue
        orb = sorted({p[c] for _, p in group})
        for x in orb:
            seen[x] = len(orbs)
        orbs.append(orb)
    return orbs


def write_inst(out, nr, nobs, cols, orbs, meta):
    """cols: list of (rows tuple, obs tuple)"""
    with open(out, "w") as f:
        f.write(f"{nr} {len(cols)} {nobs} {len(orbs)}\n")
        for d, o in cols:
            f.write(f"{len(d)} {' '.join(map(str, d))} {len(o)} {' '.join(map(str, o))}\n")
        for orb in orbs:
            f.write(f"{len(orb)} {' '.join(map(str, orb))}\n")
    meta["num_rows"], meta["num_cols"], meta["num_obs"], meta["num_orbits"] = nr, len(cols), nobs, len(orbs)
    meta["orbit_sizes"] = sorted({len(o) for o in orbs})
    Path(str(out) + ".meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps({k: v for k, v in meta.items() if k not in ("columns",)})[:600])


def dem_case(spec, code, task, basis, R, out, name):
    circ = add_noise(build_circuits(spec.canonical(), code, R)[basis], "sd6", 1e-3)
    dem, cols = dem_columns(circ)
    l, m = LM[task]
    group, rank = translations_dem(dem, cols, l, m)
    keep = [j for j, (d, o) in enumerate(cols) if d or o]
    # drop columns with no detector and no observable (never part of a minimal solution); renumber
    ren = {j: i for i, j in enumerate(keep)}
    cols2 = [cols[j] for j in keep]
    group2 = [(t, [ren[p[j]] for j in keep]) for t, p in group]
    orbs = orbits_from(group2, len(cols2))
    meta = dict(case=name, task=task, basis=basis, R=R, noise="sd6", dem_terms=len(cols), dropped_empty=len(cols) - len(keep),
                group=[t for t, _ in group], group_order=len(group), rank_DL=rank,
                max_col_weight=max(len(d) for d, _ in cols2), detectors=dem.num_detectors, observables=dem.num_observables)
    write_inst(out, dem.num_detectors, dem.num_observables, cols2, orbs, meta)


def ext_case(spec, code, basis, out):
    H, L = (np.asarray(code.HZ, np.uint8) % 2, np.asarray(code.LZ, np.uint8) % 2) if basis == "Z" else \
        (np.asarray(code.HX, np.uint8) % 2, np.asarray(code.LX, np.uint8) % 2)
    P = spec.period
    checks = spec.x_checks if basis == "Z" else spec.z_checks   # hook-spreading checks for this basis
    orders = [[col for _, col in sorted(((t - c.prep) % P, col) for col, t in c.cnots)] for c in checks]
    n = H.shape[1]
    sups = [(j,) for j in range(n)] + [tuple(sorted(o[k:])) for o in orders for k in range(1, 6)]
    keys, cols, supl = {}, [], []
    for s in sups:
        v = np.zeros(n, np.uint8); v[list(s)] = 1
        hb, lb = (H @ v) % 2, (L @ v) % 2
        if not hb.any() and not lb.any():
            continue
        k = hb.tobytes() + lb.tobytes()
        if k in keys:
            continue
        keys[k] = len(cols)
        cols.append((tuple(np.nonzero(hb)[0].tolist()), tuple(np.nonzero(lb)[0].tolist())))
        supl.append(list(s))
    # translations of the data torus (l=12, m=6): qubit q = blk*72 + 6x + y
    group = []
    for a in range(12):
        for b in range(6):
            def tq(q):
                blk, i = divmod(q, 72); x, y = divmod(i, 6)
                return blk * 72 + ((x + a) % 12) * 6 + (y + b) % 6
            perm = []
            for s in supl:
                v = np.zeros(n, np.uint8); v[[tq(q) for q in s]] = 1
                k = ((H @ v) % 2).tobytes() + ((L @ v) % 2).tobytes()
                if k not in keys:
                    break
                perm.append(keys[k])
            else:
                # the code itself is translation invariant (BB); logical classes preserved since stabilisers and
                # ker H are; checked here anyway on the column matrices
                D = np.array([[1 if r in d else 0 for d, _ in cols] for r in range(H.shape[0])], np.uint8)
                Lm = np.array([[1 if r in o else 0 for _, o in cols] for r in range(L.shape[0])], np.uint8)
                LP = Lm[:, perm]
                base = gf2_rank(np.vstack([D, Lm]))
                if gf2_rank(np.vstack([D, LP])) == base == gf2_rank(np.vstack([D, Lm, LP])):
                    group.append(((a, b), perm))
    orbs = orbits_from(group, len(cols))
    meta = dict(case="ext", basis=basis, group=[t for t, _ in group], group_order=len(group),
                columns=[dict(support=s, H=list(d), L=list(o)) for s, (d, o) in zip(supl, cols)],
                weight_hist={str(w): sum(1 for d, _ in cols if len(d) == w) for w in sorted({len(d) for d, _ in cols})})
    write_inst(out, H.shape[0], L.shape[0], cols, orbs, meta)


def main(argv):
    cmd = argv[0]
    if cmd == "dem":
        path, task, basis, R, out = argv[1], argv[2], argv[3], int(argv[4]), argv[5]
        code, _ = build_code(get_task(task), None)
        spec = parse_schedule(json.load(open(path)))
        dem_case(spec, code, task, basis, R, out, Path(path).stem)
    elif cmd == "ibm72":
        basis, R, out = argv[1], int(argv[2]), argv[3]
        code, _ = build_code(get_task("bb72-dcirc"), None)
        from baselines.bb_code import BBCode
        from baselines.schedule import ibm_depth8
        from schedule_helpers import from_baseline
        bb = BBCode(6, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"])
        assert (bb.HX == np.asarray(code.HX)).all() and (bb.HZ == np.asarray(code.HZ)).all()
        dem_case(from_baseline(ibm_depth8(bb)), code, "bb72-dcirc", basis, R, out, "ibm_bb72")
    elif cmd == "stim":
        circ = stim.Circuit.from_file(argv[1])
        dem, cols = dem_columns(circ)
        keep = list(dict.fromkeys(c for c in cols if c[0] or c[1]))   # identical (detectors, observables) merged
        meta = dict(case="stim", file=argv[1], dem_terms=len(cols), merged_duplicates=len([c for c in cols if c[0] or c[1]]) - len(keep),
                    detectors=dem.num_detectors,
                    observables=dem.num_observables, group_order=1)
        write_inst(argv[2], dem.num_detectors, dem.num_observables, keep, [[j] for j in range(len(keep))], meta)
    elif cmd == "ext":
        path, basis, out = argv[1], argv[2], argv[3]
        code, _ = build_code(get_task("gross-dcirc"), None)
        ext_case(parse_schedule(json.load(open(path))), code, basis, out)


if __name__ == "__main__":
    main(sys.argv[1:])
