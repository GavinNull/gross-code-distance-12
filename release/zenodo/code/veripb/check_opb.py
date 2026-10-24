"""Semantic check of the shipped OPB files (certificates/veripb/*.opb.gz) against the data files, independent of
code/veripb/build_opb.py: the file encodes exactly "an extended logical of weight <= W that contains none of the listed
logicals" for the extended code of the record.

Checks (all must hold):
  * every constraint has one of five shapes: check row  sum x - sum 2^{k+1} a = 0 ;  logical row
    sum x + q - sum 2^{k+1} b = 0 ;  weight  sum -x >= -W  over ALL columns ;  sum of all q >= 1 ;  clause sum ~x >= 1;
  * auxiliary digits: every a / b variable occurs in exactly one constraint, digit k has coefficient -2^{k+1},
    k = 0..K-1, and 2(2^K - 1) >= row size (+1 for logical rows), so "= 0" <=> even sum (resp. q = parity of the row);
    every q occurs in exactly one logical row and in the sum-q constraint;
  * the multiset of check-row column sets equals the rows of H restricted to the columns of the data file;
  * logical rows: span(file rows) + rowspace(H) == span(L rows of the data file) + rowspace(H) over GF(2), with
    quotient dimension k, so on ker H "some logical row of the file is odd" <=> L x != 0;
  * the blocked clauses are exactly the entries of the record's list files (as column sets), every entry is an
    extended logical; no column has zero H part (so "x contains a blocked set" adds nothing at weights <= W);
  * every translation of the data file's group maps the check rows, logical rows and blocked sets onto themselves.

    python code/veripb/check_opb.py [NAME ...]          (default: every record)
"""
import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
from common_cli import Verdict                    # noqa: E402

DATA = ROOT / "data"
CERT = ROOT / "certificates" / "veripb"
EXTFILE = {"fig12": "extended_code_{b}_memory.json", "bb90": "bb90_extended_code_{b}_memory.json",
           "u11": "u11_extended_code_{b}_memory.json"}
CODEFILE = {"fig12": "gross_code.json", "bb90": "bb90_code.json", "u11": "gross_code.json"}


def rank2(M):
    M = np.array(M, dtype=np.uint8) % 2
    r = 0
    for c in range(M.shape[1]):
        p = np.nonzero(M[r:, c])[0]
        if len(p) == 0:
            continue
        p = p[0] + r
        M[[r, p]] = M[[p, r]]
        for i in np.nonzero(M[:, c])[0]:
            if i != r:
                M[i] ^= M[r]
        r += 1
        if r == M.shape[0]:
            break
    return r


