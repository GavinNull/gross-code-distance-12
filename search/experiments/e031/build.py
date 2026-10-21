"""E-031 instance builder: pseudo-Boolean (OPB) encoding with native parity rows + symmetry data for the
proof-logging search (pbdfs.c).

Question encoded (for an extended code with columns j, check rows H, logical rows L):
    exists x in {0,1}^n with H x = 0 (mod 2), L x != 0 (mod 2), |x| <= W, and x not a superset of any blocked set?

OPB variables
    x<j+1>        column j chosen                                  (j = 0..n-1)
    q<l+1>        parity of logical row l                           (l = 0..NL-1)
    a<r+1>_<k>    binary digits of half the row-r sum (check rows)  (k = 0..KC-1)
    b<l+1>_<k>    binary digits for logical row l                   (k = 0..KL-1)
Constraints, in this order (VeriPB ids: an '=' line gives two ids, >= then <=):
    check row r:    sum_{j in N_r} x_j - sum_k 2^{k+1} a_{r,k} = 0
    logical row l:  sum_{j in N_l} x_j + q_l - sum_k 2^{k+1} b_{l,k} = 0
    weight:         sum_j -x_j >= -W
    logical:        sum_l q_l >= 1
    blocked set B:  sum_{j in B} ~x_j >= 1
Exactness: a 0/1 point (x, q, a, b) satisfies the rows iff every check row has even x-sum and q_l is the parity
of the x-sum of row l (the digit vectors can represent every even sum because 2(2^K - 1) >= row size).  So the
formula is satisfiable iff such an x exists.

Logical rows: the given L rows (data level) are closed under the symmetry group G (all translates, deduplicated
at the level of extended-code column vectors).  Every translate of a logical operator is a logical operator, so
for x with H x = 0 "some translate row odd" <=> "L x != 0"; the closure makes the formula invariant under G
(checked below), which is what the redundance (symmetry) steps of the proof need.

Writes OUT.opb, OUT.inst (input of pbdfs.c), OUT.json (metadata, orbits, permutations).
    uv run python search/experiments/e031/build.py SOURCE BASIS W OUT [--blocks FILE] [--no-sym]
SOURCE: gross (Fig. 12 extended code), bb90 (c16 extended code) from release/zenodo/data, or ibm:<code>
(IBM depth-8 extended code built with the E-015 code, validation only).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "release" / "zenodo" / "data"


# ----------------------------------------------------------------------------------------------- sources
def bb_translation(l, m, s, t):
    """Data-qubit and check permutation of x^s y^t on a BB code (index m*a+b per block)."""
    g = np.array([((a + s) % l) * m + (b + t) % m for a in range(l) for b in range(m)])
    return np.concatenate([g, g + l * m]), g


def load_release(name, basis):
    code = json.load(open(DATA / "code" / ("gross_code.json" if name == "gross" else "bb90_code.json")))
    ext = json.load(open(DATA / "extended_code" / (("" if name == "gross" else "bb90_")
                                                   + f"extended_code_{basis}_memory.json")))
    l, m = int(code["l"]), int(code["m"])
    n = int(code["n"])
    H = np.zeros((len(code["H" + basis]), n), dtype=np.uint8)
    for i, row in enumerate(code["H" + basis]):
        H[i, row] = 1
    L = np.zeros((len(code["L" + basis]), n), dtype=np.uint8)
    for i, row in enumerate(code["L" + basis]):
        L[i, row] = 1
    sups = [tuple(c["support"]) for c in ext["columns"]]
    group = [tuple(g) for g in ext["translation_group"]]
    # consistency with the file's own H / L lists
    for c in ext["columns"]:
        s = list(c["support"])
        assert sorted(np.nonzero(H[:, s].sum(1) % 2)[0].tolist()) == sorted(c["H"])
        assert sorted(np.nonzero(L[:, s].sum(1) % 2)[0].tolist()) == sorted(c["L"])
    return dict(H=H, L=L, sups=sups, l=l, m=m, group=group, name=f"{name}_{basis}")


def load_ibm(key, basis):
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "search" / "experiments" / "e015"))
    from common import HL, get_code  # noqa
    from search.codes.schedule import default_schedule  # noqa
    from search.noninterleaved.ext import orders_from_schedule, residual_supports  # noqa
    code = get_code(key)
    xo, zo = orders_from_schedule(default_schedule(code))
    # E-015 convention: kind "X" = X-check orders -> X errors? HL(code,"X") = (HZ, LZ): Z-basis memory
    kind = "X" if basis == "Z" else "Z"
    orders = xo if kind == "X" else zo
    H, L = HL(code, kind)
    H = np.asarray(H, dtype=np.uint8) % 2
    L = np.asarray(L, dtype=np.uint8) % 2
    sups = [(j,) for j in range(code.n)] + [tuple(sorted(s)) for o in orders for s in residual_supports(o)]
    l, m = {"bb72": (6, 6), "bb108": (9, 6), "gross": (12, 6), "bb90": (15, 3)}[key]
    group = [(a, b) for a in range(l) for b in range(m)]
    return dict(H=H, L=L, sups=sups, l=l, m=m, group=group, name=f"ibm_{key}_{basis}")


# ----------------------------------------------------------------------------------------------- build
def build(src, W, blocks=(), use_sym=True):
    H, L, l, m = src["H"], src["L"], src["l"], src["m"]
    group = src["group"] if use_sym else [(0, 0)]
    # merge supports into extended-code columns (key: H-vector and L-vector)
    key_of, cols = {}, []
    for S in src["sups"]:
        h = H[:, list(S)].sum(1) % 2
        lv = L[:, list(S)].sum(1) % 2
        if not h.any() and not lv.any():
            continue
        k = h.tobytes() + lv.tobytes()
        if k not in key_of:
            key_of[k] = len(cols)
            cols.append(tuple(S))
    n = len(cols)
    Hc = np.array([H[:, list(S)].sum(1) % 2 for S in cols], dtype=np.uint8).T      # R x n
    R = Hc.shape[0]
    # data-level translations, column permutations, row permutations
    perms, rperms, dperms = [], [], []
    hrow = {H[i].tobytes(): i for i in range(R)}
    for (s, t) in group:
        dp, _ = bb_translation(l, m, s, t)
        dperms.append(dp)
        P = np.full(n, -1)
        for j, S in enumerate(cols):
            T = [int(dp[q]) for q in S]
            k = (H[:, T].sum(1) % 2).tobytes() + (L[:, T].sum(1) % 2).tobytes()
            assert k in key_of, "column set not invariant"
            P[j] = key_of[k]
        assert sorted(P.tolist()) == list(range(n))
        rp = np.full(R, -1)
        for i in range(R):
            Ti = np.zeros(H.shape[1], dtype=np.uint8)
            Ti[dp[np.nonzero(H[i])[0]]] = 1
            rp[i] = hrow[Ti.tobytes()]
        # H column vectors must be equivariant
        for j in range(n):
            assert (Hc[:, P[j]] == Hc[rp.argsort()][:, j][rp.argsort().argsort()]).all() or True
        perms.append(P)
        rperms.append(rp)
    # equivariance check (direct): row rp[i] contains column P[j] iff row i contains column j
    for P, rp in zip(perms, rperms):
        assert (Hc[np.ix_(rp, P)] == Hc).all()
    # logical rows: closure of the L rows under the group, as column vectors
    lvecs, lkey = [], {}
    for dp in dperms:
        for r in range(L.shape[0]):
            Tl = np.zeros(H.shape[1], dtype=np.uint8)
            Tl[dp[np.nonzero(L[r])[0]]] = 1
            v = np.array([Tl[list(S)].sum() % 2 for S in cols], dtype=np.uint8)
            if not v.any():
                continue
            if v.tobytes() not in lkey:
                lkey[v.tobytes()] = len(lvecs)
                lvecs.append(v)
    Lc = np.array(lvecs, dtype=np.uint8)                                           # NL x n
    NL = Lc.shape[0]
    lperms = []
    for P in perms:
        lp = np.full(NL, -1)
        for i in range(NL):
            v = np.zeros(n, dtype=np.uint8)
            v[P[np.nonzero(Lc[i])[0]]] = 1
            lp[i] = lkey[v.tobytes()]
        assert sorted(lp.tolist()) == list(range(NL))
        assert (Lc[np.ix_(lp, P)] == Lc).all()
        lperms.append(lp)
    # the original rows are among them (spanning property is then automatic)
    for r in range(L.shape[0]):
        v = np.array([L[r, list(S)].sum() % 2 for S in cols], dtype=np.uint8)
        assert not v.any() or v.tobytes() in lkey
    # a basis of the logical rows modulo the check rows, and for every other logical row m its expansion
    # Lc[m] = sum_{l in c_m} Lc[l] + sum_{r in d_m} Hc[r] (mod 2); the proof turns these into clauses
    # ~q_m v OR_{l in c_m} q_l, so that branching on "some logical row is odd" can use the basis only
    basis, expand = logical_basis(Hc, Lc)
    # blocked sets: as column-index sets; must be closed under the group
    bl = sorted({tuple(sorted(b)) for b in blocks})
    bset = set(bl)
    for P in perms:
        for b in bl:
            assert tuple(sorted(int(P[j]) for j in b)) in bset, "blocked list not closed under the group"
    # orbits
    orb = np.full(n, -1)
    orbits = []
    for j in range(n):
        if orb[j] >= 0:
            continue
        o = sorted({int(P[j]) for P in perms})
        orb[o] = len(orbits)
        orbits.append(o)
    rows = [np.nonzero(Hc[i])[0].tolist() for i in range(R)] + [np.nonzero(Lc[i])[0].tolist() for i in range(NL)]
    KC = max(1, int(np.ceil(np.log2(max(len(r) for r in rows[:R]) / 2 + 1))))
    KL = max(1, int(np.ceil(np.log2((max(len(r) for r in rows[R:]) + 1) / 2 + 1))))
    assert 2 * (2 ** KC - 1) >= max(len(r) for r in rows[:R])
    assert 2 * (2 ** KL - 1) >= max(len(r) for r in rows[R:]) + 1
    return dict(n=n, R=R, NL=NL, W=W, rows=rows, KC=KC, KL=KL, cols=cols, Hc=Hc, Lc=Lc, perms=perms,
                rperms=rperms, lperms=lperms, orbits=orbits, blocks=bl, basis=basis, expand=expand)


def logical_basis(Hc, Lc):
    """Greedy basis of span(Lc) modulo span(Hc) over GF(2) (rows of Lc in order) and the expansion of every
    non-basis row.  Expansions are verified by direct recomputation."""
    R, n = Hc.shape
    NL = Lc.shape[0]
    # reduced echelon form with tracking: vectors are (row over columns, combination bits)
    piv = {}            # pivot column -> (vec, comb) ; comb = (set of H rows, set of basis L rows)

    def reduce(v, comb):
        v = v.copy(); ch, cl = set(comb[0]), set(comb[1])
        changed = True
        while True:
            nz = np.nonzero(v)[0]
            hit = [c for c in nz if c in piv]
            if not hit:
                return v, (ch, cl)
            c = hit[0]
            pv, (ph, pl) = piv[c]
            v ^= pv; ch ^= ph; cl ^= pl
    for r in range(R):
        v, comb = reduce(Hc[r], ({r}, set()))
        if v.any():
            piv[int(np.nonzero(v)[0][0])] = (v, comb)
    basis, expand = [], {}
    for m in range(NL):
        v, (ch, cl) = reduce(Lc[m], (set(), {m}))
        if v.any():
            basis.append(m)
            piv[int(np.nonzero(v)[0][0])] = (v, (ch, cl))
        else:
            # Lc[m] + sum_{cl \ {m}} Lc + sum_ch Hc = 0  ->  Lc[m] = sum_{cl\{m}} Lc + sum_ch Hc
            cm = sorted(cl - {m}); dm = sorted(ch)
            assert all(l in basis for l in cm)
            chk = (Lc[cm].sum(0) + Hc[dm].sum(0)) % 2
            assert (chk == Lc[m]).all()
            expand[m] = (cm, dm)
    return basis, expand


def opb_lines(I):
    n, R, NL = I["n"], I["R"], I["NL"]
    out = []
    for i, row in enumerate(I["rows"]):
        if i < R:
            terms = [f"1 x{j + 1}" for j in row] + [f"-{2 ** (k + 1)} a{i + 1}_{k}" for k in range(I["KC"])]
        else:
            li = i - R
            terms = [f"1 x{j + 1}" for j in row] + [f"1 q{li + 1}"] + \
                    [f"-{2 ** (k + 1)} b{li + 1}_{k}" for k in range(I["KL"])]
        out.append(" ".join(terms) + " = 0 ;")
    out.append(" ".join(f"-1 x{j + 1}" for j in range(n)) + f" >= -{I['W']} ;")
    out.append(" ".join(f"1 q{l + 1}" for l in range(NL)) + " >= 1 ;")
    for b in I["blocks"]:
        out.append(" ".join(f"1 ~x{j + 1}" for j in b) + " >= 1 ;")
    return out


def witness(I, g, rep):
    """Substitution x_j -> x_{P[j]} of the group element P with P[rep] = g (witness for ~x_g v x_rep v ...)."""
    for P, rp, lp in zip(I["perms"], I["rperms"], I["lperms"]):
        if P[rep] == g:
            s = [f"x{j + 1} -> x{P[j] + 1}" for j in range(I["n"]) if P[j] != j]
            s += [f"q{i + 1} -> q{lp[i] + 1}" for i in range(I["NL"]) if lp[i] != i]
            s += [f"a{i + 1}_{k} -> a{rp[i] + 1}_{k}" for i in range(I["R"]) if rp[i] != i for k in range(I["KC"])]
            s += [f"b{i + 1}_{k} -> b{lp[i] + 1}_{k}" for i in range(I["NL"]) if lp[i] != i for k in range(I["KL"])]
            return " ".join(s)
    raise ValueError("no group element")


def check_automorphisms(I, lines):
    """Every group element maps the multiset of OPB constraints onto itself (syntactic invariance)."""
    import re

    def canon(line, ren):
        body, rel = re.split(r" (=|>=) ", line[:-2])[0::2], re.search(r" (=|>=) ", line).group(1)
        toks = body[0].split()
        terms = sorted((int(toks[i]), ren(toks[i + 1])) for i in range(0, len(toks), 2))
        return (tuple(terms), rel, body[1].strip())
    base = {canon(x, lambda v: v) for x in lines}
    assert len(base) == len(lines)
    for P, rp, lp in zip(I["perms"], I["rperms"], I["lperms"]):
        def ren(v):
            neg = v.startswith("~")
            w = v[1:] if neg else v
            if w[0] == "x":
                w = f"x{P[int(w[1:]) - 1] + 1}"
            elif w[0] == "q":
                w = f"q{lp[int(w[1:]) - 1] + 1}"
            else:
                i, k = w[1:].split("_")
                w = f"{w[0]}{(rp if w[0] == 'a' else lp)[int(i) - 1] + 1}_{k}"
            return ("~" if neg else "") + w
        img = {canon(x, ren) for x in lines}
        assert img == base, "formula not invariant"
    return len(I["perms"])


def write(I, out, case_order=None):
    lines = opb_lines(I)
    nsym = check_automorphisms(I, lines) if len(I["perms"]) > 1 else 1
    nvars = I["n"] + I["NL"] + I["R"] * I["KC"] + I["NL"] * I["KL"]
    with open(out + ".opb", "w") as f:
        f.write(f"* #variable= {nvars} #constraint= {len(lines)}\n")
        f.write("\n".join(lines) + "\n")
    # constraint ids: rows give 2 each
    rid = []
    cid = 1
    for _ in I["rows"]:
        rid.append((cid, cid + 1))
        cid += 2
    wid, sid = cid, cid + 1
    bid = cid + 2
    ncons = cid + 1 + len(I["blocks"])
    # cases: orbit reps (with symmetry) or every column
    n, R, NL = I["n"], I["R"], I["NL"]
    with open(out + ".inst", "w") as f:
        f.write(f"{n} {NL} {R} {I['W']} {ncons}\n")
        colrows = [[] for _ in range(n + NL)]
        for i, row in enumerate(I["rows"]):
            for j in row:
                colrows[j].append(i)
            if i >= R:
                colrows[n + i - R].append(i)
        for j in range(n + NL):
            f.write(f"{1 if j < n else 0} {len(colrows[j])} " + " ".join(map(str, colrows[j])) + "\n")
        for (g, le) in rid:
            f.write(f"{g} {le}\n")
        f.write(f"{wid} {sid}\n")
        f.write(f"{len(I['basis'])} " + " ".join(map(str, I["basis"])) + "\n")
        f.write(f"{len(I['expand'])}\n")
        for m, (cm, dm) in sorted(I["expand"].items()):
            f.write(f"{m} {len(cm)} " + " ".join(map(str, cm)) + f" {len(dm)} " + " ".join(map(str, dm)) + "\n")
        f.write(f"{len(I['blocks'])} {bid}\n")
        for b in I["blocks"]:
            f.write(f"{len(b)} " + " ".join(map(str, b)) + "\n")
        # cases
        if len(I["perms"]) > 1:
            f.write(f"{len(I['orbits'])}\n")
            for o in I["orbits"]:
                rep = o[0]
                f.write(f"{rep} {len(o) - 1}\n")
                for g in o[1:]:
                    f.write(f"{g} {witness(I, g, rep)}\n")
        else:
            order = case_order or list(range(n))
            f.write(f"{len(order)}\n")
            for j in order:
                f.write(f"{j} 0\n")
    meta = dict(n=n, R=R, NL=NL, basis=len(I["basis"]), W=I["W"], KC=I["KC"], KL=I["KL"], nsym=nsym, orbits=[len(o) for o in I["orbits"]],
                blocks=len(I["blocks"]), ncons=ncons, nvars=nvars,
                row_sizes=[len(r) for r in I["rows"][:R]], lrow_sizes=[len(r) for r in I["rows"][R:]])
    Path(out + ".json").write_text(json.dumps(meta))
    return meta


def load_blocks(path, src_cols_name):
    d = json.load(open(path))
    return [tuple(e["columns"]) for e in d["logicals"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("basis")
    ap.add_argument("W", type=int)
    ap.add_argument("out")
    ap.add_argument("--blocks", nargs="*", default=[])
    ap.add_argument("--no-sym", action="store_true")
    ap.add_argument("--drop-block", type=int, default=None, help="remove the orbit of block #i (planted test)")
    a = ap.parse_args()
    if a.source in ("gross", "bb90"):
        src = load_release(a.source, a.basis)
    else:
        src = load_ibm(a.source.split(":")[1], a.basis)
    blocks = []
    for p in a.blocks:
        blocks += load_blocks(p, None)
    I = build(src, a.W, (), use_sym=not a.no_sym)
    # release column indices == our merged indices? (release columns are already merged; verify identity)
    if a.source in ("gross", "bb90"):
        assert I["n"] == len(src["sups"]), "release columns were expected to be distinct"
    if a.drop_block is not None:
        b0 = tuple(sorted(blocks[a.drop_block]))
        orbit_b0 = {tuple(sorted(int(P[j]) for j in b0)) for P in I["perms"]}
        blocks = [b for b in blocks if tuple(sorted(b)) not in orbit_b0]
        print("dropped", len(orbit_b0), "blocked sets (orbit of block", a.drop_block, ")")
    I = build(src, a.W, blocks, use_sym=not a.no_sym)
    meta = write(I, a.out)
    print(json.dumps({k: v for k, v in meta.items() if k not in ("row_sizes", "lrow_sizes")}),
          "check row sizes", sorted(set(meta["row_sizes"])), "logical row sizes", min(meta["lrow_sizes"]),
          max(meta["lrow_sizes"]))


if __name__ == "__main__":
    main()
