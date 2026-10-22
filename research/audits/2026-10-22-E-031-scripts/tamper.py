"""Auditor tamper tests on the regenerated, VeriPB-verified proof results/E-031-audit/regen/bb90_Z_W7.pbp.gz.
Every mutant must be REJECTED (no 'Verification succeeded.' / 's VERIFIED UNSATISFIABLE').
Formula mutants (F*) make the formula satisfiable, so acceptance would be a soundness failure of the pipeline.
    uv run python tamper.py [names...]       -> results/E-031-audit/tamper/tamper.jsonl
"""
import gzip
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REG = ROOT / "results/E-031-audit/regen"
OUT = ROOT / "results/E-031-audit/tamper"
OPB = REG / "bb90_Z_W7.mine.opb"
PROOF = REG / "bb90_Z_W7.pbp.gz"


def lines_proof():
    return gzip.open(PROOF, "rt").read().split("\n")


def write_proof(name, L):
    p = OUT / f"{name}.pbp.gz"
    with gzip.open(p, "wt", compresslevel=1) as f:
        f.write("\n".join(L))
    return p


def mutants():
    opb = OPB.read_text().split("\n")
    m = {}

    def P(fn):
        L = lines_proof(); fn(L); return L

    # proof mutants
    def red_bad_image(L):           # first red step: x1 -> x2 replaced by x1 -> x5 (not an automorphism)
        i = next(k for k, l in enumerate(L) if l.startswith("red "))
        L[i] = L[i].replace(" x1 -> x2 ", " x1 -> x5 ", 1)
    m["P1_red_witness_not_automorphism"] = ("proof", red_bad_image)

    def red_x_only(L):              # last red step: keep only the x part of the witness (q, a, b not renamed)
        i = max(k for k, l in enumerate(L) if l.startswith("red "))
        head, wit = L[i].split(";", 1)
        toks = wit.split()
        keep = []
        for j in range(0, len(toks), 3):
            if toks[j].startswith("x"):
                keep += toks[j:j + 3]
        L[i] = head + "; " + " ".join(keep)
    m["P2_red_witness_x_only"] = ("proof", red_x_only)

    def red_x_only_first(L):        # first red step (orbit 0, nothing fixed by earlier orbits): x part only
        i = next(k for k, l in enumerate(L) if l.startswith("red "))
        head, wit = L[i].split(";", 1)
        toks = wit.split()
        keep = []
        for j in range(0, len(toks), 3):
            assert toks[j + 1] == "->"
            if toks[j].startswith("x"):
                keep += toks[j:j + 3]
        L[i] = head + "; " + " ".join(keep)
    m["P2b_first_red_witness_x_only"] = ("proof", red_x_only_first)

    def last_red_as_rup(L):         # diagnostic: is the last symmetry clause already implied by propagation?
        i = max(k for k, l in enumerate(L) if l.startswith("red "))
        L[i] = "rup " + L[i][4:].split(";", 1)[0] + ";"
    m["D1_last_red_as_plain_rup_diagnostic"] = ("proof", last_red_as_rup)

    def red_wrong_clause(L):        # first red step: clause ~x2 v x1 replaced by the unit ~x2 (not redundant) with the same witness
        i = next(k for k, l in enumerate(L) if l.startswith("red "))
        L[i] = L[i].replace("red 1 ~x2 1 x1 >= 1", "red 1 ~x2 >= 1", 1)
    m["P3_red_unit_clause_not_redundant"] = ("proof", red_wrong_clause)

    def drop_last_red(L):           # remove the last symmetry step; ids shift -> replaced by a trivial tautology
        i = max(k for k, l in enumerate(L) if l.startswith("red "))
        L[i] = "rup 1 x1 1 ~x1 >= 1 ;"
    m["P4_last_red_replaced_by_tautology"] = ("proof", drop_last_red)

    def no_conclusion(L):
        i = next(k for k, l in enumerate(L) if l.startswith("conclusion"))
        L[i] = "conclusion NONE"
    m["P5_conclusion_NONE"] = ("proof", no_conclusion)

    def conclusion_wrong_id(L):
        i = next(k for k, l in enumerate(L) if l.startswith("conclusion"))
        L[i] = "conclusion UNSAT : 300"
    m["P6_conclusion_points_to_non_contradiction"] = ("proof", conclusion_wrong_id)

    def drop_one_unit_case(L):      # delete the rup that derives the unit ~x_rep of the last case (replaced by tautology)
        idx = [k for k, l in enumerate(L) if re.fullmatch(r"rup 1 ~x\d+ >= 1 ;.*", l)]
        L[idx[-1]] = "rup 1 x1 1 ~x1 >= 1 ;"
    m["P7_last_orbit_unit_removed"] = ("proof", drop_one_unit_case)

    # formula mutants (satisfiable formulas, same constraint ids)
    def f_w8(o):
        i = next(k for k, l in enumerate(o) if l.startswith("-1 x1 "))
        o[i] = o[i].replace(">= -7 ;", ">= -8 ;")
    m["F1_weight_bound_8_formula_SAT"] = ("opb", f_w8)

    def f_q0(o):
        i = next(k for k, l in enumerate(o) if l.startswith("1 q1 "))
        o[i] = o[i].replace(">= 1 ;", ">= 0 ;")
    m["F2_sum_q_ge_0_formula_SAT"] = ("opb", f_q0)

    def f_drop_col(o):              # remove column x1 from every check row it appears in (x1 alone becomes a logical)
        for k, l in enumerate(o):
            if " = 0 ;" in l and " q" not in l:
                o[k] = re.sub(r"(^|(?<= ))1 x1 ", "", l)
    m["F3_column1_removed_from_check_rows_formula_SAT"] = ("opb", f_drop_col)
    return m, opb


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    m, opb = mutants()
    want = sys.argv[1:] or list(m)
    for name in want:
        kind, fn = m[name]
        if kind == "proof":
            L = lines_proof(); fn(L)
            proof, opbp = write_proof(name, L), OPB
        else:
            o = list(opb); fn(o)
            assert o != opb
            opbp = OUT / f"{name}.opb"; opbp.write_text("\n".join(o))
            proof = PROOF
        t0 = time.time()
        q = subprocess.run([sys.executable, str(ROOT / "search/experiments/e031/veripb_run.py"), str(opbp), str(proof)],
                           capture_output=True, text=True)
        acc = "Verification succeeded." in q.stdout and "s VERIFIED UNSATISFIABLE" in q.stdout
        tail = [l for l in (q.stdout + q.stderr).splitlines() if l.strip()][-3:]
        rec = {"name": name, "rc": q.returncode, "accepted": acc, "rejected_as_required": not acc,
               "wall_s": round(time.time() - t0, 1), "tail": tail}
        print(json.dumps(rec), flush=True)
        with open(OUT / "tamper.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        if kind == "proof":
            proof.unlink()


if __name__ == "__main__":
    main()
