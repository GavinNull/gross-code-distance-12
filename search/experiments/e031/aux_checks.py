"""E-031 auxiliary checks (no proofs involved).

  enumerate SOURCE BASIS W OUT.json      list all logicals of weight W found by the (count-only) search in the orbit
                                         representative cases, closed under the symmetry group (for planted tests)
  models OPB_STEM LIST.json [LIST2.json] exactness, satisfiable direction: every listed logical (weight <= W) extends
                                         to a 0/1 model of the OPB instance (aux digits and q computed here) unless
                                         it contains a blocked set; parsed from the .opb file itself
  tamper OPB PROOF.gz OUTDIR             mutate a verified proof in several ways; each mutant must be rejected
"""
import gzip
import json
import random
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BIN = ROOT / "results" / "E-031-xor-certificates" / "bin" / "pbdfs"
sys.path.insert(0, str(HERE))


def cmd_enumerate(source, basis, W, out):
    from build import build, load_ibm, load_release, write
    src = load_release(source, basis) if source in ("gross", "bb90") else load_ibm(source.split(":")[1], basis)
    I = build(src, W, ())
    stem = str(Path(out).with_suffix(""))
    write(I, stem)
    p = subprocess.run([str(BIN), stem + ".inst", "-e"], capture_output=True, text=True)
    sols = {tuple(sorted(int(x) for x in l.split(":")[1].split())) for l in p.stdout.splitlines()
            if l.startswith("SAT columns:")}
    allsets = set()
    for s in sols:
        for P in I["perms"]:
            allsets.add(tuple(sorted(int(P[j]) for j in s)))
    ws = sorted({len(s) for s in allsets})
    Path(out).write_text(json.dumps({"description": f"weight-{W} logicals of {source} {basis} found by pbdfs -e "
                                     "(orbit representatives closed under the group); untrusted list for tests",
                                     "count": len(allsets), "weights": ws, "num_orbits": len(sols),
                                     "logicals": [{"columns": list(s)} for s in sorted(allsets)]}))
    print(f"{len(sols)} representatives -> {len(allsets)} logicals, weights {ws}; {p.stdout.splitlines()[-1]}")


def parse_opb(path):
    cons = []
    for line in open(path):
        if line.startswith("*") or not line.strip():
            continue
        m = re.match(r"(.*?)\s*(>=|=)\s*(-?\d+)\s*;", line)
        toks = m.group(1).split()
        terms = [(int(toks[i]), toks[i + 1]) for i in range(0, len(toks), 2)]
        cons.append((terms, m.group(2), int(m.group(3))))
    return cons


def cmd_models(stem, lists):
    cons = parse_opb(stem + ".opb")
    meta = json.loads(Path(stem + ".json").read_text())
    rows = []        # (x columns, kind, index)
    for terms, rel, rhs in cons:
        xs = [int(v[1:]) - 1 for c, v in terms if v.startswith("x") and c == 1]
        if rel == "=":
            q = [v for c, v in terms if v.startswith("q")]
            aux = [(c, v) for c, v in terms if v[0] in "ab"]
            rows.append((xs, q[0] if q else None, aux))
    W = meta["W"]
    blocks = [set(int(v[2:]) - 1 for c, v in terms) for terms, rel, rhs in cons
              if rel == ">=" and all(v.startswith("~x") for c, v in terms)]
    nok = nblk = 0
    bad = []
    for lf in lists:
        for e in json.load(open(lf))["logicals"]:
            x = set(e["columns"])
            if any(b <= x for b in blocks):
                nblk += 1
                continue
            assign = {f"x{j + 1}": 1 for j in x}
            for xs, q, aux in rows:
                s = sum(1 for j in xs if j in x)
                if q is not None:
                    assign[q] = s % 2
                    s += s % 2
                assert s % 2 == 0
                half = s // 2
                for c, v in sorted(aux, key=lambda t: t[0]):
                    k = int(v.split("_")[1])
                    assign[v] = (half >> k) & 1
            val = lambda v: (1 - assign.get(v[1:], 0)) if v.startswith("~") else assign.get(v, 0)
            sat = all((sum(c * val(v) for c, v in terms) == rhs) if rel == "=" else
                      (sum(c * val(v) for c, v in terms) >= rhs) for terms, rel, rhs in cons)
            if sat:
                nok += 1
            else:
                bad.append(sorted(x))
    print(json.dumps({"opb": stem, "models_ok": nok, "contains_blocked": nblk, "not_models": len(bad),
                      "examples": bad[:3]}))


