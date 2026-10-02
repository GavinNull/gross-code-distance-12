"""Tests for search/codes (code-family enumeration and cheap screening).  Run: pytest -k codes_search"""
from __future__ import annotations

import numpy as np
import pytest

from search.codes.catalog import IBM_TABLE3, WANG_MUELLER_T2, all_known_codes
from search.codes.constraints import check_constraints, tanner_edges, thickness_le2
from search.codes.construct import (GroupAlgebraCode, bb_code, coprime_bb_code, parse_monomial,
                                    to_baseline_bbcode, two_bga_code)
from search.codes.distance import distance_exact_milp, distance_upper_bound_bposd
from search.codes.enumerate import family_size, general_family, ibm_family
from search.codes.equivalence import canonical_key, canonical_key_abelian, key_to_code
from search.codes.groups import abelian_automorphisms, abelian_group, dihedral_group, iso_to_canonical
from search.codes.schedule import check_schedule, default_schedule


def test_codes_search_parse_monomial():
    assert parse_monomial("1") == (0, 0)
    assert parse_monomial("x^3") == (3, 0)
    assert parse_monomial("y") == (0, 1)
    assert parse_monomial("x^2y^5") == (2, 5)
    assert parse_monomial("x*y^2") == (1, 2)
    with pytest.raises(ValueError):
        parse_monomial("z")


@pytest.mark.parametrize("row", IBM_TABLE3, ids=[r[0] for r in IBM_TABLE3])
def test_codes_search_ibm_table3_nk(row):
    name, l, m, A, B, n, k, d, kind = row
    c = bb_code(l, m, A, B)
    assert (c.n, c.k) == (n, k)
    bb = to_baseline_bbcode(c)
    assert np.array_equal(bb.HX, c.HX) and np.array_equal(bb.HZ, c.HZ)
    if n <= 300:
        css = c.to_css()
        assert css.k == k and not css.check()


def test_codes_search_known_catalog_k():
    for row, c in all_known_codes():
        assert c.k == row[6], row[0]


def test_codes_search_2bga_abelian_equals_bb_and_dihedral_valid():
    G = abelian_group(6, 6)
    a = [3 * 6, 1, 2]          # x^3, y, y^2
    b = [3, 6, 12]             # y^3, x, x^2
    c1 = two_bga_code(G, a, b)
    c2 = bb_code(6, 6, "x^3+y+y^2", "y^3+x+x^2")
    assert np.array_equal(c1.HX, c2.HX) and np.array_equal(c1.HZ, c2.HZ)
    D = dihedral_group(6)
    assert not D.is_abelian
    c = two_bga_code(D, [0, 1, 6 + 2], [0, 3, 6 + 1])
    assert c.family == "2BGA"
    assert not ((c.HX.astype(int) @ c.HZ.T) % 2).any()
    css = c.to_css()
    assert css.k == c.k and not css.check()
    con = check_constraints(c)
    assert con["max_row_weight"] == 6 and con["max_qubit_degree"] == 6


def test_codes_search_fast_k_matches_css():
    rng = np.random.default_rng(1)
    for _ in range(20):
        l, m = int(rng.integers(2, 7)), int(rng.integers(2, 7))
        N = l * m
        if N < 4:
            continue
        a = rng.choice(N, 3, replace=False)
        b = rng.choice(N, 3, replace=False)
        c = GroupAlgebraCode(abelian_group(l, m), a, b, family="BB")
        assert c.k == c.to_css().k


# ------------------------------------------------------------------ equivalence

def test_codes_search_automorphisms_are_automorphisms():
    for d1, d2 in [(1, 12), (2, 4), (3, 3), (6, 6)]:
        auts = abelian_automorphisms(d1, d2)
        G = abelian_group(d1, d2)
        for p in auts[:50]:
            assert (p[G.mul] == G.mul[p][:, p]).all()
    assert len(abelian_automorphisms(1, 12)) == 4          # |Z_12^*|
    assert len(abelian_automorphisms(3, 3)) == 48          # |GL(2,3)|


def test_codes_search_iso_to_canonical_is_hom():
    for l, m in [(3, 5), (6, 4), (10, 3), (12, 6)]:
        phi = iso_to_canonical(l, m)
        G = abelian_group(l, m)
        from search.codes.groups import invariant_factors
        H = abelian_group(*invariant_factors(l, m))
        assert len(set(phi.tolist())) == l * m
        assert (phi[G.mul] == H.mul[phi][:, phi]).all()


def _transform(l, m, a, b, rng):
    """Apply a random element of E1-E3 directly in Z_l x Z_m (no canonical map)."""
    from search.codes.groups import invariant_factors
    G = abelian_group(l, m)
    # automorphisms of Z_l x Z_m: brute force via homomorphism images of x, y
    while True:
        p = (int(rng.integers(l)), int(rng.integers(m)))
        q = (int(rng.integers(l)), int(rng.integers(m)))
        if (l * p[1]) % m or (m * q[0]) % l:
            continue
        I, J = np.divmod(np.arange(l * m), m)
        perm = ((I * p[0] + J * q[0]) % l) * m + (I * p[1] + J * q[1]) % m
        if len(set(perm.tolist())) == l * m:
            break
    g, h = int(rng.integers(l * m)), int(rng.integers(l * m))
    A = [G.mul[g, perm[t]] for t in a]
    B = [G.mul[h, perm[t]] for t in b]
    if rng.integers(2):
        A, B = B, A
    return A, B


