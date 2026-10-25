"""E-037 audit: my own tamper tests on a regenerated (OPB, proof) pair.  Each variant is checked by VeriPB 3.0.2 from
scratch; accepted = rc 0 AND a line "s VERIFIED UNSATISFIABLE".

  uv run python search/experiments/e037_audit/tamper_audit.py STEM OUT.jsonl
STEM.opb, STEM.pbp from certify.py --keep.
  U   unmodified (must be accepted)
  F1  weight bound W -> W+1                         (formula satisfiable: weight-d logicals exist)
  F2  "some logical odd" row  >= 1  ->  >= 0        (formula trivially satisfiable)
  F3  one column removed from the longest detector row (wrong DEM)
  F4  one column removed from a logical row
  P1  proof truncated to its first 90% of lines
  P2  proof: the last 'pol' / 'rup' / 'p' / 'u' derivation line removed (ids shift)
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VERIPB = ROOT / "tools/veripb/target/release/veripb"


def run(opb, pbp):
    t = time.time()
    p = subprocess.run([str(VERIPB), str(opb), str(pbp)], capture_output=True, text=True)
    ok = any(l.strip() == "s VERIFIED UNSATISFIABLE" for l in p.stdout.splitlines())
    return dict(rc=p.returncode, verified_line=ok, accepted=(ok and p.returncode == 0), wall_s=round(time.time() - t, 1),
                tail=(p.stdout + p.stderr)[-200:])


def main():
    stem, out = sys.argv[1], sys.argv[2]
    opb, pbp = Path(stem + ".opb"), Path(stem + ".pbp")
    lines = opb.read_text().splitlines()
    work = Path(stem + "_tamper"); work.mkdir(exist_ok=True)
    res = []

    def emit(name, o, p, expect):
        r = run(o, p); r.update(name=name, expected_accept=expect, pass_=(r["accepted"] == expect))
        res.append(r); print(json.dumps(r), flush=True)
        with open(out, "a") as f:
            f.write(json.dumps(dict(stem=stem, **r)) + "\n")
    emit("U_unmodified", opb, pbp, True)

    def variant(name, f):
        L = list(lines)
        f(L)
        p = work / (name + ".opb"); p.write_text("\n".join(L) + "\n")
        return p
    wi = next(i for i, l in enumerate(lines) if l.startswith("-1 x1 -1 x2") and l.count(" x") > 1000)

    def f1(L):
        W = int(re.search(r">= -(\d+) ;$", L[wi]).group(1)); L[wi] = re.sub(r">= -\d+ ;$", f">= -{W + 1} ;", L[wi])
    emit("F1_weight_W+1", variant("F1", f1), pbp, False)
    qi = next(i for i, l in enumerate(lines) if l.startswith("1 q1 "))

    def f2(L):
        L[qi] = L[qi].replace(">= 1 ;", ">= 0 ;")
    emit("F2_logical_row_ge0", variant("F2", f2), pbp, False)
    det = [i for i, l in enumerate(lines) if " a" in l and "_0" in l and l.endswith("= 0 ;") and " x" in l]
    di = max(det, key=lambda i: lines[i].count(" x"))

    def f3(L):
        L[di] = re.sub(r"^1 x\d+ ", "", L[di], count=1)
    emit("F3_detector_row_column_removed", variant("F3", f3), pbp, False)
    li = next(i for i, l in enumerate(lines) if " q1 " in l and "= 0 ;" in l)

    def f4(L):
        L[li] = re.sub(r"^1 x\d+ ", "", L[li], count=1)
    emit("F4_logical_row_column_removed", variant("F4", f4), pbp, False)
    P = pbp.read_text().splitlines()
    p1 = work / "P1.pbp"; p1.write_text("\n".join(P[: int(len(P) * 0.9)]) + "\n")
    emit("P1_proof_truncated_90pct", opb, p1, False)
    k = max(i for i, l in enumerate(P[: int(len(P) * 0.5)]) if l.split(" ", 1)[0] in ("pol", "rup", "p", "u"))
    p2 = work / "P2.pbp"; p2.write_text("\n".join(P[:k] + P[k + 1:]) + "\n")
    emit("P2_proof_one_derivation_removed", opb, p2, False)
    print("ALL PASS" if all(r["pass_"] for r in res) else "SOME FAIL")


if __name__ == "__main__":
    main()
