"""E-042 audit copy (2026-11-01) of the E-031/E-034 auditor semcheck, extended with source g10 and with block lists
given as key pickles (the E-040 auditor's independent enumeration), mapped through MY column keys.

Auditor: semantic check of an E-031 OPB file against the auditor's own extended code (alib.py).

    uv run python semcheck.py SOURCE BASIS OPB [LIST.json ...]      SOURCE in bb90, u11, fig12

Checks (all must hold; prints one JSON line, appends to results/E-042-audit/semcheck.jsonl):
  * every constraint is of one of five shapes: check row  sum x - sum 2^{k+1} a = 0 ;  logical row
    sum x + q - sum 2^{k+1} b = 0 ;  weight  sum -x >= -W  over ALL columns ;  sum_all q >= 1 ;  clause sum ~x >= 1;
  * aux digits: every a/b variable occurs in exactly one constraint, digit k has coefficient -2^{k+1}, k = 0..K-1,
    and 2(2^K - 1) >= row size (+1 for logical rows), so "= 0" <=> even sum (resp. q = parity);
    every q occurs in exactly one logical row and in the sum-q constraint;
  * multiset of check-row column sets == rows of the own Hc (own columns from the circuit file);
  * logical rows: span(theirs) + rowspace(Hc) == span(own L rows) + rowspace(Hc) over GF(2), and the quotient has
    dimension k (so on ker Hc: some row of theirs odd <=> L x != 0);
  * blocked clauses == the given lists exactly (as column sets), each list entry is a logical of the stated weight;
    no column has zero H part (so blocking supersets is the same as blocking the sets at weights <= min|B| + 1);
  * invariance: every translation maps the check-row sets, the logical-row sets and the blocked sets onto themselves.
"""
import json
import re
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, __import__("os").path.dirname(__file__))
from alib import DATA, ROOT, col_vec, ext_code, rank2  # noqa: E402

SRC = {"bb90": ("bb90", DATA / "circuits/bb90_c16.json", lambda b: DATA / f"extended_code/bb90_extended_code_{b}_memory.json"),
       "fig12": ("gross", DATA / "circuits/fig12.json", lambda b: DATA / f"extended_code/extended_code_{b}_memory.json"),
       "u11": ("gross", ROOT / "search/experiments/e032/u11_spec.json", lambda b: None),
       "g10": ("gross", ROOT / "search/experiments/e040/g10_d12_spec.json", lambda b: None)}


def parse(path):
    cons = []
    nhead = None
    for line in open(path):
        if line.startswith("*"):
            m = re.search(r"#variable=\s*(\d+)\s+#constraint=\s*(\d+)", line)
            nhead = (int(m.group(1)), int(m.group(2)))
            continue
        m = re.fullmatch(r"\s*(.*?)\s*(>=|=)\s*(-?\d+)\s*;\s*", line)
        assert m, line
        t = m.group(1).split()
        assert len(t) % 2 == 0
        cons.append(([(int(t[i]), t[i + 1]) for i in range(0, len(t), 2)], m.group(2), int(m.group(3))))
    return cons, nhead


def evalkeys(E):
    """evaluator-convention key of each of my columns (H, L from the evaluator code via the B_audit loader, which
    builds the code from the task definition -- not from E-042 code) -> my column's own key."""
    sys.path.insert(0, str(ROOT))
    from search.theory.B_audit.common import get_code
    c = get_code("gross")
    H = (np.asarray(c.HZ if E["basis"] == "Z" else c.HX) % 2).astype(np.uint8)
    L = (np.asarray(c.LZ if E["basis"] == "Z" else c.LX) % 2).astype(np.uint8)
    out = {}
    for S in E["cols"]:
        v = np.zeros(H.shape[1], dtype=np.int64); v[list(S)] = 1
        k = (H.astype(np.int64) @ v % 2).astype(np.uint8).tobytes() + (L.astype(np.int64) @ v % 2).astype(np.uint8).tobytes()
        assert k not in out
        out[k] = E["key"](S)
    return out