def test_codes_search_canonical_key_invariance():
    rng = np.random.default_rng(0)
    for l, m in [(6, 6), (12, 6), (15, 3), (9, 6)]:
        for _ in range(5):
            a = tuple(rng.choice(l * m, 3, replace=False))
            b = tuple(rng.choice(l * m, 3, replace=False))
            k0 = canonical_key_abelian(l, m, a, b)
            c0 = GroupAlgebraCode(abelian_group(l, m), a, b)
            for _ in range(5):
                A, B = _transform(l, m, a, b, rng)
                assert canonical_key_abelian(l, m, A, B) == k0
            rep = key_to_code(k0)
            assert (rep.n, rep.k) == (c0.n, c0.k)


def test_codes_search_key_across_isomorphic_shapes():
    # Z_3 x Z_5 ~ Z_5 x Z_3: swap x<->y and A<->B must give the same key
    c = coprime_bb_code(3, 5, (0, 1, 2), (0, 2, 7))
    l, m = 3, 5
    sw = lambda g: (g % m) * l + g // m   # x^i y^j in Z3xZ5 -> y^i x^j in Z5xZ3
    k1 = canonical_key(c)
    k2 = canonical_key_abelian(5, 3, [sw(t) for t in c.b], [sw(t) for t in c.a])
    assert k1 == k2


def test_codes_search_ibm_codes_distinct_keys():
    keys = {canonical_key(bb_code(r[1], r[2], r[3], r[4])) for r in IBM_TABLE3}
    assert len(keys) == len(IBM_TABLE3)


def test_codes_search_family_sizes():
    for l, m in [(3, 2), (4, 3), (5, 4)]:
        assert sum(1 for _ in ibm_family(l, m)) == family_size("ibm", l, m)
        assert sum(1 for _ in general_family(l, m)) == family_size("general", l, m)


# ------------------------------------------------------------------ distance

def test_codes_search_distance_72():
    c = bb_code(6, 6, "x^3+y+y^2", "y^3+x+x^2")
    css = c.to_css()
    ub = distance_upper_bound_bposd(css, trials=30, time_budget=20, seed=0, symmetric=True)
    assert ub["d_ub"] >= 6
    w = ub["witness"]
    assert css.is_logical_z(w) and int(w.sum()) == ub["d_ub"]
    ex = distance_exact_milp(css, time_limit=120, upper=ub["d_ub"], symmetric=True, translation_n2=c.n2)
    assert ex["exact"] and ex["d_upper"] == 6
    # without symmetry tricks and computing both types
    ex2 = distance_exact_milp(css, time_limit=120, upper=None, symmetric=False)
    assert ex2["exact"] and ex2["d_upper"] == 6


def test_codes_search_distance_small_known():
    # Wang-Mueller [[30,4,6]] coprime code
    row = WANG_MUELLER_T2[0]
    c = coprime_bb_code(row[1], row[2], row[3], row[4])
    ex = distance_exact_milp(c.to_css(), time_limit=60, symmetric=False)
    assert (c.n, c.k, ex["d_upper"], ex["exact"]) == (30, 4, 6, True)


# ------------------------------------------------------------------ constraints

def test_codes_search_thickness_and_connectivity():
    import networkx as nx
    c = bb_code(12, 6, "x^3+y+y^2", "y^3+x+x^2")
    th = thickness_le2(c)
    assert th["status"] == "le2"
    G = nx.Graph([(u, v) for u, v, _ in tanner_edges(c)])
    assert not nx.check_planarity(G)[0]       # full Tanner graph is not planar (thickness exactly 2)
    con = check_constraints(c)
    assert con["connected"] and con["weight_ok"]
    # a disconnected code: A, B only involve y on Z_2 x Z_3 -> components = copies along x
    d = bb_code(2, 6, "1+y+y^2", "1+y^3+y^4")
    assert not check_constraints(d, thickness=False)["connected"]


# ------------------------------------------------------------------ schedule interface

def test_codes_search_default_schedule_matches_baseline():
    from baselines.schedule import ibm_depth8
    c = bb_code(6, 6, "x^3+y+y^2", "y^3+x+x^2")
    s = default_schedule(c)
    assert s.layers == ibm_depth8(to_baseline_bbcode(c)).layers
    r = check_schedule(c, s, rounds=(1, 2), shots=8)
    assert r["valid_structure"] and r["deterministic"]


def test_codes_search_default_schedule_general_monomials():
    c = coprime_bb_code(3, 5, (0, 1, 2), (0, 2, 7))   # has mixed monomials x y^2
    r = check_schedule(c, default_schedule(c), rounds=(1, 2), shots=8)
    assert r["valid_structure"] and r["deterministic"]


def test_codes_search_pilot_smoke(tmp_path):
    from search.codes import pilot
    pilot.main(["--n-max", "40", "--out", str(tmp_path), "--workers", "2", "--time-cap", "120",
                "--s1", "4", "--n2", "20", "--s2", "20", "--n3", "6", "--s3", "40", "--milp-time", "30",
                "--top", "5"])
    import csv
    rows = list(csv.DictReader(open(tmp_path / "top20.csv")))
    assert 1 <= len(rows) <= 5
    for r in rows:
        assert int(r["n"]) <= 40 and int(r["k"]) > 0
        assert r["d_kind"] in ("exact", "upper")
