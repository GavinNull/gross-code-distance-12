"""Regenerate one lift batch CNF exactly as run_lift_certs.py writes it, compare its sha256 with the shipped record,
and check its selector/disjunction structure directly on the DIMACS text:
  1. clause 1 is (t_1 v ... v t_m) with t_j = j;
  2. every other clause has exactly one selector literal, and it is negative;
  3. the clause groups of different selectors use pairwise disjoint (non-selector) variables;
  4. member j, with its guard removed and variables renumbered canonically, is literally the single-instance CNF of
     logical idx[j] (code/proofs/lift_cnf.py 'single'), so batch UNSAT => each listed logical's instance UNSAT.
Optionally (--keep PATH) leaves the CNF on disk for proof checking.

    python batch_struct.py CIRCUIT BASIS R S K [--keep OUT.cnf]
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "release/zenodo/code/proofs"))
import lift_cnf as LC   # noqa: E402


def canon(clauses):
    ren = {}
    out = []
    for c in clauses:
        cc = []
        for l in c:
            v = abs(l)
            if v not in ren:
                ren[v] = len(ren) + 1
            cc.append(ren[v] if l > 0 else -ren[v])
        out.append(tuple(cc))
    return out


def main(a):
    circ, basis, R, s, K = a[0], a[1], int(a[2]), int(a[3]), int(a[4])
    lists, groups, st = LC.setup(circ, basis, R)
    idx = list(range(s, len(lists), K))
    b = LC.batch(lists, groups, idx)
    name = f"{circ}_{basis}_R{R}_s{s}of{K}"
    out = Path(a[a.index("--keep") + 1]) if "--keep" in a else None
    text_comment = [f"lift batch: circuit {circ}, {basis}-basis memory, R = {R}, weight-11 logicals i = {s} mod "
                    f"{K} ({len(idx)} instances); selector variables 1..{len(idx)}; UNSAT iff no instance lifts"]
    h = hashlib.sha256()
    body = "".join(f"c {c}\n" for c in text_comment) + f"p cnf {b.n} {len(b.clauses)}\n" + \
        "".join(" ".join(map(str, c)) + " 0\n" for c in b.clauses)
    h.update(body.encode())
    if out:
        out.write_text(body)
    rec = {json.loads(l)["name"]: json.loads(l) for l in
           open(ROOT / f"release/zenodo/certificates/proofs/lift_circuit_{circ}.jsonl")}[name]
    m = len(idx)
    cl = b.clauses
    res = dict(name=name, sha_match=h.hexdigest() == rec["cnf_sha256"], vars=b.n, clauses=len(cl),
               rec_vars=rec["vars"], rec_clauses=rec["clauses"])
    res["first_clause_is_selector_or"] = cl[0] == list(range(1, m + 1))
    bad_guard = 0
    members = [[] for _ in range(m)]
    for c in cl[1:]:
        sel = [l for l in c if abs(l) <= m]
        if len(sel) != 1 or sel[0] > 0:
            bad_guard += 1
            continue
        members[-sel[0] - 1].append([l for l in c if abs(l) > m])
    res["clauses_with_bad_guard"] = bad_guard
    owner = {}
    shared = 0
    for j, mc in enumerate(members):
        for c in mc:
            for l in c:
                o = owner.setdefault(abs(l), j)
                shared += o != j
    res["vars_shared_between_members"] = shared
    eq = 0
    for j, i in enumerate(idx):
        sb = LC.Builder()
        sb.instance(lists[i], groups, [])
        eq += canon(sb.clauses) == canon(members[j])
    res["members_equal_single_instance"] = f"{eq}/{m}"
    res["logicals"] = [idx[0], idx[-1], m]
    print(json.dumps(res), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
