"""E-037 audit: does a certified OPB instance encode MY DEM, and is every extra constraint justified?

  uv run python search/experiments/e037_audit/opb_audit.py OPB SRC W [--runs RUNS.jsonl]

Checks (every constraint of the file must fall in exactly one class, otherwise FAIL):
  parity rows  sum x_j - sum_k 2^{k+1} a_{r,k} = 0      -> detector rows; the family of column detector sets read off
               these rows must equal my DEM's (bijection OPB var -> my column); capacity 2(2^K-1) >= row length
  logical rows sum x_j + q_l - sum_k 2^{k+1} b_{l,k} = 0 -> span(D, these rows) == span(D, my observables)
  weight row   sum -x_j >= -W over ALL x, W as claimed;  q row  sum q_l >= 1 over ALL q of logical rows
  card         sum -x_j >= -b  with T detector-silent and logically trivial in my DEM, b >= floor(|T|/2)
  block        sum ~x_j >= 1   with T nonempty, detector-silent, logically trivial in my DEM
  SB           H1 ~x_j v h_o (exactly one per column), E2 ~e_o v e_{o-1} v h_{o-1}, SB ~h_o v e_o v x_rep
               (o = 1: ~h_1 v x_rep): the classes {j : H1(j) = o} must be exactly the orbits of MY translation group
               (run_mincc.group), rep in its class, E2 for every o >= 2 with the consecutive numbering
  every auxiliary variable (a, b, q, h, e) occurs only where its class says
Also: sha256 of the OPB equals the opb_sha256 recorded in runs.jsonl for this instance (if --runs given).
"""
import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import mydem
from run_mincc import group