def ext(source, basis):
    code = json.load(open(DATA / "code" / CODEFILE[source]))
    e = json.load(open(DATA / "extended_code" / EXTFILE[source].format(b=basis)))
    n, l, m = code["n"], code["l"], code["m"]
    H = np.zeros((len(code["H" + basis]), n), np.uint8)
    for i, r in enumerate(code["H" + basis]):
        H[i, r] = 1
    L = np.zeros((len(code["L" + basis]), n), np.uint8)
    for i, r in enumerate(code["L" + basis]):
        L[i, r] = 1
    cols = [c["support"] for c in e["columns"]]
    N = len(cols)
    key = lambda s: (H[:, list(s)].sum(1) % 2).tobytes() + (L[:, list(s)].sum(1) % 2).tobytes()  # noqa: E731
    kidx = {key(s): j for j, s in enumerate(cols)}
    assert len(kidx) == N
    Hc = np.array([H[:, s].sum(1) % 2 for s in cols], np.uint8).T
    Lc = np.array([L[:, s].sum(1) % 2 for s in cols], np.uint8).T
    perms = []
    for a, b in e["translation_group"]:
        g = [((i // m + a) % l) * m + (i % m + b) % m for i in range(l * m)]
        g = g + [x + l * m for x in g]
        perms.append([kidx[key([g[q] for q in s])] for s in cols])
    return dict(N=N, Hc=Hc, Lc=Lc, perms=perms, k=int(L.shape[0]))


def parse(path):
    cons, head = [], None
    for line in gzip.open(path, "rt"):
        if line.startswith("*"):
            mm = re.search(r"#variable=\s*(\d+)\s+#constraint=\s*(\d+)", line)
            head = (int(mm.group(1)), int(mm.group(2)))
            continue
        mm = re.fullmatch(r"\s*(.*?)\s*(>=|=)\s*(-?\d+)\s*;\s*", line)
        assert mm, line
        t = mm.group(1).split()
        assert len(t) % 2 == 0
        cons.append(([(int(t[i]), t[i + 1]) for i in range(0, len(t), 2)], mm.group(2), int(mm.group(3))))
    return cons, head


def check(rec):
    E = ext(rec["source"], rec["basis"])
    N, Hc = E["N"], E["Hc"]
    cons, head = parse(CERT / f"{rec['name']}.opb.gz")
    chk, lg, wt, sq, blk = [], [], [], [], []
    occ = Counter()
    for terms, rel, rhs in cons:
        names = [v for _, v in terms]
        assert len(set(names)) == len(names), "repeated literal"
        for v in names:
            occ[v.lstrip("~")] += 1
        xs = [v for v in names if re.fullmatch(r"x\d+", v)]
        if rel == "=":
            assert rhs == 0
            qs = [(c, v) for c, v in terms if v.startswith("q")]
            aux = [(c, v) for c, v in terms if v[0] in "ab"]
            assert all(c == 1 for c, v in terms if v.startswith("x"))
            assert len(xs) + len(qs) + len(aux) == len(terms)
            pref = "b" if qs else "a"
            assert all(v[0] == pref for _, v in aux)
            ks = sorted(int(v.split("_")[1]) for _, v in aux)
            assert ks == list(range(len(aux))) and all(c == -2 ** (int(v.split("_")[1]) + 1) for c, v in aux)
            assert len({v.split("_")[0] for _, v in aux}) == 1
            cap = 2 * (2 ** len(aux) - 1)
            if qs:
                assert len(qs) == 1 and qs[0][0] == 1 and cap >= len(xs) + 1
                lg.append((frozenset(int(v[1:]) - 1 for v in xs), qs[0][1]))
            else:
                assert cap >= len(xs)
                chk.append(frozenset(int(v[1:]) - 1 for v in xs))
        elif all(c == -1 and v.startswith("x") for c, v in terms):
            wt.append((len(terms), -rhs))
        elif all(c == 1 and v.startswith("q") for c, v in terms):
            assert rhs == 1
            sq.append(set(names))
        elif all(c == 1 and v.startswith("~x") for c, v in terms):
            assert rhs == 1
            blk.append(frozenset(int(v[2:]) - 1 for v in names))
        else:
            raise AssertionError("unexpected constraint shape")
    assert head[1] == len(cons)
    for v, c in occ.items():
        assert c == 1 if v[0] in "ab" else (c == 2 if v[0] == "q" else True), v
    assert len(wt) == 1 and wt[0][0] == N and len(sq) == 1 and sq[0] == {q for _, q in lg}
    W = wt[0][1]
    assert {int(v[1:]) - 1 for v in occ if v.startswith("x")} == set(range(N))
    res = {"W": W, "constraints": len(cons)}
    res["check_rows"] = Counter(chk) == Counter(frozenset(np.flatnonzero(Hc[i]).tolist()) for i in range(Hc.shape[0]))
    T = np.zeros((len(lg), N), np.uint8)
    for i, (s, _) in enumerate(lg):
        T[i, list(s)] = 1
    rH = rank2(Hc)
    rT, rM, rTM = rank2(np.vstack([Hc, T])), rank2(np.vstack([Hc, E["Lc"]])), rank2(np.vstack([Hc, T, E["Lc"]]))
    res["logical_span"] = rT == rM == rTM and rTM - rH == E["k"]
    want = set()
    for f in rec["blocks"]:
        for e in json.load(open(ROOT / f))["logicals"]:
            s = frozenset(e["columns"])
            v = np.zeros(N, np.uint8); v[list(s)] = 1
            assert len(s) == len(e["columns"])
            assert not ((Hc.astype(int) @ v) % 2).any() and ((E["Lc"].astype(int) @ v) % 2).any(), "not a logical"
            want.add(s)
    res["blocks"] = set(blk) == want and len(blk) == len(want)
    res["no_zero_H_column"] = int((Hc.sum(0) == 0).sum()) == 0
    cs, ls, bs = Counter(chk), Counter(s for s, _ in lg), set(blk)
    inv = True
    for P in E["perms"]:
        f = lambda s: frozenset(P[j] for j in s)  # noqa: E731
        inv &= Counter(f(s) for s in chk) == cs and Counter(f(s) for s, _ in lg) == ls and {f(s) for s in blk} == bs
    res["invariant"] = bool(inv)
    res["ok"] = all(res[k] for k in ("check_rows", "logical_span", "blocks", "no_zero_H_column", "invariant")) \
        and W == rec["W"]
    return res, len(lg), len(blk), len(E["perms"])


def main():
    recs = {r["name"]: r for r in map(json.loads, open(CERT / "records.jsonl"))}
    names = sys.argv[1:] or list(recs)
    V = Verdict()
    for n in names:
        res, nl, nb, ng = check(recs[n])
        V(res["ok"], f"{n}: OPB = 'extended logical of weight <= {res['W']}' for "
                     f"{EXTFILE[recs[n]['source']].format(b=recs[n]['basis'])}: {res['constraints']} constraints, check "
                     f"rows = H {res['check_rows']}, {nl} logical rows spanning L modulo H {res['logical_span']}, "
                     f"{nb} blocked sets = the record's lists {res['blocks']}, invariant under {ng} translations "
                     f"{res['invariant']}")
    V.exit()


if __name__ == "__main__":
    main()
