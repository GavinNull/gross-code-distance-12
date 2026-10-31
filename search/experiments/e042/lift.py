"""E-042: DRAT certificates (CaDiCaL -> drat-trim -> cake_lpr) that no item of the complete g10 lists lifts at R*.

Lift question (generalised Lemma 2, identical to e031/liftcert.py): for each memory basis,
  (a) each weight-10 extended logical S of the list (3,204): one DEM mechanism per column of S (the mechanisms whose
      image is that column) and AT MOST ONE extra zero-image mechanism (only those whose detectors lie in the union
      of the groups' supports: any other one cannot be cancelled), all detectors even;
  (b) each weight-11 extended logical S (121,104): one mechanism per column, all detectors even.
Groups come from the audited e032 code (lift.build_groups on the evaluator's SD6 stim DEM augmented with the H and
L rows as observables on the final data readout; every DEM term's image is 0 or an extended column, asserted).
The extended code is e032.common.ext_general of this circuit's own per-check orders (lift.label_orders).
The CNF of one instance and the selector batching are e031/liftcert.add_instance and e027/lift_cnf, unchanged
(imported).  Every list item is used (no orbit reduction).

R = R* = 13 (rstar.py + bulk compression lemma, journal Sec. 2): "no lift at R*" => "no bulk lift" (Theorem 4).

    uv run python -m search.experiments.e042.lift run   R OUTDIR [--bases Z X] [--spec SPEC] [--batch N]
    uv run python -m search.experiments.e042.lift ctl   R OUTDIR       # positive control (segmented timing; SAT)
Records: OUTDIR/results.jsonl, one line per batch (finished batches are skipped on restart).  A batch passes iff
CaDiCaL UNSAT, drat-trim "s VERIFIED" and cake_lpr "s VERIFIED UNSAT".
"""
from __future__ import annotations

import hashlib
import json
import math
import pickle
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in (str(ROOT), str(ROOT / "tests"), str(ROOT / "search/experiments/e031"), str(ROOT / "search/experiments/e027")):
    if p not in sys.path:
        sys.path.insert(0, p)

SPEC = "search/experiments/e040/g10_d12_spec.json"
LISTS = ROOT / "results/E-040-min-period"
TYPE = "A1A2B1A3B2B3"            # E-040 files are named by the order type representative (audit Sec. 2)
AUDIT = ROOT / "results/E-040-audit-circ"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def list_files(kind):
    return LISTS / f"list_gross_{kind}_{TYPE}.pkl", LISTS / f"list11_gross_{kind}_{TYPE}.pkl"


def load_lists(E, kind, basis, crosscheck=True):
    from search.experiments.e032 import lift as L
    f10, f11 = list_files(kind)
    k10 = pickle.load(open(f10, "rb"))["keys"]
    k11 = pickle.load(open(f11, "rb"))["keys"]
    s10, cs = L.reindex(E, k10)
    s11, _ = L.reindex(E, k11)
    assert len(set(s10)) == len(s10) == 3204 and len(set(s11)) == len(s11) == 121104
    assert all(len(set(S)) == 10 for S in s10) and all(len(set(S)) == 11 for S in s11)
    info = {"w10_file": str(f10.relative_to(ROOT)), "w10_sha256": sha(f10), "w11_file": str(f11.relative_to(ROOT)),
            "w11_sha256": sha(f11)}
    if crosscheck:     # the audit's independent enumeration (by basis): set-equal
        for w, mine in ((10, s10), (11, s11)):
            a = pickle.load(open(AUDIT / f"list_g10_{basis}_w{w}.pkl", "rb"))
            sa, _ = L.reindex(E, a["keys"])
            assert {frozenset(x) for x in sa} == {frozenset(x) for x in mine}, f"audit list w{w} differs"
            assert frozenset(a["colset"]) == cs, "audit column set differs"
        info["audit_lists_set_equal"] = True
    return s10, s11, info


def setup(spec_path, R, basis, lists_from=None):
    from evaluators.candidate import parse_schedule
    from search.experiments.e032 import common as C
    from search.experiments.e032 import lift as L
    spec = parse_schedule(json.loads((ROOT / spec_path).read_text())).canonical()
    lo = L.label_orders(spec)
    kind = L.KIND_OF_BASIS[basis]
    E = C.ext_general(kind, lo[kind], group=[(0, 0)])
    if lists_from is None:
        sA, sB, info = load_lists(E, kind, basis)
    else:
        sA, sB, info = lists_from(E, kind, basis)
    zeros = set()
    groups, st = L.build_groups(spec, R, basis, E, zeros=zeros)
    insts = []
    for S in sA:
        sup = 0
        for j in S:
            for m in groups[j]:
                sup |= m
        z = sorted(m for m in zeros if m and m & ~sup == 0)
        insts.append(([list(dict.fromkeys(groups[j])) for j in S], z))
    for S in sB:
        insts.append(([list(dict.fromkeys(groups[j])) for j in S], []))
    meta = {"nA": len(sA), "nB": len(sB), "zero_terms": len(zeros), "ext_columns": int(E["N"]), **info,
            **{k: v for k, v in st.items() if isinstance(v, (int, float, str))}}
    return insts, meta


