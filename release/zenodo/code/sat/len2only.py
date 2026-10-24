"""Table S5 (retimings that keep the Fig. 12 orders) with the frame model restricted to the 360 weight-11 logicals per
basis of the form "ten data columns + one residual of length 2" (the residual of the last two CNOTs of the check).
For these logicals the direction "frame-model lift => weight-11 undetected error of the circuit" is the one proven in
SM S9, so UNSAT of the restricted CEGAR is a theorem-level obstruction for the family.

The CEGAR drivers are the shipped ones (enc_primary / enc_second with --pin-fig12); only frame.prepare is wrapped so
that it keeps the records of that type.  The final clause set (family encoding + nogoods) is the certificate.

    python code/sat/len2only.py list
    python code/sat/len2only.py NAME [--out FILE.cnf.gz] [--compare FILE.cnf.gz] [--max-sec S]
NAME: one of the 25 rows, e.g. primary_P09_pipelined, second_P09_subgroup_0_3__2_1, primary_P16_common_frame_nosym.
Default --compare: certificates/fig12_retimings_len2only/NAME.cnf.gz (byte-identical body expected).
"""
import argparse
import gzip
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gross12.paths import CERTIFICATES           # noqa: E402
from sat import enc_primary, enc_second, frame   # noqa: E402
from sat.common import fig12_labels, table       # noqa: E402
from sat.recorder import dimacs_body, write_cnf  # noqa: E402

T = table()
F12 = fig12_labels()
_prepare = frame.prepare
KEPT = {}


def is_len2(r):
    """record = ten data columns + one residual equal to the last two CNOT targets of its check."""
    hs = [e for e in r["evs"] if e[0] == "h"]
    if len(hs) != 1:
        return False
    _, a, V = hs[0]
    o = F12[r["kind"]][a]
    return set(V) == {int(T[r["kind"]][a][o[4]]), int(T[r["kind"]][a][o[5]])}


def prepare(F, kind_data, kinds="XZ"):
    recs, skipped = _prepare(F, kind_data, kinds)
    KEPT["all"] = len(recs)
    recs = [r for r in recs if is_len2(r)]
    KEPT["kept"] = len(recs)
    return recs, skipped


frame.prepare = prepare


def sub_name(s):
    return s.replace(",", "_").replace(";", "__")


ROWS = {f"primary_P{P:02d}_pipelined": ("primary", dict(P=P)) for P in range(8, 13)}
ROWS["primary_P38_common_frame"] = ("primary", dict(P=38, nowrap=1))
ROWS["primary_P16_common_frame_nosym"] = ("primary", dict(P=16, nowrap=1, sub="0,0"))
ROWS.update({f"second_P{P:02d}_sym24": ("second", dict(P=P)) for P in range(8, 13)})
ROWS.update({f"second_P09_subgroup_{sub_name(s)}": ("second", dict(P=9, sub=s)) for s in
             ("1,2", "1,5", "0,3;2,1", "2,1", "2,4", "4,5", "0,3;3,0", "0,3;6,0", "3,3", "4,2")})
ROWS.update({f"second_P10_subgroup_{sub_name(s)}": ("second", dict(P=10, sub=s)) for s in ("1,2", "0,3;3,0", "2,4")})


def run(name, max_sec=7200):
    enc, kw = ROWS[name]
    mod = enc_primary if enc == "primary" else enc_second
    t0 = time.process_time()
    st, M, info = mod.run(pin=True, max_sec=max_sec, log=lambda *a, **k: None, **kw)
    info["cpu_sec"] = round(time.process_time() - t0, 1)
    info["records_all"], info["records_kept"] = KEPT["all"], KEPT["kept"]
    return enc, kw, st, M, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--out", default=None)
    ap.add_argument("--compare", default=None)
    ap.add_argument("--max-sec", type=float, default=7200)
    a = ap.parse_args()
    if a.name == "list":
        print("\n".join(ROWS))
        return 0
    enc, kw, st, M, info = run(a.name, a.max_sec)
    cl = M.S.clauses
    print(f"{a.name}: status {st}; {len(cl)} clauses ({M.S.nfamily} family, {len(cl) - M.S.nfamily} nogoods); "
          f"{info['records_kept']} of {info['records_all']} logical records kept; {info}")
    if a.out:
        write_cnf(a.out, cl, header(a.name, enc, kw, st, M))
    ref = Path(a.compare) if a.compare else CERTIFICATES / "fig12_retimings_len2only" / f"{a.name}.cnf.gz"
    ok = st == "UNSAT"
    if ref.exists():
        text = gzip.open(ref, "rt").read()
        same = text[text.index("p cnf"):] == dimacs_body(cl)
        print(("PASS  IDENTICAL" if same else "FAIL  DIFFERENT") + f": clause sequence vs {ref.name}")
        ok &= same
    return 0 if ok else 1


def header(name, enc, kw, st, M):
    return [f"{name}: Fig. 12 orders pinned; {enc} encoding {kw}; frame model restricted to the 360 per basis "
            f"'ten data + one length-2 residual' weight-11 logicals; CEGAR status {st}",
            f"clauses 1..{M.S.nfamily}: family encoding; clauses {M.S.nfamily + 1}..{len(M.S.clauses)}: CEGAR nogoods"]


if __name__ == "__main__":
    sys.exit(main())
