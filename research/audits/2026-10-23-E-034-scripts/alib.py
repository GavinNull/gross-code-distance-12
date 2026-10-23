"""Auditor's own library for the E-031 audit.  Imports nothing from search/ or evaluators/.

Inputs used: release/zenodo/data/code/{bb90,gross}_code.json (H, L matrices and qubit indexing),
the circuit files (release/zenodo/data/circuits/bb90_c16.json, search/experiments/e032/u11_spec.json) for the CNOT
orders, and -- only to fix the column NUMBERING used by the blocked lists -- the release extended-code files.

Extended code of a memory basis b (b = Z: X errors, H = HZ, L = LZ, hooks of the X checks; b = X: the converse):
columns = distinct non-zero (H s, L s) over s in {single data qubits} U {proper suffixes order[k:], k = 1..5, of the
time-ordered CNOT list of every check of the other type}.
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "release/zenodo/data"


def rank2(M):
    M = (np.array(M, dtype=np.uint8) % 2).copy()
    r = 0
    rows, cols = M.shape
    for c in range(cols):
        p = None
        for i in range(r, rows):
            if M[i, c]:
                p = i; break
        if p is None:
            continue
        M[[r, p]] = M[[p, r]]
        for i in range(rows):
            if i != r and M[i, c]:
                M[i] ^= M[r]
        r += 1
        if r == rows:
            break
    return r


def mat(rows, n):
    M = np.zeros((len(rows), n), dtype=np.uint8)
    for i, r in enumerate(rows):
        M[i, r] = 1
    return M


def load_code(name):
    c = json.load(open(DATA / "code" / f"{name}_code.json"))
    n = int(c["n"])
    return dict(n=n, l=int(c["l"]), m=int(c["m"]), HX=mat(c["HX"], n), HZ=mat(c["HZ"], n),
                LX=mat(c["LX"], n), LZ=mat(c["LZ"], n))


def translation(l, m, s, t):
    g = np.array([((a + s) % l) * m + (b + t) % m for a in range(l) for b in range(m)])
    return np.concatenate([g, g + l * m])


def orders(spec, typ):
    P = spec["period"]
    out = []
    for c in spec["x_checks" if typ == "X" else "z_checks"]:
        out.append([q for q, t in sorted(c["cnots"], key=lambda qt: (qt[1] - c["prep"]) % P)])
    return out


def ext_code(codename, spec_path, basis, release_ext=None):
    """returns dict(H, L, cols(list of supports), keys, Hc, Lcol, group perms on columns, data perms)."""
    C = load_code(codename)
    n, l, m = C["n"], C["l"], C["m"]
    H, L = (C["HZ"], C["LZ"]) if basis == "Z" else (C["HX"], C["LX"])
    Hother = C["HX"] if basis == "Z" else C["HZ"]
    spec = json.load(open(spec_path))
    hook_type = "X" if basis == "Z" else "Z"
    ords = orders(spec, hook_type)
    Hh = C["HX"] if hook_type == "X" else C["HZ"]
    for i, o in enumerate(ords):
        assert sorted(o) == np.flatnonzero(Hh[i]).tolist() and len(o) == 6
    sups = [(q,) for q in range(n)] + [tuple(sorted(o[k:])) for o in ords for k in range(1, 6)]

    def key(S):
        v = np.zeros(n, dtype=np.uint8); v[list(S)] = 1
        return (H.astype(int) @ v % 2).astype(np.uint8).tobytes() + (L.astype(int) @ v % 2).astype(np.uint8).tobytes()
    cols, keys = [], {}
    for S in sups:
        k = key(S)
        if k.strip(b"\x00") == b"":
            continue
        if k not in keys:
            keys[k] = len(cols); cols.append(S)
    if release_ext is not None:
        # renumber to the release numbering (needed for the blocked lists); require identical key sets
        rel = json.load(open(release_ext))["columns"]
        rkeys = [key(c["support"]) for c in rel]
        assert len(set(rkeys)) == len(rkeys) == len(cols) and set(rkeys) == set(keys), "column set differs"
        cols = [cols[keys[k]] for k in rkeys]
        keys = {k: j for j, k in enumerate(rkeys)}
    N = len(cols)
    Hc = np.array([[int(H[i, list(S)].sum() % 2) for S in cols] for i in range(H.shape[0])], dtype=np.uint8)
    # translations: code invariance, column permutations
    perms, dperms, rperms = [], [], []
    group = [(s, t) for s in range(l) for t in range(m)]
    if release_ext is not None:
        group = [tuple(g) for g in json.load(open(release_ext))["translation_group"]]
    for (s, t) in group:
        if True:
            dp = translation(l, m, s, t)
            for M in (C["HX"], C["HZ"]):
                rs = {tuple(np.flatnonzero(r)) for r in M}
                assert {tuple(sorted(dp[np.flatnonzero(r)])) for r in M} == rs
            P = np.array([keys[key(tuple(dp[list(S)]))] for S in cols])
            assert sorted(P) == list(range(N))
            perms.append(P); dperms.append(dp)
    return dict(n=n, l=l, m=m, H=H, L=L, Hother=Hother, cols=cols, keys=keys, Hc=Hc, perms=perms,
                dperms=dperms, N=N, key=key, C=C)


def col_vec(E, row):
    """GF(2) value of a data-level row on every column."""
    return np.array([int(row[list(S)].sum() % 2) for S in E["cols"]], dtype=np.uint8)
