"""E-034: run e031/liftcert.py batches, optionally restricted to named batches (to add cake_lpr to E-031 batches that
were checked by drat-trim only).  The batch construction is e031/liftcert.py's, unchanged (imported); for re-done
batches the regenerated CNF's sha256 is compared with the E-031 record.

    PYTHONPATH=.:tests uv run python search/experiments/e034/liftsel.py FAMILY SPEC XO ZO RANGE OUTDIR
        [--bases Z X] [--only E031_RESULTS_JSONL]   (--only: redo the batches whose cake_lpr verdict was "not run")
Verdict per batch: solver UNSAT + drat-trim VERIFIED + cake_lpr VERIFIED UNSAT (e027/certify.py rule).
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "search" / "experiments" / "e031"))
import liftcert as LC                    # noqa: E402
from liftcert import CE, Builder, write, setup, add_instance  # noqa: E402


def main(argv):
    family, spec, xo, zo, rng, outdir = argv[:6]
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    bases = ["Z", "X"]
    if "--bases" in argv:
        i = argv.index("--bases") + 1; bases = []
        while i < len(argv) and not argv[i].startswith("--"):
            bases.append(argv[i]); i += 1
    only = None
    if "--only" in argv:
        only = {}
        for l in open(argv[argv.index("--only") + 1]):
            r = json.loads(l)
            if r.get("cake_lpr", {}).get("verdict") == "not run":
                only[r["name"]] = r
    Rs = []
    for part in rng.split(","):
        a, _, c = part.partition("-"); Rs += list(range(int(a), int(c or a) + 1))
    res = outdir / "results.jsonl"
    done = {json.loads(l)["name"] for l in res.open()} if res.exists() else set()
    circ = Path(spec).stem
    allok = True
    for R in Rs:
        for basis in bases:
            K = None
            todo_names = None
            if only is not None:
                todo_names = [n for n in only if only[n]["R"] == R and only[n]["basis"] == basis and n not in done]
                if not todo_names:
                    continue
            insts, meta = setup(family, spec, xo, zo, R, basis)
            K = max(1, math.ceil(len(insts) / min(1500, max(50, 13000 // R))))
            for s in range(K):
                name = f"{circ}_{basis}_R{R}_s{s}of{K}"
                if name in done or (todo_names is not None and name not in todo_names):
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
                if only is not None:
                    o = only[name]
                    rec["e031_cnf_sha256_equal"] = rec.get("cnf_sha256") == o.get("cnf_sha256")
                    rec["e031_drat_sha256_equal"] = rec.get("drat_sha256") == o.get("drat_sha256")
                    rec["ok"] = rec["ok"] and rec["e031_cnf_sha256_equal"]
                rec["ok"] = rec["ok"] and rec.get("cake_lpr", {}).get("verdict") == "VERIFIED UNSAT"
                with open(res, "a") as f:
                    f.write(json.dumps(rec) + "\n")
                print(("PASS" if rec["ok"] else "FAIL"), name, rec.get("clauses"), rec["solver"]["answer"],
                      rec["solver"]["cpu_s"], rec.get("drat_trim", {}).get("verdict"),
                      rec.get("cake_lpr", {}).get("verdict"), rec.get("e031_cnf_sha256_equal"), flush=True)
                allok &= rec["ok"]
    print("ALL PASS" if allok else "SOME FAILED", flush=True)
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
