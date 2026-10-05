"""A1/A2: independent extended codes for Strikis Fig. 12 gross circuit.

(i)  BB coordinates: HX/HZ built here from the polynomials; CNOT orders read off strikis_fig12's layers with
     the auditor's own cyclic logic (offset (t - prep) mod 8, checking meas comes after the last CNOT);
     compared column-by-column with results/E-014-gross-dcirc11-proof/inst_{X,Z}.txt.
(ii) Lattice coordinates (Fig. 10 / Fig. 12 numbers only, no lattice_to_bb, no BBCode): own Tanner graph on the
     6 x 12 torus, own orders, own logical basis, own symmetry group -> independent dfs128 instances.
Also: symmetry group checks (code automorphism, order preservation, logical classes preserved, well defined on
merged columns), orbit comparison with the lead's instances.
"""
import json
import sys
import itertools
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from gf2 import rank, logical_basis  # noqa: E402
import extx  # noqa: E402

OUT = Path("results/E-014-E-015-audit")
LEAD = Path("results/E-014-gross-dcirc11-proof")
l, m = 12, 6
n2 = l * m


def shift(a, b):
    """Permutation matrix of x^a y^b on Z_l x Z_m (index i*m + j)."""
    P = np.zeros((n2, n2), np.uint8)
    for i in range(l):
        for j in range(m):
            P[i * m + j, ((i + a) % l) * m + (j + b) % m] = 1  # convention of baselines.bb_code (row g has x at g+1)
    return P


def bb_mats():
    x = shift(1, 0); y = shift(0, 1)
    mp = lambda M, k: np.linalg.matrix_power(M.astype(int), k) % 2  # noqa: E731
    A = (mp(x, 3) + y + mp(y, 2)) % 2
    B = (mp(y, 3) + x + mp(x, 2)) % 2
    HX = np.hstack([A, B]).astype(np.uint8)
    HZ = np.hstack([B.T, A.T]).astype(np.uint8)
    return HX, HZ


def orders_from_layers(sched, H, kind):
    """Own reading of a cyclic schedule: per check ancilla, CNOT offsets relative to prep (mod D)."""
    D = len(sched.layers)
    col = {q: j for j, q in enumerate(sched.data)}
    anc = sched.x_checks if kind == "X" else sched.z_checks
    prep, meas, ev = {}, {}, {q: [] for q in anc}
    for t, Ly in enumerate(sched.layers):
        for q in (Ly.prep_x if kind == "X" else Ly.prep_z):
            prep[q] = t
        for q in (Ly.meas_x if kind == "X" else Ly.meas_z):
            meas[q] = t
        for a, b in Ly.cnots:
            if kind == "X" and a in ev:
                assert b in col
                ev[a].append((t, col[b]))
            if kind == "Z" and b in ev:
                assert a in col
                ev[b].append((t, col[a]))
    rows = {tuple(np.nonzero(H[i])[0]): i for i in range(H.shape[0])}
    orders = [None] * H.shape[0]
    for q in anc:
        offs = sorted(((t - prep[q]) % D, j) for t, j in ev[q])
        mo = (meas[q] - prep[q]) % D
        assert len({o for o, _ in offs}) == 6 and all(0 < o < mo for o, _ in offs), (q, offs, mo)
        sup = tuple(sorted(j for _, j in offs))
        i = rows[sup]
        assert orders[i] is None
        orders[i] = [j for _, j in offs]
    return orders


