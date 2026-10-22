"""E-034: tamper tests for VeriPB 3.  Mutates a verified proof (format 3.0 or 2.0) or its formula; every mutant in the
"must reject" set has to be rejected, i.e. VeriPB 3 must NOT print "s VERIFIED UNSATISFIABLE".  Verdicts are taken
from the output line only (exit codes are recorded but not used).
Mutant set = E-031's own tamper set (aux_checks.py tamper) + the E-031 auditor's set (F1-F3, P1-P7).

    uv run python search/experiments/e034/tamper3.py OPB PROOF.gz OUT.jsonl [--v2]
"""
import gzip
import json
import random
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VERIPB = ROOT / "tools/veripb/target/release/veripb"


def main():
    opb, proof, out = sys.argv[1:4]
    v2 = "--v2" in sys.argv
    S = " ; " if v2 else " : "            # separator before hints / witness
    E = "" if v2 else ";"                 # end of rule
    lines = gzip.open(proof, "rt").read().split("\n")
    opbl = Path(opb).read_text().split("\n")
    rng = random.Random(34)
    idx = {k: [i for i, l in enumerate(lines) if l.startswith(k + " ")] for k in ("pol", "rup", "red")}
    reds = idx["red"]
    M = []   # (name, must_reject, kind, payload)

    def pm(name, rej, i, new):
        L = list(lines); L[i] = new; M.append((name, rej, "proof", L))

    def strip(l):
        return l[:-1] if (not v2 and l.endswith(";")) else l
    # --- E-031 set
    c = [i for i in idx["rup"] if S + "~ " in lines[i] and len(strip(lines[i]).split(S + "~ ")[1].split()) >= 3]
    i = rng.choice(c); a, b = strip(lines[i]).split(S + "~ "); h = b.split(); del h[len(h) // 2]
    pm("E1_drop_hint", True, i, a + S + "~ " + " ".join(h) + E)
    c = [i for i in idx["rup"] if lines[i].count(" 1 ~") >= 3 and S + "~ " in lines[i]]
    i = rng.choice(c); l = lines[i]; k = l.index(" 1 ~"); k2 = l.index(" 1 ~", k + 1)
    pm("E2_drop_literal", True, i, l[:k] + l[k2:])
    c = [i for i in idx["pol"] if strip(lines[i]).endswith(" 2 d 2 * +")]
    i = rng.choice(c); pm("E3_no_division", True, i, lines[i].replace(" 2 d 2 * +", " 2 * +"))
    first_case = min(idx["rup"])
    c = [i for i in idx["pol"] if i > first_case and re.fullmatch(r"pol \d+( \d+ \+)+", strip(lines[i]))]
    i = rng.choice(c); l = strip(lines[i]); pm("E4_counting_bound_without_weight_term", True, i,
                                                re.sub(r" \d+ \+$", "", l) + E)
    pm("E5_red_witness_swapped_images", True, reds[0], lines[reds[0]].replace(" x1 -> x2 ", " x1 -> x3 ", 1))
    i = rng.choice(idx["rup"][len(idx["rup"]) // 2:]); L = list(lines); del L[i]; M.append(("E6_delete_line", True, "proof", L))
    c = [i for i in idx["pol"] if re.search(r" (\d+) \* \+$", strip(lines[i])) and not strip(lines[i]).endswith(" 2 d 2 * +")]
    if c:
        i = rng.choice(c); l = strip(lines[i]); m = re.search(r" (\d+) \* \+$", l); lam = int(m.group(1))
        pm("E7_lambda_minus_1_(sound_weakening)", False, i, l[:m.start()] + (f" {lam - 1} * +" if lam > 2 else " +") + E)
    # --- auditor set
    pm("P1_red_witness_not_automorphism", True, reds[0], lines[reds[0]].replace(" x1 -> x2 ", " x1 -> x5 ", 1))

    def x_only(l):
        head, wit = strip(l).split(S, 1)
        t = wit.split(); keep = []
        for j in range(0, len(t), 3):
            if t[j].startswith("x"):
                keep += t[j:j + 3]
        return head + S + " ".join(keep) + E
    pm("P2b_first_red_witness_x_only", True, reds[0], x_only(lines[reds[0]]))
    pm("P2_last_red_witness_x_only_(redundant_step)", False, reds[-1], x_only(lines[reds[-1]]))
    pm("P3_red_unit_clause_not_redundant", True, reds[0], lines[reds[0]].replace("red 1 ~x2 1 x1 >= 1", "red 1 ~x2 >= 1", 1))
    pm("P4_last_red_replaced_by_tautology_(redundant_step)", False, reds[-1], "rup 1 x1 1 ~x1 >= 1" + (" ;" if v2 else ";"))
    ci = next(k for k, l in enumerate(lines) if l.startswith("conclusion"))
    pm("P5_conclusion_NONE", True, ci, "conclusion NONE" + E)
    pm("P6_conclusion_points_to_non_contradiction", True, ci, "conclusion UNSAT : 300" + E)
    units = [k for k, l in enumerate(lines) if re.fullmatch(r"rup 1 ~x\d+ >= 1 ?;", l)]
    pm("P7_last_orbit_unit_removed_(redundant_step)", False, units[-1], "rup 1 x1 1 ~x1 >= 1" + (" ;" if v2 else ";"))
    # formula mutants (satisfiable formulas)
    o = list(opbl); i = next(k for k, l in enumerate(o) if l.startswith("-1 x1 ")); W = re.search(r">= (-\d+) ;", o[i]).group(1)
    o[i] = o[i].replace(f">= {W} ;", f">= {int(W) - 1} ;"); M.append(("F1_weight_bound_plus_1_formula_SAT", True, "opb", o))
    o = list(opbl); i = next(k for k, l in enumerate(o) if l.startswith("1 q1 ")); o[i] = o[i].replace(">= 1 ;", ">= 0 ;")
    M.append(("F2_sum_q_ge_0_formula_SAT", True, "opb", o))
    o = [re.sub(r"(^|(?<= ))1 x1 ", "", l) if (" = 0 ;" in l and " q" not in l) else l for l in opbl]
    M.append(("F3_column1_removed_from_check_rows_formula_SAT", True, "opb", o))
    # the unmodified proof (must be accepted)
    M.append(("U0_unmodified", False, "proof", list(lines)))

    tmp = Path(out).with_suffix(".tmp")
    tmp.mkdir(parents=True, exist_ok=True)
    allok = True
    for name, rej, kind, payload in M:
        po, oo = proof, opb
        if kind == "proof":
            po = tmp / "m.pbp.gz"
            with gzip.open(po, "wt", compresslevel=1) as f:
                f.write("\n".join(payload))
        else:
            assert payload != opbl
            oo = tmp / "m.opb"; oo.write_text("\n".join(payload))
        t0 = time.time()
        q = subprocess.run([str(VERIPB), str(oo), str(po)], capture_output=True, text=True)
        acc = any(l.strip() == "s VERIFIED UNSATISFIABLE" for l in q.stdout.splitlines())
        ok = (not acc) if rej else (acc if name.startswith("U0") else True)
        allok &= ok
        tail = [l for l in (q.stdout + q.stderr).splitlines() if l.strip()][-3:]
        rec = {"name": name, "syntax": "2.0" if v2 else "3.0", "must_reject": rej, "accepted": acc, "rc": q.returncode,
               "as_required": ok, "wall_s": round(time.time() - t0, 2), "tail": [t[:300] for t in tail]}
        print(json.dumps(rec)[:400], flush=True)
        with open(out, "a") as f:
            f.write(json.dumps(rec) + "\n")
    print("ALL AS REQUIRED" if allok else "SOME NOT AS REQUIRED")


if __name__ == "__main__":
    main()
