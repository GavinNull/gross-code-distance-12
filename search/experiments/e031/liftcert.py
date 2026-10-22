"""E-031 part 3: DRAT certificates (CaDiCaL -> drat-trim -> cake_lpr, E-027 pipeline) for the extended lift of
circuits whose side has d_ext = D (D = 8: [[90]] c16/c13/c11 via E-028; D = 10: gross u11 via E-032).

Lift question (generalised Lemma 2, E-028/E-032 journals): an undetected logical of weight D or D+1 exists in the
R-round SD6 circuit iff one of
  (a) a weight-D extended logical S: one DEM mechanism per column of S (mechanisms with that image) and AT MOST ONE
      extra zero-image mechanism (only those whose detectors lie in the union of the groups' supports, as in
      lift9/lift10: any other one cannot be cancelled), all detectors even;   [covers |F| = D and D + zero term]
  (b) a weight-(D+1) extended logical S: one mechanism per column, all detectors even
has a solution.  Groups are built by the audited E-028/E-032 code (lift.build_groups on the augmented stim DEM).
CNF exactly as e027/lift_cnf.py (one variable per distinct detector mask of a group, exactly-one per column group,
at-most-one for the zero group, Tseitin XOR chains per detector), instances of one (circuit, basis, R) batched by
selectors: (t_1 v ... v t_m), every clause of instance i guarded by -t_i.  Batch UNSAT <=> no instance lifts.

    PYTHONPATH=.:tests uv run python search/experiments/e031/liftcert.py FAMILY SPEC XO ZO RANGE OUTDIR
        [--bases Z X] [--batch N] [--expect sat] [--no-cake]
FAMILY e028 (D = 8) or e032 (D = 10).  Records: OUTDIR/results.jsonl (finished batches are skipped on restart).
"""
import importlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "search" / "experiments" / "e027"))
import certify as CE                     # noqa: E402  (e027/certify.py)
from lift_cnf import Builder, write      # noqa: E402  (e027/lift_cnf.py)

CE.CADICAL = str(ROOT / "tools/cadical/build/cadical")
CE.DRAT_TRIM = str(ROOT / "tools/drat-trim/drat-trim")
CE.CAKE_LPR = str(ROOT / "tools/cake_lpr/cake_lpr")


def setup(family, spec_path, xo, zo, R, basis):
    from evaluators.candidate import parse_schedule
    C = importlib.import_module(f"search.experiments.{family}.common")
    L = importlib.import_module(f"search.experiments.{family}.lift")
    cg = importlib.import_module(f"search.experiments.{family}.cegar")
    D = 8 if family == "e028" else 10
    spec = parse_schedule(json.load(open(spec_path))).canonical()
    lo = L.label_orders(spec)
    k = L.KIND_OF_BASIS[basis]
    E = C.ext_general(k, lo[k], group=[(0, 0)])
    o = xo if k == "X" else zo
    lA, csA = cg.load_class(k, "all", o, D)
    lB, _ = cg.load_class(k, "all", o, D + 1)
    sA, cs = L.reindex(E, lA)
    assert cs == csA, "circuit's extended code differs from the class"
    sB, _ = L.reindex(E, lB)
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
    meta = {"D": D, "nA": len(sA), "nB": len(sB), "zero_terms": len(zeros), **{k2: v for k2, v in st.items()
                                                                                if isinstance(v, (int, float, str))}}
    return insts, meta


def add_instance(b, inst, guard):
    gs, zero = inst
    det = {}
    for masks in gs:
        vs = []
        for m in masks:
            v = b.new(); vs.append(v)
            d = 0
            while m:
                if m & 1:
                    det.setdefault(d, []).append(v)
                m >>= 1; d += 1
        b.exactly_one(vs, guard)
    if zero:
        zs = []
        for m in zero:
            v = b.new(); zs.append(v)
            d = 0
            while m:
                if m & 1:
                    det.setdefault(d, []).append(v)
                m >>= 1; d += 1
        # at most one zero-image term (pairwise; Sinz ladder if large)
        if len(zs) <= 8:
            for a in range(len(zs)):
                for c in range(a + 1, len(zs)):
                    b.clauses.append(guard + [-zs[a], -zs[c]])
        else:
            s = [b.new() for _ in zs]
            for i, x in enumerate(zs):
                b.clauses.append(guard + [-x, s[i]])
                if i > 0:
                    b.clauses.append(guard + [-s[i - 1], s[i]])
                    b.clauses.append(guard + [-x, -s[i - 1]])
    for d in sorted(det):
        b.xor_chain(det[d], guard)


def main(argv):
    family, spec, xo, zo, rng, outdir = argv[:6]
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    bases = ["Z", "X"]
    if "--bases" in argv:
        i = argv.index("--bases") + 1; bases = []
        while i < len(argv) and not argv[i].startswith("--"):
            bases.append(argv[i]); i += 1
    bsize = int(argv[argv.index("--batch") + 1]) if "--batch" in argv else 1500
    expect = "sat" if "--expect" in argv else "unsat"
    if "--no-cake" in argv:          # drat-trim only (budget); the record then says cake_lpr "not run"
        CE.CAKE_LPR = "/nonexistent"
    Rs = []
    for part in rng.split(","):
        a, _, c = part.partition("-"); Rs += list(range(int(a), int(c or a) + 1))
    res = outdir / "results.jsonl"
    done = {json.loads(l)["name"] for l in res.open()} if res.exists() else set()
    circ = Path(spec).stem
    allok = True
    for R in Rs:
        for basis in bases:
            insts, meta = setup(family, spec, xo, zo, R, basis)
            # about <= 3 M clauses per batch (~225 R clauses per instance): at most 13000 / R instances
            K = max(1, math.ceil(len(insts) / min(bsize, max(50, 13000 // R))))
            for s in range(K):
                name = f"{circ}_{basis}_R{R}_s{s}of{K}"
                if name in done:
                    continue
                idx = list(range(s, len(insts), K))
                b = Builder()
                sel = [b.new() for _ in idx]
                b.clauses.append(list(sel))
                for t, i in zip(sel, idx):
                    add_instance(b, insts[i], [-t])
                cnf = outdir / "tmp" / f"{name}.cnf"
                cnf.parent.mkdir(parents=True, exist_ok=True)
                write(cnf, b, [f"lift batch: {circ} ({family}, d_ext={meta['D']}), {basis}-basis memory, R = {R}, "
                               f"instances i = {s} mod {K} of {len(insts)} (first {meta['nA']}: weight-{meta['D']} "
                               f"list with optional zero-image term; then weight-{meta['D'] + 1} list); "
                               f"selectors 1..{len(idx)}; UNSAT iff no instance lifts"])
                rec = CE.certify(cnf, outdir / "work", name, timeout=7200, keep=False)
                cnf.unlink()
                rec.update(circuit=circ, family=family, basis=basis, R=R, split=[s, K], instances=len(idx), dem=meta)
                if expect == "sat":
                    rec["ok"] = rec["solver"]["answer"] == "SAT"
                with open(res, "a") as f:
                    f.write(json.dumps(rec) + "\n")
                print(("PASS" if rec["ok"] else "FAIL"), name, rec.get("clauses"), rec["solver"]["answer"],
                      rec["solver"]["cpu_s"], rec.get("drat_trim", {}).get("verdict"),
                      rec.get("cake_lpr", {}).get("verdict"), flush=True)
                allok &= rec["ok"]
    print("ALL PASS" if allok else "SOME FAILED", flush=True)
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
