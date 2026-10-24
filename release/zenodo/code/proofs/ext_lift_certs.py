"""DRAT certificates of the extended lift (generalised Lemma 2) for the period-11 circuits and their relatives.

Lift instances (code/p11/lift.py): for a circuit of d_ext = D, a memory basis and R rounds,
  (a) every weight-D extended logical S of the complete list: one DEM mechanism per column of S (mechanisms with that
      image) and AT MOST ONE extra zero-image mechanism (only those whose detectors lie in the union of the groups'
      detectors: any other one could not be cancelled), every detector even   [|F| = D and |F| = D + 1, z = 1]
  (b) every weight-(D + 1) extended logical: one mechanism per column, every detector even.
CNF of an instance: one variable per distinct detector set of a group (groups in the column order of the circuit's
own extended code, mechanisms in DEM order), exactly one per column group (at-least-one clause; pairwise or ladder
at-most-one, lift_cnf.Builder), at most one of the zero-image candidates (pairwise up to 8, otherwise a ladder), and
for every detector touched by these mechanisms the XOR of its mechanisms = 0 (Tseitin chain, pieces of <= 5 literals).
The instances of one (circuit, basis, R) are split into K batches (instance i in batch i mod K); a batch is the
disjunction of its instances: selector t_i per instance, clause (t_1 v ... v t_m), every clause of instance i extended
by -t_i (disjoint variables), so a batch is UNSAT iff none of its instances lifts.  Instance order: the weight-D list
then the weight-(D + 1) list, in the order of certificates/proofs/lift_instance_order.json (u11: the order of the
data files).  Each batch is refuted by CaDiCaL with a DRAT proof, checked by drat-trim (backward), whose LRAT core is
checked by cake_lpr (code/proofs/certify.py).

Records: certificates/proofs/lift_{u11,c11,c12,c13,c16}.jsonl (one per batch: split [s, K], sha256 of CNF / DRAT /
LRAT, sizes, verdicts, CPU seconds, DEM statistics, and the comment line of the CNF), lift_controls.jsonl (positive
controls, SAT).  The CNFs are deterministic: regenerated CNFs must have the recorded sha256.  The DRAT proofs of the
smallest batches are shipped (certificates/proofs/drat_lift/NAME.drat.xz); for the others only the sha256 is recorded.

    python code/proofs/ext_lift_certs.py u11 1-2 OUT                      # regenerate, refute, check, compare (R = 1, 2)
    python code/proofs/ext_lift_certs.py c11 1-25 OUT --workers 4         # all c11 batches (about 6 CPU h)
    python code/proofs/ext_lift_certs.py u11 1-31 OUT --cnf-only          # only regenerate the CNFs, compare sha256
    python code/proofs/ext_lift_certs.py shipped OUT                      # drat-trim (and cake_lpr) on the shipped proofs
    python code/proofs/ext_lift_certs.py u11_control_p10 1 OUT --expect sat   # positive control (SAT)
Options: --basis Z X, --batches 0,3 (only these s), --no-cake, --keep-proofs, --workers N.
"""
import json
import lzma
import os
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import certify as CE                              # noqa: E402
from lift_cnf import Builder, write               # noqa: E402

ROOT = HERE.parents[1]
PROOFS = ROOT / "certificates" / "proofs"
RECFILE = {"u11": "lift_u11.jsonl", "c11": "lift_c11.jsonl", "c12": "lift_c12.jsonl", "c13": "lift_c13.jsonl",
           "c16": "lift_c16.jsonl", "u11_control_p10": "lift_controls.jsonl", "u16": "lift_controls.jsonl"}


