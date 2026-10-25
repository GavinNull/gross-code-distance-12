"""E-037: tamper tests of the DEM certificates.  experimenter.

    uv run python search/experiments/e037/tamper.py STEM OUT.jsonl
STEM = a certified instance kept with certify.py --keep (STEM.opb, STEM.pbp).  Each variant must be REJECTED
(no "s VERIFIED UNSATISFIABLE"), the unmodified pair must be accepted.  Constraint ids are preserved by replacing a
line with a trivially true constraint instead of deleting it.
  T1  weight bound W -> W+1 in the formula (the formula becomes satisfiable: weight-(W+1) logicals exist)
  T2  one cardinality constraint replaced by a tautology (formula no longer closed under the group)
  T3  one blocking clause replaced by a tautology
  T4  one detector row loses a column (wrong DEM)
  P1  proof: one symmetry (red) step replaced by a RUP claim of the same clause (ids preserved): not RUP-derivable
  T5  (in-formula symmetry breaking) one SB clause replaced by a tautology
  T6  (in-formula symmetry breaking) one orbit-indicator clause x_j -> h_o replaced by a tautology
  (T2/T3 apply to the in-proof symmetry mode only: there the formula must stay group-invariant syntactically)
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VERIPB = ROOT / "tools/veripb/target/release/veripb"


def check(opb, pbp):
    p = subprocess.run([str(VERIPB), str(opb), str(pbp)], capture_output=True, text=True)
    return any(l.strip() == "s VERIFIED UNSATISFIABLE" for l in p.stdout.splitlines()), (p.stdout + p.stderr)[-300:]


def main():
    stem, outp = sys.argv[1], sys.argv[2]
    opb = Path(stem + ".opb").read_text().splitlines()
    pbp = Path(stem + ".pbp")
    meta = json.loads(Path(stem + ".json").read_text())
    W = meta["W"]
    tmp = Path(stem + ".tamper"); tmp.mkdir(exist_ok=True)
    res = []

    def variant(name, lines, proof=pbp, expect=False):
        f = tmp / f"{name}.opb"
        f.write_text("\n".join(lines) + "\n")
        ok, tail = check(f, proof)
        res.append(dict(name=name, verified=ok, expected=expect, pass_=ok == expect, tail=tail))
        print(name, "verified" if ok else "rejected", "OK" if ok == expect else "UNEXPECTED", flush=True)
    variant("unmodified", opb, expect=True)
    wl = [i for i, l in enumerate(opb) if l.startswith("-1 x1 -1 x2 ") and l.endswith(f">= -{W} ;")]
    assert len(wl) == 1
    L1 = list(opb); L1[wl[0]] = L1[wl[0]].replace(f">= -{W} ;", f">= -{W + 1} ;")
    variant("T1_weight_W+1", L1)
    taut = "1 x1 >= 0 ;"
    formula_sym = meta.get("sym_mode") == "formula"
    if formula_sym:
        # in-formula symmetry breaking: removing an SB or H1 constraint must break the proof
        sb = [i for i, l in enumerate(opb) if l.startswith("1 ~h")]
        h1 = [i for i, l in enumerate(opb) if re.fullmatch(r"1 ~x\d+ 1 h\d+ >= 1 ;", l)]
        L5 = list(opb); L5[sb[len(sb) // 2]] = taut
        variant("T5_drop_one_symmetry_breaking_clause", L5)
        L6 = list(opb); L6[h1[len(h1) // 2]] = taut
        variant("T6_drop_one_orbit_indicator_clause", L6)
    cl = [] if formula_sym else [i for i, l in enumerate(opb) if re.fullmatch(r"(-1 x\d+ ?)+ >= -[12] ;", l)]
    if cl:
        L2 = list(opb); L2[cl[len(cl) // 2]] = taut
        variant("T2_drop_one_cardinality", L2)
    bl = [] if formula_sym else [i for i, l in enumerate(opb) if l.startswith("1 ~x")]
    if bl:
        L3 = list(opb); L3[bl[len(bl) // 2]] = taut
        variant("T3_drop_one_block", L3)
    # T4: first detector row (line 2 of the file) loses its first x term
    i4 = 1
    toks = opb[i4].split()
    k = toks.index("1")
    L4 = list(opb); L4[i4] = " ".join(toks[:k] + toks[k + 2:])
    variant("T4_detector_row_column_removed", L4)
    # proof tampering
    lines = pbp.read_text().splitlines()
    reds = [i for i, l in enumerate(lines) if l.startswith("red ")]
    if reds:
        p1 = tmp / "P1.pbp"
        r = reds[len(reds) // 2]
        claim = lines[r][4:].split(" : ")[0]            # the symmetry clause, now claimed by RUP (ids preserved)
        p1.write_text("\n".join(lines[:r] + ["rup " + claim + ";"] + lines[r + 1:]) + "\n")
        ok, tail = check(Path(stem + ".opb"), p1)
        res.append(dict(name="P1_red_as_rup", verified=ok, expected=False, pass_=not ok, tail=tail))
        print("P1_red_as_rup", "verified" if ok else "rejected", flush=True)
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()
    with open(outp, "a") as f:
        for r in res:
            f.write(json.dumps(dict(stem=stem, **r)) + "\n")
    print("all as expected:", all(r["pass_"] for r in res))


if __name__ == "__main__":
    main()