def cmd_tamper(opb, proof, outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    lines = gzip.open(proof, "rt").read().split("\n")
    rng = random.Random(31)
    idx = {k: [i for i, l in enumerate(lines) if l.startswith(k)] for k in ("pol", "rup", "red")}
    muts = []
    # 1) drop a hint from an internal-node rup (one with >= 3 hints)
    c = [i for i in idx["rup"] if " ; ~ " in lines[i] and len(lines[i].split(" ; ~ ")[1].split()) >= 3]
    i = rng.choice(c); l = lines[i].split(" ; ~ "); h = l[1].split(); del h[len(h) // 2]
    muts.append(("drop_hint", i, l[0] + " ; ~ " + " ".join(h)))
    # 2) remove the assumption literals of a weight leaf clause (claims a stronger clause)
    c = [i for i in idx["rup"] if lines[i].count(" 1 ~") >= 3 and " ; ~ " in lines[i]]
    i = rng.choice(c); l = lines[i]; k = l.index(" 1 ~"); k2 = l.index(" 1 ~", k + 1)
    muts.append(("drop_literal", i, l[:k] + l[k2:]))
    # 3) parity clause derivation: drop the division
    c = [i for i in idx["pol"] if lines[i].endswith(" 2 d 2 * +")]
    i = rng.choice(c); muts.append(("no_division", i, lines[i].replace(" 2 d 2 * +", " 2 * +")))
    # 4) counting bound with multiplier reduced
    c = [i for i in idx["pol"] if re.search(r" (\d+) \* \+$", lines[i]) and not lines[i].endswith(" 2 d 2 * +")]
    if c:
        i = rng.choice(c); m = re.search(r" (\d+) \* \+$", lines[i]); lam = int(m.group(1))
        muts.append(("lambda_minus_1", i, lines[i][:m.start()] + (f" {lam - 1} * +" if lam > 2 else " +")))
    # 5) symmetry step with a wrong witness (swap two images)
    i = idx["red"][0]; l = lines[i].split(" ; "); w = l[1].split(); a_ = [k for k in range(0, len(w), 3)]
    w[2], w[5] = w[5], w[2]
    muts.append(("red_bad_witness", i, l[0] + " ; " + " ".join(w)))
    # 6) delete one row-clause derivation line (ids shift: every later reference is off by one)
    i = rng.choice(idx["pol"][len(idx["pol"]) // 2:])
    muts.append(("delete_line", i, None))
    res = []
    for name, i, new in muts:
        L2 = list(lines)
        if new is None:
            del L2[i]
        else:
            L2[i] = new
        p = out / f"{name}.pbp.gz"
        with gzip.open(p, "wt", compresslevel=1) as f:
            f.write("\n".join(L2))
        q = subprocess.run([sys.executable, str(HERE / "veripb_run.py"), opb, str(p)], capture_output=True, text=True)
        rejected = not (q.returncode == 0 and "s VERIFIED UNSATISFIABLE" in q.stdout)
        res.append({"mutation": name, "line": i + 1, "rejected": rejected,
                    "msg": [x for x in q.stdout.splitlines() if "Fail" in x or "Hint" in x or "rror" in x][:2]})
        p.unlink()
    print(json.dumps(res, indent=1))
    (out / "tamper.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "enumerate":
        cmd_enumerate(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5])
    elif c == "models":
        cmd_models(sys.argv[2], sys.argv[3:])
    elif c == "tamper":
        cmd_tamper(sys.argv[2], sys.argv[3], sys.argv[4])
