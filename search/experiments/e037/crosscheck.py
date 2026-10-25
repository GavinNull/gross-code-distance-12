"""E-037 task 4: independent cross-check of the encoding/search against E-029's ccsearch (separately written exact
branch and bound, audited in E-029/E-033).  experimenter.

    uv run python search/experiments/e037/crosscheck.py SOURCE W_MIN OUT.jsonl

For one DEM: (1) ccsearch decide W_MIN-1 must print NONE; (2) ccsearch enum W_MIN and pbdfs -e (enumeration, no
proof; with the cardinality constraints and trivial-set closure of the certified runs) must list the same set of
weight-W_MIN solutions (both list each solution once in the case of its lowest orbit); (3) the solutions are expanded
under the translation group and deduplicated -> total number of weight-W_MIN undetectable logicals, which for the SD6
DEM can be compared with E-033 (IBM gross, SD6: 144 (Z) / 288 (X) per round).  Every listed solution is re-verified
directly on the column data (detectors cancel, some observable flips).
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import dem_inst  # noqa: E402

B = ROOT / "results/E-037-ibm-cert/bin"


def main():
    source, W, outp = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    tmp = ROOT / "results/E-037-ibm-cert/crosscheck"
    tmp.mkdir(parents=True, exist_ok=True)
    stem = str(tmp / (source.replace(":", "_") + f"_W{W}"))
    subprocess.run([sys.executable, str(HERE / "dem_inst.py"), source, str(W), stem, "--no-symcheck"], check=True,
                   capture_output=True)
    subprocess.run([sys.executable, str(HERE / "to_cc.py"), stem + ".cols.json", stem + ".json", stem + ".cc"],
                   check=True, capture_output=True)
    rec = dict(source=source, W=W)
    t0 = time.time()
    p = subprocess.run([str(B / "ccsearch"), stem + ".cc", "decide", str(W - 1)], capture_output=True, text=True)
    rec["cc_decide_below"] = p.stdout.strip().splitlines()[-1]
    p = subprocess.run([str(B / "ccsearch"), stem + ".cc", "enum", str(W)], capture_output=True, text=True)
    cc = sorted(tuple(sorted(int(x) for x in l.split(":")[1].split())) for l in p.stdout.splitlines()
                if l.startswith("SOL"))
    rec["cc_enum"] = p.stdout.strip().splitlines()[-1]
    p = subprocess.run([str(B / "pbdfs"), stem + ".inst", "-e", "-R", stem + ".triv"], capture_output=True, text=True)
    pb = sorted(tuple(sorted(int(x) for x in l.split(":")[1].split())) for l in p.stdout.splitlines()
                if l.startswith("SAT columns:"))
    rec["pbdfs_enum"] = [l for l in p.stdout.splitlines() if l.startswith("RESULT")][-1][:80]
    rec["n_cc"], rec["n_pbdfs"] = len(cc), len(pb)
    rec["same_solution_lists"] = cc == pb
    src = dem_inst.load_source(source)
    D, L = src["D"], src["L"]
    bad = 0
    for s in set(cc) | set(pb):
        d, o = set(), set()
        for j in s:
            d ^= set(D[j]); o ^= set(L[j])
        bad += bool(d) or not o or len(s) != W
    rec["bad_solutions"] = bad
    I = dem_inst.build(src, W, cards=())
    tot = set()
    for s in cc:
        for P in I["perms"]:
            tot.add(tuple(sorted(int(P[j]) for j in s)))
    rec["total_weight_W_logicals"] = len(tot)
    rec["n_columns"] = len(D)
    rec["wall_s"] = round(time.time() - t0, 1)
    for ext in (".opb", ".inst"):
        Path(stem + ext).unlink()
    with open(outp, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec))


if __name__ == "__main__":
    main()
