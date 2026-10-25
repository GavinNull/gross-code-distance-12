"""E-037: OPB instance + search input for "is there an undetectable logical of weight <= W" on a DEM.  experimenter.

Same encoding as e031/build.py (audited in E-031), with the extended code replaced by the DEM itself:
    columns   = merged single-fault classes (one x_j each)
    check rows = detectors                     sum_{j in N_r} x_j - sum_k 2^{k+1} a_{r,k} = 0
    logical rows = closure of the observable rows under the translation group (as DEM column vectors)
                                               sum_{j in N_l} x_j + q_l - sum_k 2^{k+1} b_{l,k} = 0
    weight     sum_j -x_j >= -W ;  logical  sum_l q_l >= 1 ;  (blocked sets: none here)
A 0/1 point satisfies the formula iff x has even parity on every detector, some logical row is odd and |x| <= W.
Logical rows: L_i o P_g^{-1} for every observable i and translation g.  Every such row is asserted to lie in
span(observable rows, detector rows) (explicit expansion, verified), and the observable rows themselves are in the
set, so on {D x = 0}: "some row odd" <=> "L x != 0".  The formula is then invariant under the group (checked line by
line with e031.build.check_automorphisms), which the redundance steps of the proof need.

Translations: x^s y^t acts on detectors (check i, cycle c) -> (g(i), c) and on columns through their detector sets
(detector sets of distinct columns are distinct; equal sets with different logicals would be a weight-2 logical and
are asserted absent).  A translation is used only if every column maps onto a column.

Sources
  ibm:CODE:TYP:R       IBM decoder_setup.py model (ibm_model.py), TYP X = X faults (Z basis), Z = Z faults (X basis)
  sd6:CODE:BASIS:R     evaluator memory circuit of baselines ibm_depth8 + evaluators.noise sd6 (E-026 / E-033)
  CODE in {gross, bb108}

    uv run python search/experiments/e037/dem_inst.py SOURCE W OUT [--no-sym]
writes OUT.opb, OUT.inst (input of e037/pbdfs.c), OUT.json (meta), OUT.cols.json (column list for re-verification)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for p in (str(ROOT), str(ROOT / "tests"), str(HERE), str(ROOT / "search/experiments/e031")):
    if p not in sys.path:
        sys.path.insert(0, p)
import ibm_model as im  # noqa: E402

TASK = {"gross": "gross-dcirc", "bb108": "bb108-dcirc"}


# ------------------------------------------------------------------------------------------------ sources
def src_ibm(code_name, typ, R):
    code = im.Code(code_name)
    d = im.build_dem(code, typ, R, ibm_faithful=True)
    nc = code.n2
    coords = [(i % nc, i // nc) for i in range(d["ndet"])]
    return dict(D=d["D"], L=d["L"], ndet=d["ndet"], nobs=d["k"], coords=coords, l=code.l, m=code.m,
                desc=f"ibm:{code_name}:{typ}:{R}")


def sd6_circuit(code_name, basis, R, p=1e-3):
    from evaluators import candidate as cand
    from evaluators.noise import add_noise
    from evaluators.tasks import build_code, get_task
    from baselines.bb_code import BBCode
    from baselines.schedule import ibm_depth8
    from schedule_helpers import from_baseline
    code, _ = build_code(get_task(TASK[code_name]), None)
    l, m = im.CODES[code_name][:2]
    s = from_baseline(ibm_depth8(BBCode(l, m, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"]))).canonical()
    assert not cand.validate_schedule(s, code)
    c = cand.memory_circuit(s, code, basis, R)
    return add_noise(c, "sd6", p), code


def src_sd6(code_name, basis, R):
    circ, code = sd6_circuit(code_name, basis, R)
    dem = circ.detector_error_model(decompose_errors=False)
    D, L = [], []
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        dd, oo = set(), set()
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                dd ^= {t.val}
            elif t.is_logical_observable_id():
                oo ^= {t.val}
        if not dd and not oo:
            continue
        D.append(tuple(sorted(dd))); L.append(tuple(sorted(oo)))
    co = dem.get_detector_coordinates()
    coords = [(int(co[i][0]), int(co[i][1])) for i in range(dem.num_detectors)]
    l, m = im.CODES[code_name][:2]
    # merge identical (D, L) (stim already merges; keep the check)
    seen, D2, L2 = set(), [], []
    for dd, oo in zip(D, L):
        if (dd, oo) in seen:
            continue
        seen.add((dd, oo)); D2.append(dd); L2.append(oo)
    return dict(D=D2, L=L2, ndet=dem.num_detectors, nobs=dem.num_observables, coords=coords, l=l, m=m,
                desc=f"sd6:{code_name}:{basis}:{R}")


def load_source(s):
    kind, code_name, b, R = s.split(":")
    return (src_ibm if kind == "ibm" else src_sd6)(code_name, b, int(R))


# ------------------------------------------------------------------------------------------------ GF(2) with ints
def vec_int(idx):
    v = 0
    for j in idx:
        v ^= 1 << j
    return v


def logical_basis_int(Hrows, Lrows):
    """Greedy basis of span(L) mod span(H) (rows of L in order); expansion of every other row:
    L[m] = sum_{cm} L[l] + sum_{dm} H[r].  Vectors are python ints (bit j = column j)."""
    piv = {}            # pivot bit -> (vec, hset_int, lset_int)

    def reduce(v, h, lset):
        # echelon form keyed by leading bit: every nonzero vector of the span has a pivot as leading bit, so a
        # vector whose leading bit is not a pivot is independent of the span
        while v:
            b = v.bit_length() - 1
            if b not in piv:
                return v, h, lset
            pv, ph, pl = piv[b]
            v ^= pv; h ^= ph; lset ^= pl
        return v, h, lset
    for r, hv in enumerate(Hrows):
        v, h, ls = reduce(hv, 1 << r, 0)
        if v:
            piv[v.bit_length() - 1] = (v, h, ls)
    basis, expand = [], {}
    for mi, lv in enumerate(Lrows):
        v, h, ls = reduce(lv, 0, 1 << mi)
        if v:
            basis.append(mi)
            piv[v.bit_length() - 1] = (v, h, ls)
        else:
            cm = [i for i in range(len(Lrows)) if (ls >> i) & 1 and i != mi]
            dm = [i for i in range(len(Hrows)) if (h >> i) & 1]
            chk = 0
            for i in cm:
                chk ^= Lrows[i]
            for i in dm:
                chk ^= Hrows[i]
            assert chk == lv
            assert all(i in basis for i in cm)
            expand[mi] = (cm, dm)
    return basis, expand


# ------------------------------------------------------------------------------------------------ build
# blocks_note: the formula may carry blocking clauses sum_{j in T} ~x_j >= 1 for detector-silent, logically trivial
# sets T (closed under the group).  They are NOT implied by the parity/weight/logical constraints; they preserve
# satisfiability for the question asked (see check_trivial).  UNSAT of the blocked formula therefore proves that
# no undetectable logical of weight <= W exists.
def build(src, W, use_sym=True, blocks=(), cards=(), small_logical=True):
    D, L, ndet, nobs = src["D"], src["L"], src["ndet"], src["nobs"]
    n = len(D)
    index = {}
    for j, d in enumerate(D):
        assert d, "column without detectors"
        assert d not in index, "two columns with equal detector sets (weight-2 logical)"
        index[d] = j
    l, m = src["l"], src["m"]
    key = {c: i for i, c in enumerate(src["coords"])}
    assert len(key) == ndet
    perms, rperms = [], []
    elems = [(a, b) for a in range(l) for b in range(m)] if use_sym else [(0, 0)]
    used = []
    for (a, b) in elems:
        def tq(i):
            x, y = divmod(i, m)
            return ((x + a) % l) * m + (y + b) % m
        rp = np.array([key[(tq(c[0]), c[1])] for c in src["coords"]])
        P = np.full(n, -1)
        ok = True
        for j, d in enumerate(D):
            img = tuple(sorted(int(rp[x]) for x in d))
            if img not in index:
                ok = False
                break
            P[j] = index[img]
        if not ok:
            continue
        assert sorted(P.tolist()) == list(range(n))
        perms.append(P); rperms.append(rp); used.append((a, b))
    assert used[0] == (0, 0)
    # rows as column-index lists
    drows = [[] for _ in range(ndet)]
    for j, d in enumerate(D):
        for x in d:
            drows[x].append(j)
    orows = [[] for _ in range(nobs)]
    for j, o in enumerate(L):
        for x in o:
            orows[x].append(j)
    # logical rows: union of the orbits (rows L_i o P^{-1}) of a few observables i whose orbits together span the
    # whole logical space modulo the detector rows (smallest such union among subsets of <= 3 observables; all 12
    # (8) observables if none).  Requirement for exactness, asserted: every original observable row lies in
    # span(chosen rows, detector rows) and every chosen row lies in span(observable rows, detector rows) (the
    # latter by the explicit expansions below), so on {D x = 0}:  some chosen row odd  <=>  L x != 0.
    Hint = [vec_int(r) for r in drows]
    orb_of = []
    for i in range(nobs):
        o = []
        seen = set()
        for P in perms:
            v = vec_int(int(P[j]) for j in orows[i])
            if v and v not in seen:
                seen.add(v); o.append(v)
        orb_of.append(o)

    def rank_mod_h(vs):
        piv = {}

        def red(v):
            while v:
                b = v.bit_length() - 1
                if b not in piv:
                    return v
                v ^= piv[b]
            return 0
        for h in Hint:
            v = red(h)
            if v:
                piv[v.bit_length() - 1] = v
        r = 0
        for v in vs:
            v = red(v)
            if v:
                piv[v.bit_length() - 1] = v; r += 1
        return r
    import itertools
    choice = None
    for size in (1, 2, 3):
        for sub in itertools.combinations(range(nobs), size):
            u = []
            ss = set()
            for i in sub:
                for v in orb_of[i]:
                    if v not in ss:
                        ss.add(v); u.append(v)
            if choice is not None and len(u) >= len(choice[1]):
                continue
            if rank_mod_h(u) == nobs:
                choice = (sub, u)
        if choice is not None:
            break
    if choice is None or not small_logical:
        u, ss = [], set()
        for i in range(nobs):
            for v in orb_of[i]:
                if v not in ss:
                    ss.add(v); u.append(v)
        choice = (tuple(range(nobs)), u)
    lvecs = choice[1]
    lkey = {v: i for i, v in enumerate(lvecs)}
    for i in range(nobs):          # every observable row in span(chosen rows, detectors)
        assert rank_mod_h(lvecs + [vec_int(orows[i])]) == rank_mod_h(lvecs) == nobs
    NL = len(lvecs)
    lperms = []
    for P in perms:
        lp = np.full(NL, -1)
        for i, v in enumerate(lvecs):
            w = 0
            vv = v
            while vv:
                b = vv & -vv
                j = b.bit_length() - 1
                w ^= 1 << int(P[j])
                vv ^= b
            lp[i] = lkey[w]
        assert sorted(lp.tolist()) == list(range(NL))
        lperms.append(lp)
    basis, expand = logical_basis_int(Hint, lvecs)
    assert len(basis) == nobs, (len(basis), nobs)
    lrows = []
    for v in lvecs:
        idx, vv = [], v
        while vv:
            b = vv & -vv
            idx.append(b.bit_length() - 1)
            vv ^= b
        lrows.append(sorted(idx))
    # orbits (cases ordered by first column index; columns are in time order from both sources)
    orb = np.full(n, -1)
    orbits = []
    for j in range(n):
        if orb[j] >= 0:
            continue
        o = sorted({int(P[j]) for P in perms})
        orb[o] = len(orbits)
        orbits.append(o)
    # blocked trivial sets (see blocks_note below): closure under the group
    bl = set()
    for b in blocks:
        for P in perms:
            bl.add(tuple(sorted(int(P[j]) for j in b)))
    bl = sorted(bl, key=lambda t: (len(t), t))
    for b in bl:
        assert len(b) <= W
    cards = sorted(set((int(bd), tuple(sorted(t))) for bd, t in cards), key=lambda c: (len(c[1]), c[1]))
    cset = set(cards)
    for P in perms:
        for bd, t in cards:
            assert (bd, tuple(sorted(int(P[j]) for j in t))) in cset, "cardinality family not group-closed"
    rows = drows + lrows
    R = ndet
    KC = max(1, int(np.ceil(np.log2(max(len(r) for r in rows[:R]) / 2 + 1))))
    KL = max(1, int(np.ceil(np.log2((max(len(r) for r in rows[R:]) + 1) / 2 + 1))))
    assert 2 * (2 ** KC - 1) >= max(len(r) for r in rows[:R])
    assert 2 * (2 ** KL - 1) >= max(len(r) for r in rows[R:]) + 1
    return dict(n=n, R=R, NL=NL, W=W, rows=rows, KC=KC, KL=KL, perms=perms, rperms=rperms, lperms=lperms,
                orbits=orbits, blocks=bl, cards=cards, logical_generators=list(choice[0]), basis=basis, expand=expand, group=used)


def write(I, out, check_sym=True):
    from build import opb_lines, check_automorphisms   # e031/build.py (audited), unchanged
    lines = opb_lines(I)
    nb = len(I["blocks"])
    cards = I.get("cards", [])
    clines = [" ".join(f"-1 x{j + 1}" for j in t) + f" >= -{bd} ;" for bd, t in cards]
    # syntactic invariance of every non-block line under every group element (e031 check); the block lines are a
    # group-closed family of clauses by construction (closure above), re-asserted here
    nsym = check_automorphisms(I, lines[:len(lines) - nb]) if (check_sym and len(I["perms"]) > 1) else len(I["perms"])
    bset = set(I["blocks"])
    for P in I["perms"]:
        for b in I["blocks"]:
            assert tuple(sorted(int(P[j]) for j in b)) in bset
    nvars = I["n"] + I["NL"] + I["R"] * I["KC"] + I["NL"] * I["KL"]
    with open(out + ".opb", "w") as f:
        f.write(f"* #variable= {nvars} #constraint= {len(lines) + len(clines)}\n")
        f.write("\n".join(lines + clines) + "\n")
    rid, cid = [], 1
    for _ in I["rows"]:
        rid.append((cid, cid + 1)); cid += 2
    wid, sid = cid, cid + 1
    bid = cid + 2
    kid = bid + nb
    ncons = cid + 1 + nb + len(cards)
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
        for mm, (cm, dm) in sorted(I["expand"].items()):
            f.write(f"{mm} {len(cm)} " + " ".join(map(str, cm)) + f" {len(dm)} " + " ".join(map(str, dm)) + "\n")
        f.write(f"{nb} {bid}\n")
        for b in I["blocks"]:
            f.write(f"{len(b)} " + " ".join(map(str, b)) + "\n")
        f.write(f"{len(cards)} {kid}\n")
        for bd, t in cards:
            f.write(f"{bd} {len(t)} " + " ".join(map(str, t)) + "\n")
        # group: KC KL NG, then per element x-perm, q-perm, row-perm
        f.write(f"{I['KC']} {I['KL']} {len(I['perms'])}\n")
        for P, rp, lp in zip(I["perms"], I["rperms"], I["lperms"]):
            f.write(" ".join(map(str, P.tolist())) + "\n")
            f.write(" ".join(map(str, lp.tolist())) + "\n")
            f.write(" ".join(map(str, rp.tolist())) + "\n")
        # cases: orbit rep, members with the index of a group element mapping rep -> member
        f.write(f"{len(I['orbits'])}\n")
        for o in I["orbits"]:
            rep = o[0]
            f.write(f"{rep} {len(o) - 1}\n")
            for g in o[1:]:
                gi = next(k for k, P in enumerate(I["perms"]) if P[rep] == g)
                f.write(f"{g} {gi}\n")
    meta = dict(logical_generators=I.get("logical_generators"), nblocks=nb, ncards=len(cards), ncard3=sum(len(t) == 3 for _, t in cards),
                ncard4=sum(len(t) == 4 for _, t in cards), n=n, R=R, NL=NL, basis=len(I["basis"]), W=I["W"], KC=I["KC"], KL=I["KL"], nsym=nsym,
                group=[list(g) for g in I["group"]], norbits=len(I["orbits"]), ncons=ncons, nvars=nvars,
                max_row=max(len(r) for r in I["rows"][:R]), max_lrow=max(len(r) for r in I["rows"][R:]))
    Path(out + ".json").write_text(json.dumps(meta))
    return meta


def check_trivial(src, blocks):
    """Every blocked set must be detector-silent and flip no observable (then, by the group, neither do its
    translates).  Justification of the blocking clauses (outside the proof): a minimum-weight solution x contains no
    nonempty detector-silent proper subset y (else y or x \\ y is a lighter solution), and a trivial set T is never
    equal to a solution, so every minimum-weight solution satisfies ~(AND_{j in T} x_j) for every trivial T."""
    D, L = src["D"], src["L"]
    for b in blocks:
        assert len(set(b)) == len(b) >= 1
        d, o = set(), set()
        for j in b:
            d ^= set(D[j]); o ^= set(L[j])
        assert not d and not o, ("blocked set is not trivial", b)


def small_trivial(D, L, kmax=4):
    """All detector-silent, logically trivial column sets of size 3 (and 4 if kmax >= 4), by pair XOR lookup.
    Every minimum-weight solution x satisfies |x cap T| <= floor(|T|/2) for each of them (else x xor T is a lighter
    solution: same detectors, same logicals), which justifies the cardinality constraints."""
    import collections
    import itertools
    n = len(D)
    Df = [frozenset(d) for d in D]
    Lf = [frozenset(o) for o in L]
    key = {(Df[j], Lf[j]): j for j in range(n)}
    bydet = collections.defaultdict(list)
    for j in range(n):
        for x in D[j]:
            bydet[x].append(j)
    T3, pairs = set(), collections.defaultdict(list)
    for a in range(n):
        nb = set()
        for x in D[a]:
            nb.update(bydet[x])
        for b in nb:
            if b <= a:
                continue
            k = (Df[a] ^ Df[b], Lf[a] ^ Lf[b])
            c = key.get(k)
            if c is not None and c not in (a, b):
                T3.add(tuple(sorted((a, b, c))))
            if kmax >= 4:
                pairs[k].append((a, b))
    T4 = set()
    if kmax >= 4:
        # a trivial 4-set {a,b,c,d}: some pair (a,b) has a detector in common (the set is detector-silent and
        # every column has a detector, so a's detectors are covered by b, c, d); its partner pair (c,d) has the
        # same XOR.  Pairs without a common detector are therefore needed too, as partners: collect them on demand.
        for k, v in pairs.items():
            for (a, b), (c, d) in itertools.combinations(v, 2):
                t = {a, b, c, d}
                if len(t) == 4:
                    T4.add(tuple(sorted(t)))
        # partners without a common detector: (c, d) with D_c ^ D_d = D_a ^ D_b; enumerate c over columns touching
        # the XOR, d by lookup
        for k, v in list(pairs.items()):
            dk, lk = k
            if not dk:
                continue
            for (a, b) in v:
                cand = set()
                for x in dk:
                    cand.update(bydet[x])
                for c in cand:
                    if c in (a, b):
                        continue
                    dd = (dk ^ Df[c], lk ^ Lf[c])
                    d = key.get(dd)
                    if d is not None and d not in (a, b, c):
                        T4.add(tuple(sorted((a, b, c, d))))
    for t in list(T3) + list(T4):
        dd, oo = set(), set()
        for j in t:
            dd ^= set(D[j]); oo ^= set(L[j])
        assert not dd and not oo
    return sorted(T3), sorted(T4)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("W", type=int)
    ap.add_argument("out")
    ap.add_argument("--no-sym", action="store_true")
    ap.add_argument("--no-symcheck", action="store_true")
    ap.add_argument("--blocks", default=None, help="trivial sets recorded by pbdfs -R (one per line: k c1 .. ck)")
    ap.add_argument("--cards", type=int, default=4, help="cardinality constraints for trivial sets up to this size "
                                                          "(0 = none, 3, 4)")
    a = ap.parse_args()
    src = load_source(a.source)
    blocks = []
    if a.blocks:
        for line in open(a.blocks):
            t = list(map(int, line.split()))
            assert t[0] == len(t) - 1
            blocks.append(tuple(t[1:]))
        check_trivial(src, blocks)
    cards = []
    if a.cards >= 3:
        T3, T4 = small_trivial(src["D"], src["L"], a.cards)
        cards = [(1, t) for t in T3] + [(2, t) for t in T4]
    I = build(src, a.W, use_sym=not a.no_sym, blocks=blocks, cards=cards)
    meta = write(I, a.out, check_sym=not a.no_symcheck)
    Path(a.out + ".cols.json").write_text(json.dumps(dict(source=a.source, D=src["D"], L=src["L"],
                                                          ndet=src["ndet"], nobs=src["nobs"])))
    meta["opb_sha256"] = sha(a.out + ".opb")
    meta["source"] = a.source
    Path(a.out + ".json").write_text(json.dumps(meta))
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