def parse_range(s):
    out = []
    for part in s.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def setup(name, basis, R):
    """instances of (circuit, basis, R): list of (groups of detector masks, zero-image candidate masks)."""
    import stim
    import numpy as np
    from p11 import common as C
    from bb90.ext import noisy_circuit
    fam = C.family_of(name)
    D = C.FAMILY[fam]["dext"]
    code = C.load_code(fam)
    spec = C.circuit(name)
    keys_f = C.ext_keys_from_file(code, fam, basis)
    keys_c, _, _ = C.ext_columns(code, basis, spec)
    assert set(keys_c) == set(keys_f), "extended code of this circuit differs from the data file"
    kc = {k: j for j, k in enumerate(keys_c)}
    order = json.load(open(PROOFS / "lift_instance_order.json"))[fam][basis]
    lists = []
    for w in (D, D + 1):
        lst = C.load_list(fam, w, basis)
        perm = order[str(w)] or list(range(len(lst)))
        lists.append([tuple(sorted(kc[keys_f[j]] for j in lst[i])) for i in perm])
    # augmented SD6 DEM (as code/bb90/ext.py dem_terms), groups in DEM order
    c = noisy_circuit(spec, code, R, basis)
    H, L = C.hl(code, basis)
    n = code.n
    last = [op for op in c if op.name in ("M", "MX")][-1]
    assert [t.value for t in last.targets_copy()] == list(range(n))
    k0 = c.num_observables
    aug = c.copy()
    for r, row in enumerate(list(H) + list(L)):
        aug.append("OBSERVABLE_INCLUDE", [stim.target_rec(int(q) - n) for q in np.nonzero(row)[0]], k0 + r)
    dem = aug.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    nH, nL = H.shape[0], L.shape[0]
    groups, zeros, nterms, nzero = {}, set(), 0, 0
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        dm = 0
        hb = np.zeros(nH, np.uint8); lb = np.zeros(nL, np.uint8); ob = np.zeros(k0, np.uint8)
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                dm ^= 1 << t.val
            elif t.is_logical_observable_id():
                v = t.val
                if v < k0:
                    ob[v] ^= 1
                elif v < k0 + nH:
                    hb[v - k0] ^= 1
                else:
                    lb[v - k0 - nH] ^= 1
        nterms += 1
        assert (ob == lb).all()
        if not hb.any() and not lb.any():
            nzero += 1
            if dm:
                zeros.add(dm)
            continue
        key = hb.tobytes() + lb.tobytes()
        assert key in kc, "image is not an extended column (Lemma 1)"
        groups.setdefault(kc[key], []).append(dm)
    assert len(groups) == len(keys_c), "not every extended column is realised"
    insts = []
    for S in lists[0]:
        sup = 0
        for j in S:
            for m in groups[j]:
                sup |= m
        z = sorted(m for m in zeros if m and m & ~sup == 0)
        insts.append(([list(dict.fromkeys(groups[j])) for j in S], z))
    for S in lists[1]:
        insts.append(([list(dict.fromkeys(groups[j])) for j in S], []))
    meta = {"D": D, "nA": len(lists[0]), "nB": len(lists[1]), "zero_terms": len(zeros), "aug_terms": nterms,
            "zero_image": nzero, "detectors": c.num_detectors}
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
        if len(zs) <= 8:
            for i in range(len(zs)):
                for j in range(i + 1, len(zs)):
                    b.clauses.append(guard + [-zs[i], -zs[j]])
        else:
            s = [b.new() for _ in zs]
            for i, x in enumerate(zs):
                b.clauses.append(guard + [-x, s[i]])
                if i > 0:
                    b.clauses.append(guard + [-s[i - 1], s[i]])
                    b.clauses.append(guard + [-x, -s[i - 1]])
    for d in sorted(det):
        b.xor_chain(det[d], guard)


def batch_cnf(insts, s, K, path, comment):
    idx = list(range(s, len(insts), K))
    b = Builder()
    sel = [b.new() for _ in idx]
    b.clauses.append(list(sel))
    for t, i in zip(sel, idx):
        add_instance(b, insts[i], [-t])
    write(path, b, [comment])
    return len(idx)


