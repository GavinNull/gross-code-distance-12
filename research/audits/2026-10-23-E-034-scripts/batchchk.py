"""Auditor: regenerate one E-031 lift batch CNF exactly as liftcert.main writes it, compare its sha256 with the
record, check the selector structure, re-solve with CaDiCaL (binary DRAT), re-check with drat-trim (WITHOUT -w)
and cake_lpr, compare DRAT / LRAT sha256 with the record.  Optional selector-substitution test.

    PYTHONPATH=.:tests uv run python batchchk.py FAMILY SPEC XO ZO BASIS R S K RESULTS.jsonl [--subst CTLSPEC]
--subst: replace three members of the batch by the same-index instances of the control circuit CTLSPEC (which has
the same column set); at least one replaced member must be SAT there; the batch must become SAT and, for each
selector forced true alone, SAT exactly for the replaced members that are SAT on their own.
Output: results/E-034-audit/lift/batchchk.jsonl
"""
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT, ROOT / "tests", ROOT / "search/experiments/e031", ROOT / "search/experiments/e027"):
    sys.path.insert(0, str(p))
import liftcert  # noqa: E402
from lift_cnf import Builder, write  # noqa: E402
from pysat.solvers import Cadical153  # noqa: E402

T = ROOT / "tools"
CAD, DT, CAKE = T / "cadical/build/cadical", T / "drat-trim/drat-trim", T / "cake_lpr/cake_lpr"
W = ROOT / "results/E-034-audit/lift/work"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def build_batch(family, spec, insts, meta, basis, R, s, K):
    circ = Path(spec).stem
    name = f"{circ}_{basis}_R{R}_s{s}of{K}"
    idx = list(range(s, len(insts), K))
    b = Builder()
    sel = [b.new() for _ in idx]
    b.clauses.append(list(sel))
    for t, i in zip(sel, idx):
        liftcert.add_instance(b, insts[i], [-t])
    cmt = [f"lift batch: {circ} ({family}, d_ext={meta['D']}), {basis}-basis memory, R = {R}, "
           f"instances i = {s} mod {K} of {len(insts)} (first {meta['nA']}: weight-{meta['D']} "
           f"list with optional zero-image term; then weight-{meta['D'] + 1} list); "
           f"selectors 1..{len(idx)}; UNSAT iff no instance lifts"]
    return name, idx, b, sel, cmt


def structure(b, sel, nmem):
    selset = set(sel)
    assert b.clauses[0] == list(sel)
    owner = {}
    for c in b.clauses[1:]:
        g = [l for l in c if -l in selset]
        assert len(g) == 1 and c[0] == g[0], "clause without exactly one leading guard"
        assert not any(l in selset for l in c), "positive selector inside a member"
        m = -g[0]
        for l in c[1:]:
            v = abs(l)
            assert owner.setdefault(v, m) == m, "variable shared between members"
    return len({*owner.values()}) == nmem


def main():
    a = sys.argv[1:]
    family, spec, xo, zo, basis, R, s, K, recf = a[:9]
    R, s, K = int(R), int(s), int(K)
    W.mkdir(parents=True, exist_ok=True)
    insts, meta = liftcert.setup(family, spec, xo, zo, R, basis)
    name, idx, b, sel, cmt = build_batch(family, spec, insts, meta, basis, R, s, K)
    rec0 = [json.loads(l) for l in open(recf) if json.loads(l)["name"] == name][-1]
    cnf = W / f"{name}.cnf"
    write(cnf, b, cmt)
    res = {"name": name, "cnf_sha_equal": sha(cnf) == rec0["cnf_sha256"], "members": len(idx),
           "structure_ok": structure(b, sel, len(idx))}
    if "--subst" in a:
        ctl = a[a.index("--subst") + 1]
        cinsts, _ = liftcert.setup(family, ctl, xo, zo, R, basis)
        assert len(cinsts) == len(insts)
        # pick three members whose control instance is SAT
        from lift_cnf import Builder as B2
        def single_sat(inst):
            bb = B2(); liftcert.add_instance(bb, inst, [])
            with Cadical153(bootstrap_with=bb.clauses) as so:
                return so.solve()
        rep = [p for p, i in enumerate(idx) if single_sat(cinsts[i])][:3]
        mod = list(insts)
        for p in rep:
            mod[idx[p]] = cinsts[idx[p]]
        _, _, b2, sel2, _ = build_batch(family, spec, mod, meta, basis, R, s, K)
        with Cadical153(bootstrap_with=b2.clauses) as so:
            batch_sat = so.solve()
            forced = [p for p in range(len(sel2)) if so.solve(assumptions=[sel2[p]])]
        res["subst"] = {"replaced_positions": rep, "batch_sat": batch_sat, "selectors_satisfiable": forced,
                        "ok": batch_sat and forced == rep}
    t0 = time.time()
    drat, lrat = W / f"{name}.drat", W / f"{name}.lrat"
    c = subprocess.run([str(CAD), "-q", "--binary=true", str(cnf), str(drat)], capture_output=True, text=True)
    res["cadical_exit"] = c.returncode
    if c.returncode == 20:
        res["drat_sha_equal"] = sha(drat) == rec0.get("drat_sha256")
        d = subprocess.run([str(DT), str(cnf), str(drat), "-L", str(lrat)], capture_output=True, text=True)
        res["drat_trim"] = "VERIFIED" if any(l.strip() == "s VERIFIED" for l in d.stdout.splitlines()) else "FAILED"
        res["drat_trim_warnings"] = sum("WARNING" in l for l in d.stdout.splitlines())
        res["lrat_sha_equal"] = sha(lrat) == rec0.get("lrat_sha256")
        k = subprocess.run([str(CAKE), str(cnf), str(lrat)], capture_output=True, text=True)
        res["cake_lpr"] = "VERIFIED UNSAT" if any(l.strip() == "s VERIFIED UNSAT" for l in k.stdout.splitlines()) else "FAILED"
        drat.unlink(); lrat.unlink()
    cnf.unlink()
    res["sec"] = round(time.time() - t0, 1)
    print(json.dumps(res), flush=True)
    with open(ROOT / "results/E-034-audit/lift/batchchk.jsonl", "a") as f:
        f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