def self_cpu():
    r = resource.getrusage(resource.RUSAGE_SELF)
    return r.ru_utime + r.ru_stime


def run(R, outdir, bases=("Z", "X"), spec=SPEC, bsize=None, expect="unsat", lists_from=None, only=None, tag=None):
    import certify as CE                 # e027/certify.py
    from liftcert import add_instance    # e031/liftcert.py (unchanged)
    from lift_cnf import Builder, write  # e027/lift_cnf.py
    CE.CADICAL = str(ROOT / "tools/cadical/build/cadical")
    CE.DRAT_TRIM = str(ROOT / "tools/drat-trim/drat-trim")
    CE.CAKE_LPR = str(ROOT / "tools/cake_lpr/cake_lpr")
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    res = outdir / "results.jsonl"
    done = {json.loads(l)["name"] for l in res.open()} if res.exists() else set()
    circ = tag or Path(spec).stem
    allok = True
    for basis in bases:
        c0 = self_cpu()
        insts, meta = setup(spec, R, basis, lists_from)
        if only is not None:
            insts = [insts[i] for i in only]
        meta["setup_cpu_s"] = round(self_cpu() - c0, 1)
        print(json.dumps({"basis": basis, "R": R, **meta}), flush=True)
        per = bsize or min(1500, max(50, 13000 // R))
        K = max(1, math.ceil(len(insts) / per))
        for s in range(K):
            name = f"{circ}_{basis}_R{R}_s{s}of{K}"
            if name in done:
                continue
            c1 = self_cpu()
            idx = list(range(s, len(insts), K))
            b = Builder()
            sel = [b.new() for _ in idx]
            b.clauses.append(list(sel))
            for t, i in zip(sel, idx):
                add_instance(b, insts[i], [-t])
            cnf = outdir / "tmp" / f"{name}.cnf"
            cnf.parent.mkdir(parents=True, exist_ok=True)
            write(cnf, b, [f"E-042 lift batch: {circ}, {basis}-basis memory, R = {R}, instances i = {s} mod {K} of "
                           f"{len(insts)} (first {meta['nA']}: weight-10 list with optional zero-image term; then "
                           f"weight-11 list); selectors 1..{len(idx)}; UNSAT iff no instance lifts"])
            gen = self_cpu() - c1
            rec = CE.certify(cnf, outdir / "work", name, timeout=7200, keep=False)
            cnf.unlink()
            rec.update(circuit=circ, basis=basis, R=R, split=[s, K], instances=len(idx), gen_cpu_s=round(gen, 1),
                       first_index=idx[0], dem=meta, end=time.strftime("%Y-%m-%dT%H:%M:%S"))
            if expect == "sat":
                rec["ok"] = rec["solver"]["answer"] == "SAT"
            else:
                rec["ok"] = rec["ok"] and rec.get("cake_lpr", {}).get("verdict") == "VERIFIED UNSAT"
            with open(res, "a") as f:
                f.write(json.dumps(rec) + "\n")
            print(("PASS" if rec["ok"] else "FAIL"), name, rec.get("clauses"), rec["solver"]["answer"],
                  rec["solver"]["cpu_s"], rec.get("drat_trim", {}).get("verdict"),
                  rec.get("cake_lpr", {}).get("verdict"), flush=True)
            allok &= rec["ok"]
    print("ALL PASS" if allok else "SOME FAILED", flush=True)
    return allok


def ctl(R, outdir):
    """Positive control: same per-check orders, separable timing (period 16; audit ctl.seg).  Theory-B Prop. 3(c):
    every extended logical lifts for every R, so every batch must be SAT.  Spot check: 6 batches per basis of single
    instances (3 from each list) plus one batch of 200 items."""
    from evaluators import candidate as cand
    from search.experiments.e040_audit_circ.ctl import seg
    from search.theory.B_audit.common import get_code
    sd = seg(json.loads((ROOT / SPEC).read_text()))
    assert not cand.validate_schedule(cand.parse_schedule(sd), get_code("gross"))
    p = (ROOT / outdir / "segctl_g10.json").resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sd))
    sp = str(p.relative_to(ROOT))
    picks = [0, 1601, 3203, 3204, 3204 + 60551, 3204 + 121103]
    ok = True
    for i in picks:
        ok &= run(R, outdir, spec=sp, bsize=1, expect="sat", only=[i], tag=f"segctl_i{i}")
    ok &= run(R, outdir, spec=sp, bsize=200, expect="sat", only=list(range(0, 124308, 621))[:200], tag="segctl_b200")
    return ok


if __name__ == "__main__":
    a = sys.argv[1:]
    mode, R, outdir = a[0], int(a[1]), a[2]
    bases = ["Z", "X"]
    if "--bases" in a:
        i = a.index("--bases") + 1; bases = []
        while i < len(a) and not a[i].startswith("--"):
            bases.append(a[i]); i += 1
    spec = a[a.index("--spec") + 1] if "--spec" in a else SPEC
    bsize = int(a[a.index("--batch") + 1]) if "--batch" in a else None
    if mode == "run":
        sys.exit(0 if run(R, outdir, bases, spec, bsize) else 1)
    elif mode == "ctl":
        sys.exit(0 if ctl(R, outdir) else 1)