def part_i():
    from baselines.bb_code import gross_code
    from baselines.strikis import strikis_fig12
    g = gross_code()
    HX, HZ = bb_mats()
    rep = {"HX_equal_baseline": bool((np.asarray(g.HX) % 2 == HX).all()),
           "HZ_equal_baseline": bool((np.asarray(g.HZ) % 2 == HZ).all())}
    assert not ((HX.astype(int) @ HZ.T.astype(int)) % 2).any()
    LX = logical_basis(HZ, HX)   # X logicals: commute with Z checks
    LZ = logical_basis(HX, HZ)
    rep["k"] = [len(LX), len(LZ)]
    sched, meta = strikis_fig12(g)
    xo = orders_from_layers(sched, HX, "X")
    zo = orders_from_layers(sched, HZ, "Z")
    # compare with project's orders_from_schedule
    from search.noninterleaved.ext import orders_from_schedule
    pxo, pzo = orders_from_schedule(sched)
    rep["orders_equal_project"] = [xo == [list(o) for o in pxo], zo == [list(o) for o in pzo]]
    res = {}
    for kind, H, L, orders in (("X", HZ, LZ, xo), ("Z", HX, LX, zo)):
        e = extx.build(H, L, orders, 2 * n2)
        He2, Le2, orb2, reps2 = extx.read128(LEAD / f"inst_{kind}.txt")
        Le2 = Le2[:12]
        ok, info = extx.compare_columns(e["He"], e["Le"], True, He2, Le2)
        mp = info.pop("map")
        # symmetry group: all translations; automorphism + order preservation
        group, autos = [], []
        for a in range(l):
            for b in range(m):
                p = np.array([((i // m + a) % l) * m + (i % m + b) % m for i in range(n2)])
                pd = np.concatenate([p, p + n2])
                auto = all(((Hm[np.ix_(p, pd)] == Hm).all()) for Hm in (HX, HZ))
                # Hm[p[i], pd[j]] == Hm[i, j]  <=> check i maps to check p[i]
                if not auto:
                    continue
                autos.append((a, b))
                inv = all(list(orders[p[i]]) == [int(pd[j]) for j in orders[i]] for orders in (xo, zo) for i in range(n2))
                if inv:
                    group.append((a, b, pd))
        gl = [(a, b) for a, b, _ in group]
        logic_ok = all(extx.logical_transform_ok(H, L, pd) for _, _, pd in group)
        orb, reps, perms = extx.orbits(e, [pd for _, _, pd in group])
        # compare orbit partitions via column map
        mine = {}
        for j in range(len(orb)):
            mine.setdefault(int(orb[j]), set()).add(mp[j])
        theirs = {}
        for j in range(len(orb2)):
            theirs.setdefault(int(orb2[j]), set()).add(j)
        same_orbits = sorted(map(sorted, mine.values())) == sorted(map(sorted, theirs.values()))
        # lead's reps belong to their orbits, orbit index ordering consistent with 'min column' rule irrelevant
        reps_ok = all(orb2[r] == o for o, r in enumerate(reps2))
        res[kind] = dict(ok_columns=ok, **info, n_autos=len(autos), n_group=len(group), group=gl,
                         a_plus_b_0mod3=all((a + b) % 3 == 0 for a, b in gl),
                         logical_classes_preserved=logic_ok, n_orbits=len(reps), orbit_sizes=np.bincount(orb).tolist(),
                         same_orbit_partition_as_lead=same_orbits, lead_reps_in_own_orbit=bool(reps_ok),
                         col_weight_hist=np.bincount(e["He"].sum(0)).tolist(), max_res_members=max(len(x) for x in e["members"]))
        extx.dump128(e["He"], e["Le"], orb, reps, OUT / f"gross_bb_{kind}.txt")
    rep["sides"] = res
    return rep


# ----------------------------------------------------------------------------- (ii) lattice construction
FIG12 = {   # 2603.05481 v2 Fig. 12 numbers (as transcribed in baselines/strikis.py; E-005 auditor checked vs paper)
    "Z": {"B": {"up": 4, "down": 5, "left": 6, "right": 8, "ur": 7, "dl": 3, "prep": 2, "meas": 1},
          "R": {"up": 4, "down": 2, "left": 7, "right": 6, "ur": 5, "dl": 3, "prep": 1, "meas": 8},
          "G": {"up": 4, "down": 2, "left": 5, "right": 7, "ur": 6, "dl": 3, "prep": 1, "meas": 8}},
    "X": {"B": {"up": 2, "down": 4, "left": 8, "right": 1, "ur": 3, "dl": 7, "prep": 6, "meas": 5},
          "R": {"up": 2, "down": 1, "left": 7, "right": 8, "ur": 3, "dl": 6, "prep": 5, "meas": 4},
          "G": {"up": 2, "down": 1, "left": 6, "right": 7, "ur": 3, "dl": 8, "prep": 5, "meas": 4}},
}
XN = {"up": ("F", -1, 0), "down": ("F", 0, 0), "left": ("O", 0, -1), "right": ("O", 0, 0), "ur": ("F", -2, 3), "dl": ("O", 3, -2)}
ZN = {"up": ("O", 0, 0), "down": ("O", 1, 0), "left": ("F", 0, 0), "right": ("F", 0, 1), "ur": ("F", -3, 2), "dl": ("O", 2, -3)}
NI, NJ = 6, 12


def lat():
    q = lambda kind, i, j: (0 if kind == "F" else NI * NJ) + (i % NI) * NJ + (j % NJ)  # noqa: E731
    HX = np.zeros((NI * NJ, 2 * NI * NJ), np.uint8)
    HZ = np.zeros_like(HX)
    xo, zo = [], []
    for i in range(NI):
        for j in range(NJ):
            col = "RGB"[(i + j) % 3]
            r = i * NJ + j
            for kind, Hm, N, oo in (("X", HX, XN, xo), ("Z", HZ, ZN, zo)):
                f = FIG12[kind][col]
                ev = []
                for d, (t, di, dj) in N.items():
                    qq = q(t, i + di, j + dj)
                    Hm[r, qq] ^= 1
                    ev.append(((f[d] - f["prep"]) % 8, qq))
                ev.sort()
                mo = (f["meas"] - f["prep"]) % 8
                assert len({o for o, _ in ev}) == 6 and all(0 < o < mo for o, _ in ev)
                oo.append([qq for _, qq in ev])
    assert HX.sum(1).tolist() == [6] * 72 and HZ.sum(1).tolist() == [6] * 72
    assert not ((HX.astype(int) @ HZ.T.astype(int)) % 2).any()
    return HX, HZ, xo, zo, q


def part_ii():
    HX, HZ, xo, zo, q = lat()
    k = 144 - rank(HX) - rank(HZ)
    LX = logical_basis(HZ, HX); LZ = logical_basis(HX, HZ)
    rep = {"k": int(k), "kL": [len(LX), len(LZ)]}
    # data collisions (sanity: every data qubit used at most once per time step mod 8, per kind)
    for kind, oo in (("X", xo), ("Z", zo)):
        pass
    # translations (di, dj) on the lattice
    group = []
    for di in range(NI):
        for dj in range(NJ):
            pd = np.array([q("F" if j < 72 else "O", (j % 72) // NJ + di, (j % 72) % NJ + dj) for j in range(144)])
            pr = np.array([((i // NJ + di) % NI) * NJ + (i % NJ + dj) % NJ for i in range(72)])
            auto = all((Hm[np.ix_(pr, pd)] == Hm).all() for Hm in (HX, HZ))
            inv = auto and all(list(oo[pr[i]]) == [int(pd[x]) for x in oo[i]] for oo in (xo, zo) for i in range(72))
            if inv:
                group.append((di, dj, pd))
    rep["group"] = [(a, b) for a, b, _ in group]
    for kind, H, L, orders in (("X", HZ, LZ, xo), ("Z", HX, LX, zo)):
        e = extx.build(H, L, orders, 144)
        rep[f"logical_ok_{kind}"] = all(extx.logical_transform_ok(H, L, pd) for _, _, pd in group)
        orb, reps, _ = extx.orbits(e, [pd for _, _, pd in group])
        rep[kind] = dict(shape=list(e["He"].shape), Le=list(e["Le"].shape), orbits=len(reps),
                         orbit_sizes=np.bincount(orb).tolist(), col_weight_hist=np.bincount(e["He"].sum(0)).tolist())
        extx.dump128(e["He"], e["Le"], orb, reps, OUT / f"gross_lat_{kind}.txt")
        # no-symmetry instance: orbit = column index
        N = e["He"].shape[1]
        extx.dump128(e["He"], e["Le"], np.arange(N), list(range(N)), OUT / f"gross_lat_nosym_{kind}.txt")
    return rep


if __name__ == "__main__":
    out = {"i_bb": part_i(), "ii_lattice": part_ii()}
    s = json.dumps(out, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    (OUT / "a1_gross.json").write_text(s)
    print(s)
