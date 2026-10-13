"""Regenerate a certificate's clause set with the encoders of this directory and compare it with the shipped file.

    python code/sat/regenerate.py primary 8                       # primary encoding, pipelined, P = 8
    python code/sat/regenerate.py primary 20 --common-frame
    python code/sat/regenerate.py second 10                        # second encoding, 24-translation symmetric
    python code/sat/regenerate.py second 11 --sub 1,2              # subgroup <(1,2)>
    python code/sat/regenerate.py second 24 --maxwin 14 --winunits X0
    python code/sat/regenerate.py primary 38 --common-frame --pin-fig12     # Table S3 family (see README)
Options: --out FILE.cnf.gz (write the clause set), --compare CERT.cnf.gz (default: the matching file in
certificates/ when there is one).  The comparison is on the DIMACS body ('p cnf' line and every clause in order,
i.e. byte-identical after the comment header) and, if that differs, on the clause multiset.
"""
import argparse
import gzip
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gross12.paths import CERTIFICATES           # noqa: E402
from sat import enc_primary, enc_second          # noqa: E402
from sat.recorder import dimacs_body, write_cnf  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("encoding", choices=["primary", "second"])
ap.add_argument("P", type=int)
ap.add_argument("--common-frame", action="store_true")
ap.add_argument("--sub", default=None, help="subgroup generators, e.g. '1,2' or '0,3;3,0'; '0,0' = none")
ap.add_argument("--maxwin", type=int, default=None)
ap.add_argument("--winunits", default="")
ap.add_argument("--pin-fig12", action="store_true")
ap.add_argument("--max-sec", type=float, default=5400)
ap.add_argument("--out", default=None)
ap.add_argument("--compare", default=None)
a = ap.parse_args()

if a.encoding == "primary":
    st, M, info = enc_primary.run(a.P, nowrap=int(a.common_frame), sub=a.sub, pin=a.pin_fig12, max_sec=a.max_sec)
    default = CERTIFICATES / "min_period_primary_encoding" / f"P{a.P:02d}_{'common_frame' if a.common_frame else 'pipelined'}.cnf.gz"
else:
    wu = {(x[0], int(x[1:])) for x in a.winunits.split(",")} if a.winunits else None
    st, M, info = enc_second.run(a.P, sub=a.sub or "1,2;0,3", maxwin=a.maxwin, winunits=wu, pin=a.pin_fig12,
                                 max_sec=a.max_sec)
    if a.maxwin:
        default = CERTIFICATES / "window_explanation" / f"P{a.P:02d}_window14_{a.winunits}.cnf.gz"
    elif a.sub in (None, "1,2;0,3"):
        default = CERTIFICATES / "min_period_second_encoding" / f"P{a.P:02d}_pipelined.cnf.gz"
    else:
        default = CERTIFICATES / "less_symmetry" / f"P{a.P:02d}_subgroup_{a.sub.replace(',', '_').replace(';', '__')}.cnf.gz"
if a.pin_fig12:
    R3 = CERTIFICATES / "fig12_retimings"
    if a.encoding == "primary":
        default = R3 / (f"primary_P{a.P:02d}_{'common_frame' if a.common_frame else 'pipelined'}"
                        + ("_nosym" if a.sub == "0,0" else "") + ".cnf.gz")
    else:
        h = info["subgroup_order"]
        default = R3 / (f"second_P{a.P:02d}_" + ("sym24" if h == 24 else "subgroup_" + a.sub.replace(",", "_").replace(";", "__"))
                        + ".cnf.gz")
cl = M.S.clauses
print(f"status {st}; {len(cl)} clauses ({M.S.nfamily} family, {len(cl) - M.S.nfamily} nogoods); {info}")
if a.out:
    write_cnf(a.out, cl, [f"{a.encoding} encoding, P = {a.P}, status {st}",
                          f"clauses 1..{M.S.nfamily}: family encoding; clauses {M.S.nfamily + 1}..{len(cl)}: CEGAR nogoods"])
ref = Path(a.compare) if a.compare else default
if ref is not None and ref.exists():
    text = gzip.open(ref, "rt").read()
    body = text[text.index("p cnf"):]
    mine = dimacs_body(cl)
    if body == mine:
        print(f"PASS  IDENTICAL: clause sequence equals {ref.name} byte for byte (after the comment header)")
    else:
        refcl = [tuple(sorted(map(int, l.split()[:-1]))) for l in body.splitlines()[1:]]
        same = Counter(refcl) == Counter(tuple(sorted(c)) for c in cl)
        print(("PASS  EQUAL UP TO CLAUSE ORDER" if same else "FAIL  DIFFERENT") + f" vs {ref.name}")
        sys.exit(0 if same else 1)
sys.exit(0 if st == "UNSAT" else 2)