def job(args):
    circ, basis, R, outdir, recs, opts = args
    outdir = Path(outdir)
    insts, meta = setup(circ, basis, R)
    mine = sorted((r for r in recs.values() if r["circuit"] == circ and r["basis"] == basis and r["R"] == R),
                  key=lambda r: r["split"][0])
    assert mine, f"no record for {circ} {basis} R={R}"
    K = mine[0]["split"][1]
    assert [r["split"] for r in mine] == [[s, K] for s in range(K)], "records incomplete"
    oks = []
    for r in mine:
        s = r["split"][0]
        if opts["batches"] is not None and s not in opts["batches"]:
            continue
        name = r["name"]
        assert r["dem"]["nA"] == meta["nA"] and r["dem"]["nB"] == meta["nB"]
        cnf = outdir / "tmp" / f"{name}.cnf"
        cnf.parent.mkdir(parents=True, exist_ok=True)
        ni = batch_cnf(insts, s, K, cnf, r["cnf_comment"])
        if opts["cnf_only"]:
            h = CE.sha256(cnf); cnf.unlink()
            ok = h == r["cnf_sha256"] and ni == r["instances"]
            print(("PASS" if ok else "FAIL"), name, f"{ni} instances: CNF sha256 {'= record' if ok else 'DIFFERS'}",
                  flush=True)
            oks.append(ok)
            continue
        rec = CE.certify(cnf, outdir / "work", name, timeout=7200, keep=opts["keep"])
        cnf.unlink()
        cm = rec["cnf_sha256"] == r["cnf_sha256"]
        dm = rec.get("drat_sha256") == r.get("drat_sha256")
        if opts["expect"] == "sat":
            ok = rec["solver"]["answer"] == "SAT" and cm
        else:
            ok = rec["ok"] and cm
        rec.update(circuit=circ, basis=basis, R=R, split=[s, K], instances=ni, cnf_matches_record=cm,
                   drat_matches_record=dm)
        with open(outdir / "results.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        ck = rec.get("cake_lpr", {}).get("verdict", "-")
        print(("PASS" if ok else "FAIL"), name, f"{ni} instances, {rec.get('clauses')} clauses:", rec["solver"]["answer"],
              "drat-trim", rec.get("drat_trim", {}).get("verdict", "-"), "cake_lpr",
              "SKIP (not run)" if ck == "not run" else ck,
              f"cnf sha256 {'= record' if cm else 'DIFFERS'}, proof {'= record' if dm else 'differs from record'}",
              flush=True)
        oks.append(ok)
    return all(oks)


def shipped(outdir):
    """drat-trim (and cake_lpr) on every shipped DRAT proof, against the regenerated CNF (sha256 = record)."""
    outdir = Path(outdir)
    d = PROOFS / "drat_lift"
    allrec = {}
    for f in set(RECFILE.values()):
        if (PROOFS / f).exists():
            for l_ in open(PROOFS / f):
                r = json.loads(l_); allrec[r["name"]] = r
    oks = []
    cache = {}
    for p in sorted(d.glob("*.drat.xz")):
        name = p.name[:-len(".drat.xz")]
        r = allrec[name]
        key = (r["circuit"], r["basis"], r["R"])
        if key not in cache:
            cache.clear(); cache[key] = setup(*key)[0]
        work = outdir / "shipped"; work.mkdir(parents=True, exist_ok=True)
        cnf = work / f"{name}.cnf"
        batch_cnf(cache[key], r["split"][0], r["split"][1], cnf, r["cnf_comment"])
        drat = work / f"{name}.drat"
        with lzma.open(p, "rb") as fi, open(drat, "wb") as fo:
            shutil.copyfileobj(fi, fo)
        ok = CE.sha256(cnf) == r["cnf_sha256"] and CE.sha256(drat) == r["drat_sha256"]
        lrat = work / f"{name}.lrat"
        code, text, _, cpu = CE.run([CE.DRAT_TRIM, str(cnf), str(drat), "-w", "-L", str(lrat)], 7200)
        v = any(l_.strip() == "s VERIFIED" for l_ in text.splitlines())
        ck = "not run"
        if v and (shutil.which(CE.CAKE_LPR) or Path(CE.CAKE_LPR).exists()):
            _, t3, _, _ = CE.run([CE.CAKE_LPR, str(cnf), str(lrat)], 7200)
            ck = "VERIFIED UNSAT" if any(l_.strip() == "s VERIFIED UNSAT" for l_ in t3.splitlines()) else "FAILED"
        ok &= v and ck in ("VERIFIED UNSAT", "not run")
        for q in (cnf, drat, lrat):
            if q.exists():
                q.unlink()
        print(("PASS" if ok else "FAIL"), name, "shipped DRAT proof: CNF and proof sha256 = record, drat-trim",
              "VERIFIED" if v else "FAILED", "cake_lpr", "SKIP (not run)" if ck == "not run" else ck, flush=True)
        oks.append(ok)
    print(("PASS" if oks and all(oks) else "FAIL"), f"{len(oks)} shipped lift proofs checked")
    return 0 if oks and all(oks) else 1


def main(argv):
    if argv[0] == "shipped":
        return shipped(argv[1])
    circ, rng, outdir = argv[0], parse_range(argv[1]), Path(argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    bases = ["Z", "X"]
    if "--basis" in argv:
        i = argv.index("--basis") + 1; bases = []
        while i < len(argv) and not argv[i].startswith("--"):
            bases.append(argv[i]); i += 1
    opts = {"cnf_only": "--cnf-only" in argv, "keep": "--keep-proofs" in argv,
            "expect": "sat" if "--expect" in argv else "unsat",
            "batches": [int(x) for x in argv[argv.index("--batches") + 1].split(",")] if "--batches" in argv else None}
    if "--no-cake" in argv:
        os.environ["CAKE_LPR"] = "/nonexistent"; CE.CAKE_LPR = "/nonexistent"
    workers = int(argv[argv.index("--workers") + 1]) if "--workers" in argv else 1
    recs = {}
    for l_ in open(PROOFS / RECFILE[circ]):
        r = json.loads(l_)
        recs[r["name"]] = r
    jobs = [(circ, b, R, str(outdir), recs, opts) for R in rng for b in bases]
    if workers > 1:
        with ProcessPoolExecutor(workers) as ex:
            oks = list(ex.map(job, jobs))
    else:
        oks = [job(j) for j in jobs]
    print(("PASS" if all(oks) else "FAIL"), f"extended-lift certificates {circ}, R = {argv[1]}, bases {' '.join(bases)}: "
          + ("every batch CNF reproduced (sha256 = record)" if opts["cnf_only"] else
             ("every batch SAT" if opts["expect"] == "sat" else "every batch UNSAT with a verified proof, CNF sha256 = "
              "record") if all(oks) else "some batch failed"))
    return 0 if all(oks) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
