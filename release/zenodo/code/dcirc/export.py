"""Write ccsearch instances: the full SD6 detector error model of a memory circuit, with its translation symmetry.

    python code/dcirc/export.py dem CIRCUIT BASIS R OUT     CIRCUIT: A, B, C, fig12, u11, u11_control_p10 (gross code) or
                                                            c11, c12, c13, c16, u16, s16
                                                            ([[90,8,10]]); the circuit of data/circuits/, the
                                                            template of code/gross12/schedule.py, SD6 noise
    python code/dcirc/export.py stim STIM_FILE OUT          any stim circuit (no symmetry; identical DEM terms merged)

The DEM is built by stim (detector_error_model(decompose_errors=False)); each column of the instance is one DEM
mechanism (terms with neither a detector nor an observable are dropped).  Faults are counted as DEM mechanisms.

Symmetry (DEM): a translation t of the check torus (12 x 6 for the gross code, 15 x 3 for [[90,8,10]]) acts on
detectors (check index, round, type) -> (t(check), round, type).  t is accepted iff every mechanism's detector set
maps onto the detector set of a mechanism (a column permutation P) AND rank[D;L] = rank[D;L P] = rank[D;L;L P] over
GF(2), so that ker D and ker [D;L] are P-invariant: "undetected" and "flips an observable" are both preserved.  The
accepted translations give the column orbits written into the instance (root cases of ccsearch).
Also writes OUT.meta.json (sizes, accepted group, orbit sizes).  Instance format: see ccsearch.c.
"""
import json
import sys
from pathlib import Path

import numpy as np
import stim

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gross12.code import gf2_rank                      # noqa: E402
from gross12.noise import add_sd6                      # noqa: E402
from gross12.schedule import build_circuits            # noqa: E402

GROSS = ("A", "B", "C", "fig12")
BB90 = ("c16", "u16", "s16")


def load(name):
    from p11 import common as P
    if name in P.CIRCUITS_P11 and name not in BB90:     # u11 and its controls, c11, c12, c13
        fam = P.family_of(name)
        return P.load_code(fam), P.circuit(name), (P.FAMILY[fam]["l"], P.FAMILY[fam]["m"])
    if name in BB90:
        from bb90 import bbcode, ext
        return bbcode.load_code(), ext.circuit(name), (15, 3)
    from common_cli import circuit, load_code
    return load_code(), circuit(name), (12, 6)


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
                xx, yy = divmod(int(c[0]), m)
                return key[tuple([float(((xx + a) % l) * m + (yy + b) % m)] + list(c[1:]))]
            perm = []
            ok = True
            for d, o in cols:
                if not d:
                    perm.append(None)
                    continue
                img = tuple(sorted(tdet(x) for x in d))
                if img not in index:
                    ok = False
                    break
                perm.append(index[img])
            if not ok:
                continue
            if any(p is None for p in perm):
                zero = [j for j, p in enumerate(perm) if p is None]
                assert all(not cols[j][1] for j in zero), "weight-1 logical"
                perm = [j if p is None else p for j, p in enumerate(perm)]
            assert sorted(perm) == list(range(nc))
            LP = Lm[:, perm]
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
    with open(out, "w") as f:
        f.write(f"{nr} {len(cols)} {nobs} {len(orbs)}\n")
        for d, o in cols:
            f.write(f"{len(d)} {' '.join(map(str, d))} {len(o)} {' '.join(map(str, o))}\n")
        for orb in orbs:
            f.write(f"{len(orb)} {' '.join(map(str, orb))}\n")
    meta["num_rows"], meta["num_cols"], meta["num_obs"], meta["num_orbits"] = nr, len(cols), nobs, len(orbs)
    meta["orbit_sizes"] = sorted({len(o) for o in orbs})
    Path(str(out) + ".meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta)[:600])


def dem_case(name, basis, R, out):
    code, spec, (l, m) = load(name)
    circ = add_sd6(build_circuits(spec.canonical(), code, R)[basis])
    dem, cols = dem_columns(circ)
    group, rank = translations_dem(dem, cols, l, m)
    keep = [j for j, (d, o) in enumerate(cols) if d or o]
    ren = {j: i for i, j in enumerate(keep)}
    cols2 = [cols[j] for j in keep]
    group2 = [(t, [ren[p[j]] for j in keep]) for t, p in group]
    orbs = orbits_from(group2, len(cols2))
    meta = dict(circuit=name, basis=basis, R=R, noise="SD6", dem_terms=len(cols), dropped_empty=len(cols) - len(keep),
                group=[t for t, _ in group], group_order=len(group), rank_DL=rank,
                max_col_weight=max(len(d) for d, _ in cols2), detectors=dem.num_detectors,
                observables=dem.num_observables)
    write_inst(out, dem.num_detectors, dem.num_observables, cols2, orbs, meta)


def main(argv):
    if argv[0] == "dem":
        dem_case(argv[1], argv[2], int(argv[3]), argv[4])
    elif argv[0] == "stim":
        circ = stim.Circuit.from_file(argv[1])
        dem, cols = dem_columns(circ)
        nz = [c for c in cols if c[0] or c[1]]
        keep = list(dict.fromkeys(nz))       # identical (detectors, observables) merged: a pair cancels
        meta = dict(circuit="stim file", dem_terms=len(cols), merged_duplicates=len(nz) - len(keep),
                    detectors=dem.num_detectors, observables=dem.num_observables, group_order=1)
        write_inst(argv[2], dem.num_detectors, dem.num_observables, keep, [[j] for j in range(len(keep))], meta)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