def main():
    src, basis, opb = sys.argv[1:4]
    lists = sys.argv[4:]
    code, spec, rel = SRC[src]
    if src in ("u11", "g10"):      # E-031/E-032 name u11 sides by hook kind: kind X = Z-basis memory, kind Z = X-basis memory
        basis = {"X": "Z", "Z": "X"}[basis]
    E = ext_code(code, spec, basis, rel(basis))
    E["basis"] = basis
    N, Hc = E["N"], E["Hc"]
    cons, head = parse(opb)
    chk, lg, wt, sq, blk = [], [], [], [], []
    occ = Counter()
    for terms, rel_, rhs in cons:
        names = [v for _, v in terms]
        assert len(set(names)) == len(names), "repeated literal"
        for v in names:
            occ[v.lstrip("~")] += 1
        xs = [v for v in names if re.fullmatch(r"x\d+", v)]
        if rel_ == "=":
            assert rhs == 0
            qs = [(c, v) for c, v in terms if v.startswith("q")]
            aux = [(c, v) for c, v in terms if v[0] in "ab"]
            assert all(c == 1 for c, v in terms if v.startswith("x"))
            assert len(xs) + len(qs) + len(aux) == len(terms)
            pref = "b" if qs else "a"
            assert all(v[0] == pref for _, v in aux)
            ks = sorted(int(v.split("_")[1]) for _, v in aux)
            assert ks == list(range(len(aux))) and all(c == -2 ** (int(v.split("_")[1]) + 1) for c, v in aux)
            base = {v.split("_")[0] for _, v in aux}
            assert len(base) == 1
            K = len(aux)
            cap = 2 * (2 ** K - 1)
            if qs:
                assert len(qs) == 1 and qs[0][0] == 1
                assert cap >= len(xs) + 1
                lg.append((frozenset(int(v[1:]) - 1 for v in xs), qs[0][1]))
            else:
                assert cap >= len(xs)
                chk.append(frozenset(int(v[1:]) - 1 for v in xs))
        else:
            if all(c == -1 and v.startswith("x") for c, v in terms):
                wt.append((len(terms), -rhs))
            elif all(c == 1 and v.startswith("q") for c, v in terms):
                assert rhs == 1
                sq.append(set(names))
            elif all(c == 1 and v.startswith("~x") for c, v in terms):
                assert rhs == 1
                blk.append(frozenset(int(v[2:]) - 1 for v in names))
            else:
                raise AssertionError("unexpected constraint shape")
    res = {"opb": opb, "constraints": len(cons), "header": head}
    assert head[1] == len(cons)
    # aux uniqueness
    for v, c in occ.items():
        if v[0] in "ab":
            assert c == 1, v
        if v[0] == "q":
            assert c == 2, v
    assert len(wt) == 1 and wt[0][0] == N and len(sq) == 1
    W = wt[0][1]
    assert sq[0] == {q for _, q in lg}
    allx = {int(v[1:]) - 1 for v in occ if v.startswith("x")}
    assert allx == set(range(N))
    # check rows
    mine = Counter(frozenset(np.flatnonzero(Hc[i]).tolist()) for i in range(Hc.shape[0]))
    res["check_rows_equal"] = Counter(chk) == mine
    # logical rows: span equality modulo rowspace(Hc)
    T = np.zeros((len(lg), N), dtype=np.uint8)
    for i, (s, _) in enumerate(lg):
        T[i, list(s)] = 1
    Lmine = np.array([col_vec(E, r) for r in E["L"]], dtype=np.uint8)
    rH = rank2(Hc)
    rT, rM, rTM = rank2(np.vstack([Hc, T])), rank2(np.vstack([Hc, Lmine])), rank2(np.vstack([Hc, T, Lmine]))
    res["logical_rows"] = len(lg)
    res["logical_span_equal"] = rT == rM == rTM
    res["logical_quotient_dim"] = rTM - rH
    res["k"] = int(E["L"].shape[0])
    # blocks
    want = set()
    import pickle
    def entries(f):
        if f.endswith(".pkl"):          # keys (H||L bytes, evaluator matrices) -> my numbering via my own H, L
            for S in pickle.load(open(f, "rb"))["keys"]:
                yield [E["keys"][keyconv(k)] for k in S]
        else:
            for e in json.load(open(f))["logicals"]:
                yield e["columns"]
    def keyconv(k):
        # list keys are (HZ s, LZ s) with the evaluator's L; map via the support-free route: find my column with the
        # same H part and an L part equal modulo nothing -> require exact match on H, then match L via a column table
        return KEYMAP[k]
    KEYMAP = {}
    for f in lists:
        if f.endswith(".pkl"):
            KEYMAP.update(evalkeys(E))
            break
    for f in lists:
        for cols_ in entries(f):
            e = {"columns": cols_}
            s = frozenset(e["columns"])
            v = np.zeros(N, dtype=np.uint8); v[list(s)] = 1
            assert not (Hc.astype(int) @ v % 2).any() and (Lmine.astype(int) @ v % 2).any(), "list entry not a logical"
            assert len(s) == len(e["columns"])
            want.add(s)
    res["blocks"] = len(blk)
    res["blocks_equal_lists"] = set(blk) == want and len(blk) == len(set(blk))
    res["min_block_weight"] = min((len(b) for b in blk), default=None)
    res["zero_H_columns"] = int((Hc.sum(0) == 0).sum())
    # invariance
    inv = True
    cs, ls, bs = Counter(chk), Counter(s for s, _ in lg), set(blk)
    for P in E["perms"]:
        f = lambda s: frozenset(int(P[j]) for j in s)
        inv &= Counter(f(s) for s in chk) == cs and Counter(f(s) for s, _ in lg) == ls and {f(s) for s in blk} == bs
    res["group_order"] = len(E["perms"])
    res["invariant"] = bool(inv)
    res["W"] = W
    res["N"] = N
    res["ok"] = bool(res["check_rows_equal"] and res["logical_span_equal"] and res["logical_quotient_dim"] == res["k"]
                     and res["blocks_equal_lists"] and res["zero_H_columns"] == 0 and inv)
    print(json.dumps(res))
    with open(ROOT / "results/E-042-audit/semcheck.jsonl", "a") as fh:
        fh.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