TOK = re.compile(r"(-?\d+)\s+(~?)([a-z]+)(\d+)(?:_(\d+))?")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def parse(line):
    line = line.strip()
    assert line.endswith(";"), line[:80]
    m = re.match(r"^(.*?)\s*(=|>=)\s*(-?\d+)\s*;$", line)
    body, rel, rhs = m.group(1), m.group(2), int(m.group(3))
    terms = []
    pos = 0
    for t in TOK.finditer(body):
        assert body[pos:t.start()].strip() == "", body[pos:t.start()]
        pos = t.end()
        c, neg, v, i, k = t.groups()
        terms.append((int(c), neg == "~", v, int(i), None if k is None else int(k)))
    assert body[pos:].strip() == ""
    return terms, rel, rhs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("opb"); ap.add_argument("src"); ap.add_argument("W", type=int)
    ap.add_argument("--runs", default=None)
    a = ap.parse_args()
    out = dict(opb=a.opb, src=a.src, W=a.W)
    if a.runs:
        name = Path(a.opb).stem
        recs = [json.loads(l) for l in open(a.runs) if json.loads(l).get("name") == name and json.loads(l).get("ok")]
        assert recs, "no ok record"
        out["sha_match"] = recs[-1]["opb_sha256"] == sha(a.opb)
    src = mydem.load(a.src)
    D, L = src["D"], src["L"]
    n = len(D)
    my_index = {tuple(d): j for j, d in enumerate(D)}
    det_rows = {}       # r -> list of x vars
    log_rows = {}       # l -> list of x vars
    aux_use = defaultdict(int)
    weight = qrow = None
    cards, blocks, h1, e2, sbc = [], [], {}, {}, {}
    other = 0
    with open(a.opb) as f:
        for ln in f:
            if ln.startswith("*") or not ln.strip():
                continue
            terms, rel, rhs = parse(ln)
            vs = {t[2] for t in terms}
            for c, neg, v, i, k in terms:
                if v != "x":
                    aux_use[(v, i, k)] += 1
            if rel == "=":
                assert rhs == 0
                xs = [i for c, neg, v, i, k in terms if v == "x"]
                assert all(c == 1 and not neg for c, neg, v, i, k in terms if v in ("x", "q"))
                aux = [(c, v, i, k) for c, neg, v, i, k in terms if v in ("a", "b")]
                assert all(not neg for c, neg, v, i, k in terms)
                rid = {i for c, v, i, k in aux}
                assert len(rid) == 1 and len({v for c, v, i, k in aux}) == 1
                r = rid.pop()
                K = len(aux)
                assert sorted((k, c) for c, v, i, k in aux) == [(kk, -(2 ** (kk + 1))) for kk in range(K)]
                assert 2 * (2 ** K - 1) >= len(xs) + (1 if "q" in vs else 0), "aux capacity"
                assert len(set(xs)) == len(xs)
                if aux[0][1] == "a":
                    assert vs <= {"x", "a"}       # rows of never-firing detectors (last noiseless cycle) are "aux = 0"
                    assert r not in det_rows
                    det_rows[r] = xs
                else:
                    qs = [i for c, neg, v, i, k in terms if v == "q"]
                    assert vs == {"x", "q", "b"} and qs == [r]
                    log_rows[r] = xs
                continue
            # >=
            if vs == {"x"} and all(c == -1 and not neg for c, neg, v, i, k in terms):
                xs = sorted(i for _, _, _, i, _ in terms)
                if len(xs) == n and rhs == -a.W and weight is None and xs == list(range(1, n + 1)):
                    weight = True
                else:
                    cards.append((-rhs, xs))
                continue
            if vs == {"q"}:
                assert rhs == 1 and all(c == 1 and not neg for c, neg, v, i, k in terms) and qrow is None
                qrow = sorted(i for _, _, _, i, _ in terms)
                continue
            if vs == {"x"} and all(c == 1 and neg for c, neg, v, i, k in terms) and rhs == 1:
                blocks.append(sorted(i for _, _, _, i, _ in terms))
                continue
            # SB family: clauses (all coef 1, rhs 1)
            assert rhs == 1 and all(c == 1 for c, *_ in terms), ("unclassified", ln[:120])
            lits = [(neg, v, i) for c, neg, v, i, k in terms]
            if len(lits) == 2 and (True, "x", lits[0][2]) == lits[0] and lits[1][:2] == (False, "h"):
                j = lits[0][2]; assert j not in h1; h1[j] = lits[1][2]; continue
            ne = [t for t in lits if t[0] and t[1] == "e"]
            nh = [t for t in lits if t[0] and t[1] == "h"]
            if len(ne) == 1 and not nh:
                o = ne[0][2]
                rest = sorted((v, i) for neg, v, i in lits if not neg)
                exp = sorted([("h", o - 1)] + ([("e", o - 1)] if o > 2 else []))
                assert rest == exp and all(not neg for neg, v, i in lits if (v, i) != ("e", o)), ("bad E2", ln[:120])
                assert o not in e2; e2[o] = True; continue
            if len(nh) == 1 and not ne:
                o = nh[0][2]
                rest = [(neg, v, i) for neg, v, i in lits if (v, i) != ("h", o)]
                xs = [i for neg, v, i in rest if v == "x" and not neg]
                es = [i for neg, v, i in rest if v == "e" and not neg]
                assert len(xs) == 1 and len(rest) == (1 if o == 1 else 2) and (o == 1 or es == [o]), ("bad SB", ln[:120])
                assert o not in sbc; sbc[o] = xs[0]; continue
            raise AssertionError(("unclassified", ln[:120]))
    out.update(ndet_rows=len(det_rows), nlog_rows=len(log_rows), ncards=len(cards), nblocks=len(blocks),
               nH1=len(h1), nE2=len(e2), nSB=len(sbc))
    assert weight and qrow is not None
    assert sorted(qrow) == sorted(log_rows), "q row does not cover exactly the logical rows"
    # aux usage: a,b once; q twice (its row + q row); h: H1 members + E2 (next) + SB; e: E2 (own, next) + SB
    for (v, i, k), c in aux_use.items():
        if v in ("a", "b"):
            assert c == 1, ("aux reused", v, i, k)
        elif v == "q":
            assert c == 2, ("q reused", i)
    # detector rows -> column detector sets (rows indexed r-1 = detector index)
    assert sorted(det_rows) == list(range(1, src["ndet"] + 1)), "detector row count"
    coldet = defaultdict(list)
    for r, xs in det_rows.items():
        for x in xs:
            coldet[x].append(r - 1)
    assert sorted(coldet) == list(range(1, n + 1)), "some x var in no detector row / var count differs"
    mp = {}
    for x, ds in coldet.items():
        t = tuple(sorted(ds))
        assert t in my_index, ("OPB column not in my DEM", x)
        mp[x] = my_index[t]
    assert len(set(mp.values())) == n, "not a bijection"
    out["detectors_match"] = True
    # logical rows modulo detectors
    Drows = mydem.rows_from(D, src["ndet"])
    Lmine = mydem.rows_from(L, src["nobs"])
    Lopb = []
    for r in sorted(log_rows):
        v = 0
        for x in log_rows[r]:
            v |= 1 << mp[x]
        Lopb.append(v)
    ok, rk = mydem.same_logicals_mod_det(Drows, Lmine, Lopb)
    assert ok, ("logical rows not equivalent", rk)
    out["logicals_equiv"] = rk

    def trivial(xs):
        dd, oo = set(), set()
        for x in xs:
            j = mp[x]
            dd ^= set(D[j]); oo ^= set(L[j])
        return not dd and not oo
    nbad_c = sum(1 for b, xs in cards if not (trivial(xs) and b >= len(xs) // 2 and len(set(xs)) == len(xs)))
    nbad_b = sum(1 for xs in blocks if not (xs and trivial(xs)))
    out.update(cards_bad=nbad_c, blocks_bad=nbad_b,
               card_sizes=sorted({len(xs) for b, xs in cards}), block_sizes=sorted({len(xs) for xs in blocks}),
               max_block=max((len(x) for x in blocks), default=0))
    assert nbad_c == 0 and nbad_b == 0
    # symmetry breaking
    if h1:
        assert sorted(h1) == list(range(1, n + 1)), "H1 not exactly one per column"
        cls = defaultdict(set)
        for x, o in h1.items():
            cls[o].add(mp[x])
        no = len(cls)
        assert sorted(cls) == list(range(1, no + 1))
        assert sorted(e2) == list(range(2, no + 1)), "E2 chain incomplete"
        assert sorted(sbc) == list(range(1, no + 1)), "SB per class"
        perms = group(src)
        for o, members in cls.items():
            rep = mp[sbc[o]]
            assert rep in members, ("rep not in class", o)
            orbit = {P[rep] for P in perms}
            assert orbit == members, ("class is not an orbit of my group", o, len(orbit), len(members))
        out.update(sym_classes=no, group=len(perms), classes_are_orbits=True)
        for (v, i, k), c in aux_use.items():
            if v == "h":
                assert c == len(cls[i]) + 1 + (1 if i < no else 0), ("h used elsewhere", i, c)
            if v == "e":
                assert c == 1 + 1 + (1 if i < no else 0), ("e used elsewhere", i, c)
    out["verdict"] = "OK"
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
